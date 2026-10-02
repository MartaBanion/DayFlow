"""Read-only Restore planning. This module cannot switch or write a database."""
from __future__ import annotations

from contextlib import closing
from dataclasses import dataclass
import hashlib
import os
from pathlib import Path
import sqlite3
import stat

from app.core.errors import AppError
from app.core.maintenance import MaintenanceBlocked, MaintenanceSafety
from app.schemas.backup import BackupRead, BackupVerification
from app.schemas.restore import CurrentDatabaseStatus, RestorePlan
from app.services.backup_service import BackupService, SCHEMA


class RestoreDryRunError(RuntimeError):
    """A safe refusal before a RestorePlan can be evaluated."""


STEPS = [
    "再次验证目标 Backup、Schema、完整性和外键状态",
    "获取并验证 Maintenance lock，记录 Restore 状态",
    "停止并确认受管 DayFlow 服务已安全退出",
    "确认当前数据库没有未知使用者或活跃连接",
    "创建并验证当前数据库的 Pre-Restore Safety Backup",
    "重新验证目标 Backup，并生成独立 Restore candidate",
    "验证 candidate 的 SQLite、外键、Schema 和关键结构",
    "在保留原数据库及 WAL/SHM 材料的前提下执行受控切换",
    "验证最终数据库，记录结果，并保持服务停止",
]


@dataclass(frozen=True)
class RestoreDryRunService:
    backup_service: BackupService
    current_database: Path
    maintenance_root: Path
    app_version: str
    timeout: float = 10.0

    @staticmethod
    def _file_digest(path: Path) -> tuple[int, str, os.stat_result]:
        try:
            before = path.stat()
            if not stat.S_ISREG(before.st_mode) or path.is_symlink():
                raise RestoreDryRunError("当前数据库不是安全的普通文件。")
            with path.open("rb") as stream:
                digest = hashlib.file_digest(stream, "sha256").hexdigest()
            after = path.stat()
        except (OSError, ValueError) as exc:
            raise RestoreDryRunError("当前数据库不可读取，Dry Run 已拒绝。") from exc
        identity = (before.st_dev, before.st_ino, before.st_size, before.st_mtime_ns, before.st_ctime_ns)
        current_identity = (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns, after.st_ctime_ns)
        if identity != current_identity:
            raise RestoreDryRunError("当前数据库在只读检查期间发生变化，Dry Run 已拒绝。")
        return after.st_size, digest, after

    def current_status(self) -> CurrentDatabaseStatus:
        file_size, digest, _ = self._file_digest(self.current_database)
        alembic_version: str | None = None
        integrity: str | None = None
        foreign_key_errors: int | None = None
        structure_valid = False
        try:
            uri = self.current_database.as_uri() + "?mode=ro"
            with closing(sqlite3.connect(uri, uri=True, timeout=min(self.timeout, 1.0))) as connection:
                connection.execute("PRAGMA query_only=ON")
                connection.execute("PRAGMA trusted_schema=OFF")
                integrity = connection.execute("PRAGMA integrity_check").fetchone()[0]
                foreign_key_errors = len(connection.execute("PRAGMA foreign_key_check").fetchall())
                rows = connection.execute("SELECT version_num FROM alembic_version").fetchall()
                if len(rows) == 1 and isinstance(rows[0][0], str):
                    alembic_version = rows[0][0]
                structure_valid = BackupService._structure(connection)
        except (OSError, sqlite3.Error) as exc:
            raise RestoreDryRunError("当前数据库不可进行只读验证，Dry Run 已拒绝。") from exc
        self._file_digest(self.current_database)
        return CurrentDatabaseStatus(
            logical_name=self.current_database.name,
            app_version=self.app_version,
            file_size=file_size,
            database_sha256=digest,
            alembic_version=alembic_version,
            integrity_check=integrity,
            foreign_key_errors=foreign_key_errors,
            structure_valid=structure_valid,
            readable=True,
            wal_present=Path(f"{self.current_database}-wal").exists(),
            shm_present=Path(f"{self.current_database}-shm").exists(),
        )

    def _target_metadata(self, backup_id: str) -> BackupRead | None:
        return next((item for item in self.backup_service.list() if item.backup_id == backup_id), None)

    def _verify_target(self, backup_id: str) -> tuple[BackupRead | None, BackupVerification | None, list[str]]:
        reasons: list[str] = []
        target: BackupRead | None = None
        try:
            target = self._target_metadata(backup_id)
            verification = self.backup_service.verify(backup_id)
        except (AppError, OSError) as exc:
            if not isinstance(exc, AppError):
                reasons.append("目标 Backup 无法验证，Dry Run 已拒绝。")
                return target, None, reasons
            if exc.code == "backup_not_found":
                reasons.append("目标 Backup 不存在、未登记或文件不可用。")
            elif exc.code == "backup_id_invalid":
                reasons.append("目标 Backup ID 无效。")
            else:
                reasons.append("目标 Backup 无法验证，Dry Run 已拒绝。")
            return target, None, reasons
        if verification.status != "valid" or not verification.compatible_for_restore:
            status_text = {
                "incompatible": "目标 Backup 的 Schema 不兼容当前版本。",
                "manifest_mismatch": "目标 Backup 与 Manifest 不匹配。",
                "corrupted": "目标 Backup 完整性或关键结构验证失败。",
                "unreadable": "目标 Backup 不可读取或路径不安全。",
            }
            reasons.append(status_text.get(verification.status, "目标 Backup 未通过恢复兼容性验证。"))
        return target, verification, reasons

    def build_plan(self, backup_id: str) -> RestorePlan:
        current = self.current_status()
        reasons: list[str] = []
        try:
            MaintenanceSafety(self.maintenance_root, self.app_version).check_startup()
        except MaintenanceBlocked:
            reasons.append("维护或恢复状态未完成，不能生成可执行恢复计划。")

        if current.alembic_version != SCHEMA:
            reasons.append("当前数据库 Schema 不是受支持的 0005 版本。")
        if current.integrity_check != "ok":
            reasons.append("当前数据库 integrity_check 未通过。")
        if current.foreign_key_errors != 0:
            reasons.append("当前数据库存在外键错误。")
        if not current.structure_valid:
            reasons.append("当前数据库关键结构验证未通过。")

        target, verification, target_reasons = self._verify_target(backup_id)
        reasons.extend(target_reasons)
        schema_compatible = bool(verification and verification.compatible_for_restore and verification.status == "valid")
        ready = not reasons and schema_compatible
        return RestorePlan(
            status="ready" if ready else "rejected",
            current_database=current,
            target_backup=target,
            target_verification=verification,
            schema_compatible=schema_compatible,
            steps=STEPS,
            refusal_reasons=reasons,
        )
