"""Add V0.5 Deadlines, Recurrence, and Reminders.

Revision ID: 0005_add_deadlines_recurrence_reminders
Revises: 0004_add_projects
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0005_add_deadlines_recurrence_reminders"
down_revision: Union[str, Sequence[str], None] = "0004_add_projects"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TASK_TAGS_BACKUP_TABLE = "_dayflow_task_tags_backup_0005"


def _backup_task_tags() -> None:
    op.create_table(
        _TASK_TAGS_BACKUP_TABLE,
        sa.Column("task_id", sa.String(length=36), nullable=False),
        sa.Column("tag_id", sa.String(length=36), nullable=False),
        sa.PrimaryKeyConstraint("task_id", "tag_id"),
    )
    op.execute(
        sa.text(
            f"INSERT INTO {_TASK_TAGS_BACKUP_TABLE} (task_id, tag_id) "
            "SELECT task_id, tag_id FROM task_tags"
        )
    )


def _restore_task_tags() -> None:
    op.execute(
        sa.text(
            "INSERT INTO task_tags (task_id, tag_id) "
            f"SELECT task_id, tag_id FROM {_TASK_TAGS_BACKUP_TABLE}"
        )
    )
    op.drop_table(_TASK_TAGS_BACKUP_TABLE)


def upgrade() -> None:
    op.create_table(
        "recurrence_rules",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("frequency", sa.String(length=20), nullable=False),
        sa.Column("weekdays_mask", sa.Integer(), nullable=True),
        sa.Column("month_day", sa.Integer(), nullable=True),
        sa.Column("starts_on", sa.Date(), nullable=False),
        sa.Column("timezone", sa.String(length=64), nullable=False),
        sa.Column("stopped_at_utc", sa.String(length=32), nullable=True),
        sa.Column("created_at_utc", sa.String(length=32), nullable=False),
        sa.Column("updated_at_utc", sa.String(length=32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.CheckConstraint(
            "frequency IN ('daily', 'weekly', 'monthly')",
            name="ck_recurrence_rules_frequency",
        ),
        sa.CheckConstraint(
            "(frequency = 'daily' AND weekdays_mask IS NULL AND month_day IS NULL) "
            "OR (frequency = 'weekly' AND weekdays_mask IS NOT NULL AND weekdays_mask BETWEEN 1 AND 127 AND month_day IS NULL) "
            "OR (frequency = 'monthly' AND weekdays_mask IS NULL AND month_day IS NOT NULL AND month_day BETWEEN 1 AND 28)",
            name="ck_recurrence_rules_selector",
        ),
        sa.CheckConstraint("version >= 1", name="ck_recurrence_rules_version_positive"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_recurrence_rules_stopped", "recurrence_rules", ["stopped_at_utc"]
    )

    _backup_task_tags()
    with op.batch_alter_table("tasks", recreate="always") as batch_op:
        batch_op.add_column(sa.Column("deadline_date", sa.Date(), nullable=True))
        batch_op.add_column(sa.Column("deadline_at_utc", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("deadline_timezone", sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column("recurrence_rule_id", sa.String(length=36), nullable=True))
        batch_op.add_column(sa.Column("recurrence_occurrence_date", sa.Date(), nullable=True))
        batch_op.create_foreign_key(
            "fk_tasks_recurrence_rule_id_recurrence_rules",
            "recurrence_rules",
            ["recurrence_rule_id"],
            ["id"],
            ondelete="RESTRICT",
        )
        batch_op.create_check_constraint(
            "ck_tasks_deadline_state",
            "(deadline_date IS NULL AND deadline_at_utc IS NULL AND deadline_timezone IS NULL) "
            "OR (deadline_date IS NOT NULL AND deadline_at_utc IS NULL AND deadline_timezone IS NOT NULL) "
            "OR (deadline_date IS NOT NULL AND deadline_at_utc IS NOT NULL AND deadline_timezone IS NOT NULL)",
        )
        batch_op.create_check_constraint(
            "ck_tasks_recurrence_pair",
            "(recurrence_rule_id IS NULL AND recurrence_occurrence_date IS NULL) "
            "OR (recurrence_rule_id IS NOT NULL AND recurrence_occurrence_date IS NOT NULL)",
        )
        batch_op.create_index(
            "ix_tasks_deadline_date_active",
            ["deadline_date", "deleted_at_utc", "status"],
        )
        batch_op.create_index(
            "uq_tasks_recurrence_occurrence",
            ["recurrence_rule_id", "recurrence_occurrence_date"],
            unique=True,
        )
    _restore_task_tags()

    op.create_table(
        "reminders",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("task_id", sa.String(length=36), nullable=False),
        sa.Column("trigger_at_utc", sa.String(length=32), nullable=False),
        sa.Column("reminder_timezone", sa.String(length=64), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False, server_default="pending"),
        sa.Column("acknowledged_at_utc", sa.String(length=32), nullable=True),
        sa.Column("dismissed_at_utc", sa.String(length=32), nullable=True),
        sa.Column("created_at_utc", sa.String(length=32), nullable=False),
        sa.Column("updated_at_utc", sa.String(length=32), nullable=False),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.ForeignKeyConstraint(["task_id"], ["tasks.id"], ondelete="CASCADE"),
        sa.CheckConstraint(
            "status IN ('pending', 'acknowledged', 'dismissed')",
            name="ck_reminders_status",
        ),
        sa.CheckConstraint(
            "(status = 'pending' AND acknowledged_at_utc IS NULL AND dismissed_at_utc IS NULL) "
            "OR (status = 'acknowledged' AND acknowledged_at_utc IS NOT NULL AND dismissed_at_utc IS NULL) "
            "OR (status = 'dismissed' AND acknowledged_at_utc IS NULL AND dismissed_at_utc IS NOT NULL)",
            name="ck_reminders_state_timestamps",
        ),
        sa.CheckConstraint("version >= 1", name="ck_reminders_version_positive"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_reminders_status_trigger", "reminders", ["status", "trigger_at_utc"]
    )
    op.create_index("ix_reminders_task_status", "reminders", ["task_id", "status"])


def downgrade() -> None:
    connection = op.get_bind()
    deadline_count = connection.execute(
        sa.text(
            "SELECT COUNT(*) FROM tasks WHERE deadline_date IS NOT NULL "
            "OR deadline_at_utc IS NOT NULL OR deadline_timezone IS NOT NULL"
        )
    ).scalar_one()
    recurrence_reference_count = connection.execute(
        sa.text(
            "SELECT COUNT(*) FROM tasks WHERE recurrence_rule_id IS NOT NULL "
            "OR recurrence_occurrence_date IS NOT NULL"
        )
    ).scalar_one()
    rule_count = connection.execute(
        sa.text("SELECT COUNT(*) FROM recurrence_rules")
    ).scalar_one()
    reminder_count = connection.execute(
        sa.text("SELECT COUNT(*) FROM reminders")
    ).scalar_one()
    if deadline_count or recurrence_reference_count or rule_count or reminder_count:
        raise RuntimeError(
            "Cannot downgrade 0005_add_deadlines_recurrence_reminders while V0.5 data exists"
        )

    op.drop_index("ix_reminders_task_status", table_name="reminders")
    op.drop_index("ix_reminders_status_trigger", table_name="reminders")
    op.drop_table("reminders")

    _backup_task_tags()
    with op.batch_alter_table("tasks", recreate="always") as batch_op:
        batch_op.drop_index("uq_tasks_recurrence_occurrence")
        batch_op.drop_index("ix_tasks_deadline_date_active")
        batch_op.drop_constraint("ck_tasks_recurrence_pair", type_="check")
        batch_op.drop_constraint("ck_tasks_deadline_state", type_="check")
        batch_op.drop_constraint(
            "fk_tasks_recurrence_rule_id_recurrence_rules", type_="foreignkey"
        )
        batch_op.drop_column("recurrence_occurrence_date")
        batch_op.drop_column("recurrence_rule_id")
        batch_op.drop_column("deadline_timezone")
        batch_op.drop_column("deadline_at_utc")
        batch_op.drop_column("deadline_date")
    _restore_task_tags()

    op.drop_index("ix_recurrence_rules_stopped", table_name="recurrence_rules")
    op.drop_table("recurrence_rules")
