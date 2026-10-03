"""Durable completed acknowledgement; never restores or deletes evidence."""
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import datetime
import hashlib
import json
import os
from typing import Literal
from uuid import UUID, uuid4

from pydantic import BaseModel, ConfigDict, Field, UUID4, field_validator, model_validator

from app.core.maintenance import MaintenanceBlocked, MaintenanceRecord
from app.core.restore_io import RestoreRefused, directory, identity, regular, same_mount
from app.services.backup_service import SCHEMA, timestamp
from app.services.restore_service import RestoreService, logical_status


RECEIPT = "startup-clearance.json"
LOG = "events.jsonl"


def _canonical(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True,
                       separators=(",", ":")) + "\n").encode()


def _digest(value: object) -> str:
    payload = value if isinstance(value, bytes) else _canonical(value)
    return hashlib.sha256(payload).hexdigest()


class TableFingerprint(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True)
    columns: list[str]
    count: int = Field(ge=0)
    sha256: str

    @field_validator("sha256")
    @classmethod
    def sha256_digest(cls, value: str) -> str:
        if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
            raise ValueError("Expected SHA-256")
        return value


class ClearanceReceipt(BaseModel):
    """Immutable mirrored authority; both copies and all evidence must verify."""

    model_config = ConfigDict(extra="forbid", frozen=True)
    format_version: Literal[1] = 1
    operation_id: UUID4
    restore_operation_id: UUID4
    backup_id: UUID4
    acknowledged_at_utc: str
    app_version: str = Field(min_length=1, max_length=64)
    completed_state: MaintenanceRecord
    acquisition_state: MaintenanceRecord
    completed_state_identity: str
    live_database_sha256: str
    live_database_size: int = Field(ge=0)
    schema_version: str
    logical_fingerprint: dict[str, TableFingerprint]
    final_verification_identity: str
    acknowledge_confirmation_identity: str
    operation_log_reference: Literal["events.jsonl"] = LOG
    operation_log_sha256: str
    workspace_receipt: Literal["startup-clearance.json"] = RECEIPT

    @field_validator("acknowledged_at_utc")
    @classmethod
    def utc_timestamp(cls, value: str) -> str:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        if not value.endswith("Z") or parsed.utcoffset() is None or parsed.utcoffset().total_seconds() != 0:
            raise ValueError("Expected UTC timestamp")
        return value

    @field_validator("completed_state_identity", "live_database_sha256",
                     "final_verification_identity", "acknowledge_confirmation_identity",
                     "operation_log_sha256")
    @classmethod
    def sha256(cls, value: str) -> str:
        if len(value) != 64 or any(char not in "0123456789abcdef" for char in value):
            raise ValueError("Expected SHA-256")
        return value

    @model_validator(mode="after")
    def coherent(self) -> "ClearanceReceipt":
        selected = str(self.operation_id)
        if (self.restore_operation_id != self.operation_id
                or str(self.completed_state.lock_id) != selected
                or str(self.acquisition_state.lock_id) != selected
                or self.completed_state.format_version != 2
                or self.acquisition_state.format_version != 2
                or self.completed_state.operation != "restore"
                or self.acquisition_state.operation != "restore"
                or self.completed_state.stage != "completed"
                or self.acquisition_state.stage != "prepare"
                or self.schema_version != SCHEMA):
            raise ValueError("Incoherent clearance receipt")
        return self


def operation_id(value: str) -> str:
    try:
        parsed = UUID(value)
    except (TypeError, ValueError) as exc:
        raise RestoreRefused("操作 ID 必须为规范 UUID4。") from exc
    if parsed.version != 4 or str(parsed) != value:
        raise RestoreRefused("操作 ID 必须为规范 UUID4。")
    return value


class RecoveryService:
    def __init__(self, restore: RestoreService):
        self.restore = restore
        self.maintenance = restore.maintenance

    @staticmethod
    def read_bytes(parent: int, name: str, *, limit: int = 4 * 1024 * 1024) -> bytes:
        fd = regular(parent, name)
        try:
            before = os.fstat(fd)
            if before.st_size > limit:
                raise RestoreRefused("恢复记录过大，必须人工检查。")
            with os.fdopen(os.dup(fd), "rb") as stream:
                payload = stream.read(limit + 1)
            after = os.fstat(fd)
            named = os.stat(name, dir_fd=parent, follow_symlinks=False)
            keys = lambda item: (item.st_dev, item.st_ino, item.st_size,
                                 item.st_mtime_ns, item.st_ctime_ns)
            if len(payload) > limit or keys(before) != keys(after) or keys(before) != keys(named):
                raise RestoreRefused("恢复记录在读取期间发生变化。")
            return payload
        finally:
            os.close(fd)

    @classmethod
    def read_json(cls, parent: int, name: str, *, limit: int = 4 * 1024 * 1024):
        return json.loads(cls.read_bytes(parent, name, limit=limit))

    @staticmethod
    def _write_once(parent: int, name: str, payload: bytes) -> None:
        temporary = f"clearance-{uuid4().hex}.partial"
        fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW,
                     0o600, dir_fd=parent)
        with os.fdopen(fd, "wb") as stream:
            stream.write(payload)
            stream.flush()
            os.fsync(stream.fileno())
        os.link(temporary, name, src_dir_fd=parent, dst_dir_fd=parent,
                follow_symlinks=False)
        os.unlink(temporary, dir_fd=parent)
        os.fsync(parent)

    @staticmethod
    def _events(payload: bytes) -> list[dict]:
        events = [json.loads(line) for line in payload.decode().splitlines()]
        if not events or any(not isinstance(event, dict) for event in events):
            raise RestoreRefused("操作日志格式无效。")
        return events

    @staticmethod
    def _one(events: list[dict], name: str) -> dict:
        matches = [event for event in events if event.get("event") == name]
        if len(matches) != 1:
            raise RestoreRefused("最终验证记录不完整。")
        return matches[0]

    def _live(self, live: int, work: int, backup_id: str, expected: str,
              expected_size: int, fingerprint: dict) -> dict:
        measured = self.restore.backup._inspect(live, self.restore.source.name, backup_id)
        if (measured.status != "valid" or not measured.compatible_for_restore
                or measured.database_sha256 != expected or measured.file_size != expected_size
                or measured.alembic_version != SCHEMA or measured.integrity_check != "ok"
                or measured.foreign_key_errors != 0 or not measured.structure_valid):
            raise RestoreRefused("当前数据库未通过 completed 复验。")
        actual = logical_status(self.restore.source, standalone=True)
        if (actual != fingerprint
                or identity(live, self.restore.source.name)[-1] != expected
                or set(self.restore.inventory(live)) != {self.restore.source.name}
                or identity(work, "candidate.sqlite3")[-1] != expected):
            raise RestoreRefused("当前数据库或 Candidate 与完成记录不一致。")
        return actual

    def _validate_clearance(self, maintenance_fd: int) -> ClearanceReceipt:
        active = self.read_bytes(maintenance_fd, self.maintenance.CLEARANCE,
                                 limit=1024 * 1024)
        receipt = ClearanceReceipt.model_validate_json(active)
        selected = str(receipt.operation_id)
        workspace = self.restore.backup.root / "restore-operations" / selected
        with directory(self.restore.source.parent) as live, directory(workspace) as work:
            if not same_mount(live, work) or not same_mount(live, maintenance_fd):
                raise RestoreRefused("维护目录挂载身份不一致。")
            if self.read_bytes(work, receipt.workspace_receipt, limit=1024 * 1024) != active:
                raise RestoreRefused("Clearance Receipt 镜像不一致。")
            metadata = self.read_json(work, "operation.json", limit=16384)
            if (not isinstance(metadata, dict) or metadata.get("operation_id") != selected
                    or metadata.get("backup_id") != str(receipt.backup_id)
                    or metadata.get("target", {}).get("database_sha256") != receipt.live_database_sha256
                    or metadata.get("target", {}).get("file_size") != receipt.live_database_size
                    or metadata.get("target", {}).get("alembic_version") != SCHEMA):
                raise RestoreRefused("操作元数据与 Clearance Receipt 不一致。")
            log = self.read_bytes(work, receipt.operation_log_reference)
            if _digest(log) != receipt.operation_log_sha256:
                raise RestoreRefused("操作日志与 Clearance Receipt 不一致。")
            events = self._events(log)
            result = self._one(events, "result")
            final = self._one(events, "final_verified")
            decision = self._one(events, "acknowledge_decision_prepared")
            fingerprint = receipt.model_dump(mode="json")["logical_fingerprint"]
            if (result.get("status") != "completed"
                    or final.get("sha256") != receipt.live_database_sha256
                    or final.get("fingerprint") != fingerprint
                    or _digest(final) != receipt.final_verification_identity
                    or decision.get("operation_id") != selected
                    or decision.get("sha256") != receipt.live_database_sha256
                    or decision.get("completed_state_identity") != receipt.completed_state_identity
                    or decision.get("final_verification_identity") != receipt.final_verification_identity
                    or decision.get("confirmation_identity") != receipt.acknowledge_confirmation_identity
                    or events[-1] is not decision):
                raise RestoreRefused("确认决定或最终验证记录不一致。")
            completed = receipt.completed_state.model_dump(mode="json")
            acquisition = receipt.acquisition_state.model_dump(mode="json")
            if (_digest(completed) != receipt.completed_state_identity
                    or receipt.app_version != self.restore.backup.app_version
                    or completed | {"stage": "prepare"} != acquisition):
                raise RestoreRefused("已归档的 active state 身份不一致。")
            self._live(live, work, str(receipt.backup_id),
                       receipt.live_database_sha256, receipt.live_database_size,
                       fingerprint)
        return receipt

    def validate_clearance(self, maintenance_fd: int) -> None:
        """Privacy-safe startup validator called while holding SH/EX gate."""
        try:
            self._validate_clearance(maintenance_fd)
        except MaintenanceBlocked:
            raise
        except Exception as exc:
            raise MaintenanceBlocked("Startup clearance 无法安全验证。") from exc

    def _restore_workspace_ids(self) -> set[str]:
        """Find retained Restore workspaces without treating their absence as proof.

        A completed Restore workspace is durable evidence. If it remains after
        active markers disappear, startup is only safe when the matching
        durable Clearance Receipt is also present and fully validated.
        """
        operations = self.restore.backup.root / "restore-operations"
        try:
            with directory(operations) as operations_fd:
                names = os.listdir(operations_fd)
                result: set[str] = set()
                for name in names:
                    try:
                        selected = operation_id(name)
                    except RestoreRefused as exc:
                        raise MaintenanceBlocked("恢复工作目录存在未知或不完整记录。") from exc
                    # Opening each entry as a directory rejects symlinks,
                    # regular files, and other path substitutions.
                    with directory(operations / selected):
                        pass
                    result.add(selected)
                return result
        except FileNotFoundError:
            return set()
        except MaintenanceBlocked:
            raise
        except Exception as exc:
            raise MaintenanceBlocked("恢复工作目录无法安全验证。") from exc

    def _active_clearance_operation_id(self) -> str | None:
        """Read the already validated active Receipt identity, if present."""
        with self.maintenance._directory(create=False) as maintenance_fd:
            if maintenance_fd is None:
                return None
            if self.maintenance.CLEARANCE not in os.listdir(maintenance_fd):
                return None
            receipt = ClearanceReceipt.model_validate_json(
                self.read_bytes(maintenance_fd, self.maintenance.CLEARANCE, limit=1024 * 1024)
            )
            return str(receipt.operation_id)

    def _enforce_restore_history(self, clearance_present: bool) -> None:
        """Never allow retained Restore evidence to be hidden by marker absence."""
        workspace_ids = self._restore_workspace_ids()
        if not workspace_ids:
            return
        if not clearance_present:
            raise MaintenanceBlocked("存在未确认的 Restore 证据；启动已阻断。")
        clearance_id = self._active_clearance_operation_id()
        if clearance_id is None or workspace_ids != {clearance_id}:
            raise MaintenanceBlocked("Restore 证据与 Clearance Receipt 不一致；启动已阻断。")

    def check_startup(self) -> bool:
        clearance = self.maintenance.check_startup(self.validate_clearance)
        self._enforce_restore_history(clearance)
        return clearance

    @contextmanager
    def backend_usage(self) -> Iterator[None]:
        with self.maintenance.backend_usage(self.validate_clearance) as clearance:
            self._enforce_restore_history(clearance)
            yield

    def status(self) -> dict:
        """Read-only inspection; it neither creates state nor authorizes cleanup."""
        try:
            workspace_ids = self._restore_workspace_ids()
            with self.maintenance._directory(create=False) as maintenance_fd:
                if maintenance_fd is None or not os.listdir(maintenance_fd):
                    if workspace_ids:
                        return {"startup_blocked": True, "startup_allowed": False,
                                "stage": "unreadable", "operation_id": None,
                                "acknowledge_committed": False, "cleanup_complete": False,
                                "acknowledgement_candidate": False,
                                "blocking_reason": "unacknowledged_restore_evidence"}
                    return {"startup_blocked": False, "startup_allowed": True,
                            "stage": "idle", "operation_id": None,
                            "acknowledge_committed": False, "cleanup_complete": True,
                            "acknowledgement_candidate": False,
                            "blocking_reason": None}
                with self.maintenance._gate(maintenance_fd, exclusive=False, create=False):
                    entries = set(os.listdir(maintenance_fd))
                    clearance = None
                    if self.maintenance.CLEARANCE in entries:
                        clearance = self._validate_clearance(maintenance_fd)
                    state = self.maintenance._read(maintenance_fd, self.maintenance.STATE)
                    try:
                        self.maintenance._check(maintenance_fd, self.validate_clearance)
                        allowed = True
                    except MaintenanceBlocked:
                        allowed = False
                    if allowed:
                        try:
                            self._enforce_restore_history(clearance is not None)
                        except MaintenanceBlocked:
                            allowed = False
                    return {
                        "startup_blocked": not allowed,
                        "startup_allowed": allowed,
                        "stage": state.stage if state else ("acknowledged" if clearance else "idle"),
                        "operation_id": str(state.lock_id) if state else (str(clearance.operation_id) if clearance else None),
                        "acknowledge_committed": clearance is not None,
                        "cleanup_complete": bool(clearance and entries == {self.maintenance.GATE, self.maintenance.CLEARANCE}),
                        "acknowledgement_candidate": bool(
                            state and state.format_version == 2
                            and state.operation == "restore" and state.stage == "completed"
                        ),
                        "blocking_reason": None if allowed else "active_or_invalid_maintenance_state",
                    }
        except Exception:
            return {"startup_blocked": True, "startup_allowed": False,
                    "stage": "unreadable", "operation_id": None,
                    "acknowledge_committed": False, "cleanup_complete": False,
                    "acknowledgement_candidate": False,
                    "blocking_reason": "maintenance_state_unreadable"}

    def summary(self, selected: str) -> dict:
        selected = operation_id(selected)
        self.restore.isolation()
        state = self.maintenance.inspect()
        if (state is None or str(state.lock_id) != selected or state.format_version != 2
                or state.operation != "restore" or state.stage != "completed"):
            raise RestoreRefused("操作不是可确认的已完成 V2 Restore。")
        return {"operation_id": selected, "stage": state.stage,
                "action": "复验并持久化启动 Clearance；保留全部恢复证据，不启动服务。"}

    def acknowledge(self, selected: str, confirmation: str) -> dict:
        selected = operation_id(selected)
        if confirmation != f"ACKNOWLEDGE {selected}":
            raise RestoreRefused("确认文本不匹配。")
        self.restore.isolation()
        workspace = self.restore.backup.root / "restore-operations" / selected
        with self.maintenance.recovery_lease(selected) as (maintenance_fd, state):
            with directory(self.restore.source.parent) as live, directory(workspace) as work:
                if not same_mount(live, work) or not same_mount(live, maintenance_fd):
                    raise RestoreRefused("维护目录挂载身份不一致。")
                metadata = self.read_json(work, "operation.json", limit=16384)
                events = self._events(self.read_bytes(work, LOG))
                if (not isinstance(metadata, dict) or metadata.get("operation_id") != selected
                        or events[0].get("event") != "prepare"
                        or events[0].get("operation_id") != selected
                        or events[-1].get("event") != "result"
                        or events[-1].get("status") != "completed"):
                    raise RestoreRefused("操作记录缺失、未完成或身份不一致。")
                target = metadata.get("target", {})
                expected = target.get("database_sha256")
                final = self._one(events, "final_verified")
                candidates = self._one(events, "candidates_verified")
                target_verified = self._one(events, "target_verified")
                self._one(events, "install_done")
                acquisition = self.maintenance._read(maintenance_fd, self.maintenance.LOCK)
                if (acquisition is None or metadata.get("backup_id") != target.get("backup_id")
                        or target.get("alembic_version") != SCHEMA
                        or any(event.get("sha256") != expected
                               for event in (target_verified, candidates, final))
                        or candidates.get("fingerprint") != final.get("fingerprint")):
                    raise RestoreRefused("恢复哈希、Schema 或逻辑记录不一致。")
                fingerprint = self._live(live, work, metadata["backup_id"], expected,
                                         target["file_size"], final["fingerprint"])
                inventory = self.restore.inventory(live)
                from app.services.restore_service import external_users
                external_users({item[:2] for item in inventory.values()})
                if self.restore.inventory(live) != inventory:
                    raise RestoreRefused("确认期间数据库发生变化。")

                # Phase A: every decision input is durable before blockers move.
                state_identity = _digest(state.model_dump(mode="json"))
                final_identity = _digest(final)
                confirmation_identity = _digest(f"ACKNOWLEDGE {selected}".encode())
                fields = dict(operation_id=selected, sha256=expected,
                              completed_state_identity=state_identity,
                              final_verification_identity=final_identity,
                              confirmation_identity=confirmation_identity)
                self.restore.record(workspace, "acknowledge_verified", **fields)
                self.restore.record(workspace, "acknowledge_decision_prepared", **fields)
                committed_log = self.read_bytes(work, LOG)
                receipt = ClearanceReceipt(
                    operation_id=selected, restore_operation_id=selected,
                    backup_id=metadata["backup_id"], acknowledged_at_utc=timestamp(),
                    app_version=self.restore.backup.app_version,
                    completed_state=state, acquisition_state=acquisition,
                    completed_state_identity=state_identity,
                    live_database_sha256=expected, live_database_size=target["file_size"],
                    schema_version=SCHEMA, logical_fingerprint=fingerprint,
                    final_verification_identity=final_identity,
                    acknowledge_confirmation_identity=confirmation_identity,
                    operation_log_sha256=_digest(committed_log),
                )
                receipt_bytes = _canonical(receipt.model_dump(mode="json"))
                self._write_once(work, RECEIPT, receipt_bytes)
                self.maintenance.publish_clearance(maintenance_fd, receipt_bytes)
                # The mirrored, fsynced receipt above is the commit point.
                # Validate that exact authority while blockers are still intact;
                # an implementation or evidence mismatch cannot enter cleanup.
                self._validate_clearance(maintenance_fd)

                # Phase B: post-commit housekeeping. Clearance is never deleted;
                # startup never depends on a compensation write.
                cleanup_complete = True
                cleanup_error: str | None = None
                for name in (self.maintenance.LOCK, self.maintenance.STATE):
                    try:
                        os.unlink(name, dir_fd=maintenance_fd)
                        os.fsync(maintenance_fd)
                    except OSError:
                        cleanup_complete = False
                        cleanup_error = "active_blocker_cleanup_incomplete"
                        break
                try:
                    self.maintenance._check(maintenance_fd, self.validate_clearance)
                    startup_allowed = True
                except MaintenanceBlocked:
                    startup_allowed = False
                    cleanup_complete = False
                    cleanup_error = cleanup_error or "active_blocker_remains"
                return {
                    "operation_id": selected,
                    "status": "acknowledge_committed",
                    "acknowledge_committed": True,
                    "cleanup_complete": cleanup_complete,
                    "startup_allowed": startup_allowed,
                    "cleanup_status": cleanup_error,
                    "database_sha256": expected,
                    "evidence_deleted": False,
                    "services_started": False,
                }
