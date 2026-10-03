"""DayFlow offline maintenance CLI.

Dry Run remains read-only. Execution is TTY-confirmed and isolated-only.
"""
from __future__ import annotations

import argparse
import json
import sqlite3
import sys

from app.core.config import get_settings
from app.services.backup_service import BackupService
from app.services.restore_dry_run_service import RestoreDryRunError, RestoreDryRunService
from app.services.restore_service import RestoreService, RestoreFailed
from app.core.restore_io import RestoreRefused
from app.core.errors import AppError
from app.core.maintenance import MaintenanceBlocked
from app.services.recovery_service import RecoveryService
from app.services.storage_service import qualify_storage


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dayflow-maintenance")
    commands = parser.add_subparsers(dest="command", required=True)
    restore = commands.add_parser("restore", help="Restore planning commands")
    restore.add_argument("--dry-run", action="store_true", help="only create a read-only RestorePlan")
    restore.add_argument("backup_id", help="registered Backup UUID4")
    restore.add_argument("--json", action="store_true", help="emit the plan as JSON")
    acknowledge = commands.add_parser("acknowledge", help="reverify completed isolated Restore and clear startup markers")
    acknowledge.add_argument("operation_id")
    for name in ("status", "storage-check"):
        command = commands.add_parser(name)
        command.add_argument("--json", action="store_true")
    return parser


def _service() -> RestoreDryRunService:
    settings = get_settings()
    backup = BackupService(settings.resolved_database_path, settings.backup_root, settings.app_version)
    return RestoreDryRunService(
        backup_service=backup,
        current_database=settings.resolved_database_path,
        maintenance_root=settings.maintenance_root,
        app_version=settings.app_version,
    )


def _human(plan) -> str:
    current = plan.current_database
    lines = [
        "DayFlow Restore Dry Run",
        f"状态：{'可生成恢复计划' if plan.status == 'ready' else '已拒绝'}",
        "",
        "当前数据库：",
        f"  文件：{current.logical_name}",
        f"  应用版本：{current.app_version}",
        f"  文件大小：{current.file_size} bytes",
        f"  Schema：{current.alembic_version or '无法读取'}",
        f"  SHA-256：{current.database_sha256}",
        f"  完整性：{current.integrity_check or '无法读取'}",
        f"  外键错误：{current.foreign_key_errors if current.foreign_key_errors is not None else '无法读取'}",
        f"  WAL/SHM：{'存在' if current.wal_present or current.shm_present else '未发现'}",
        "",
        "目标 Backup：",
    ]
    if plan.target_backup is None:
        lines.append("  未找到已登记的目标 Backup")
    else:
        lines.extend([
            f"  文件：{plan.target_backup.filename}",
            f"  Backup ID：{plan.target_backup.backup_id}",
            f"  Schema：{plan.target_backup.alembic_version}",
            f"  SHA-256：{plan.target_backup.database_sha256}",
        ])
    if plan.target_verification is None:
        lines.append("  验证：未完成")
    else:
        lines.extend([
            f"  验证状态：{plan.target_verification.status}",
            f"  可用于当前 Schema：{'是' if plan.schema_compatible else '否'}",
        ])
    lines.extend(["", f"Schema 兼容性：{'兼容' if plan.schema_compatible else '不兼容或未验证'}", "", "计划步骤："])
    lines.extend(f"  {index}. {step}（本 Dry Run 不执行）" for index, step in enumerate(plan.steps, 1))
    if plan.refusal_reasons:
        lines.extend(["", "拒绝原因：", *(f"  - {reason}" for reason in plan.refusal_reasons)])
    lines.extend(["", "No changes performed."])
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.command != "restore":
        settings = get_settings()
        service = RestoreService(BackupService(settings.resolved_database_path, settings.backup_root, settings.app_version))
        recovery = RecoveryService(service)
        try:
            if args.command == "status":
                result = recovery.status()
            elif args.command == "storage-check":
                result = qualify_storage(settings.resolved_database_path.parent,
                                         settings.backup_root if settings.backup_root.exists() else None)
            else:
                if not sys.stdin.isatty() or not sys.stdout.isatty():
                    raise RestoreRefused("确认仅支持双 TTY 交互。")
                print(json.dumps(recovery.summary(args.operation_id), ensure_ascii=False))
                confirmation = input(f"请输入 ACKNOWLEDGE {args.operation_id}：")
                result = recovery.acknowledge(args.operation_id, confirmation)
            print(json.dumps(result, ensure_ascii=False, indent=2))
            return 0
        except (EOFError, KeyboardInterrupt):
            print("维护确认已取消。", file=sys.stderr)
        except (RestoreRefused, MaintenanceBlocked, AppError, OSError, ValueError, KeyError, TypeError, sqlite3.Error):
            if getattr(args, "json", False):
                print(json.dumps({"status": "rejected", "reason": "维护安全检查未通过。", "real_restore_approved": False}, ensure_ascii=False))
            else:
                print("维护安全检查未通过；不启动服务、不自动清理恢复证据。", file=sys.stderr)
        return 2
    if not args.dry_run:
        if args.json or not sys.stdin.isatty() or not sys.stdout.isatty():
            print("Restore 已拒绝：实际执行仅支持 TTY 交互确认，不支持 JSON 自动执行。", file=sys.stderr)
            return 2
        settings = get_settings()
        service = RestoreService(BackupService(settings.resolved_database_path, settings.backup_root, settings.app_version))
        try:
            summary = service.preview(args.backup_id)
            target_snapshot = summary.pop("_target_snapshot")
            print(json.dumps(summary, ensure_ascii=False, indent=2))
            print("恢复将覆盖当前隔离数据库。请先停止 DayFlow 并关闭外部数据库工具。")
            confirmation = input(f"请输入 RESTORE {args.backup_id}：")
            result = service.execute(args.backup_id, confirmation, expected_target_sha=summary["target_sha256"],
                                     expected_target_snapshot=target_snapshot)
            print(f"Restore completed: operation_id={result.operation_id}; backup_id={result.backup_id}; safety_backup_id={result.safety_backup_id}")
            print("Final verification: PASS\nDayFlow remains stopped.\nMaintenance confirmation is still required before restart.")
            return 0
        except (EOFError, KeyboardInterrupt):
            print("Restore 已取消。", file=sys.stderr)
        except RestoreFailed as exc:
            print(f"Restore failed: operation_id={exc.operation_id}; stage={exc.stage}; {exc}", file=sys.stderr)
        except (RestoreRefused, MaintenanceBlocked, AppError, OSError, ValueError, sqlite3.Error):
            print("Restore blocked：准入或安全检查未通过；不会自动恢复或启动服务。", file=sys.stderr)
        return 2
    try:
        plan = _service().build_plan(args.backup_id)
    except RestoreDryRunError as exc:
        if args.json:
            print(json.dumps({"status": "rejected", "error": str(exc), "changes_performed": False, "lock_created": False, "database_write_performed": False}, ensure_ascii=False, indent=2))
        else:
            print(f"Restore Dry Run 已拒绝：{exc}\nNo changes performed.")
        return 2
    if args.json:
        print(json.dumps(plan.model_dump(mode="json"), ensure_ascii=False, indent=2))
    else:
        print(_human(plan))
    return 0 if plan.status == "ready" else 2


if __name__ == "__main__":
    raise SystemExit(main())
