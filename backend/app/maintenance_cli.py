"""DayFlow offline maintenance CLI.

Only ``restore --dry-run`` is implemented here. It never obtains a maintenance
lock and never replaces, copies, migrates, or writes a database.
"""
from __future__ import annotations

import argparse
import json
import sys

from app.core.config import get_settings
from app.services.backup_service import BackupService
from app.services.restore_dry_run_service import RestoreDryRunError, RestoreDryRunService


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="dayflow-maintenance")
    commands = parser.add_subparsers(dest="command", required=True)
    restore = commands.add_parser("restore", help="Restore planning commands")
    restore.add_argument("--dry-run", action="store_true", required=True, help="only create a read-only RestorePlan")
    restore.add_argument("backup_id", help="registered Backup UUID4")
    restore.add_argument("--json", action="store_true", help="emit the plan as JSON")
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
