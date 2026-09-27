"""Add the V0.3 single-task time block fields.

Revision ID: 0003_add_task_schedule
Revises: 0002_add_priority_categories_tags
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0003_add_task_schedule"
down_revision: Union[str, Sequence[str], None] = "0002_add_priority_categories_tags"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("tasks", recreate="always") as batch_op:
        batch_op.add_column(sa.Column("start_at_utc", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("end_at_utc", sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column("schedule_timezone", sa.String(length=64), nullable=True))
        batch_op.create_check_constraint(
            "ck_tasks_schedule_complete",
            "(start_at_utc IS NULL AND end_at_utc IS NULL AND schedule_timezone IS NULL) "
            "OR (start_at_utc IS NOT NULL AND end_at_utc IS NOT NULL AND schedule_timezone IS NOT NULL)",
        )
        batch_op.create_check_constraint(
            "ck_tasks_schedule_requires_date",
            "start_at_utc IS NULL OR planned_date IS NOT NULL",
        )


def downgrade() -> None:
    connection = op.get_bind()
    scheduled_count = connection.execute(
        sa.text(
            "SELECT COUNT(*) FROM tasks "
            "WHERE start_at_utc IS NOT NULL "
            "OR end_at_utc IS NOT NULL "
            "OR schedule_timezone IS NOT NULL"
        )
    ).scalar_one()
    if scheduled_count:
        raise RuntimeError(
            "Cannot downgrade 0003_add_task_schedule while scheduled tasks exist"
        )

    with op.batch_alter_table("tasks", recreate="always") as batch_op:
        batch_op.drop_constraint("ck_tasks_schedule_requires_date", type_="check")
        batch_op.drop_constraint("ck_tasks_schedule_complete", type_="check")
        batch_op.drop_column("schedule_timezone")
        batch_op.drop_column("end_at_utc")
        batch_op.drop_column("start_at_utc")
