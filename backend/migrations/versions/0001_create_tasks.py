"""Create the V0.1 tasks table.

Revision ID: 0001_create_tasks
Revises:
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0001_create_tasks"
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "tasks",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("title", sa.String(length=500), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(length=20), server_default="pending", nullable=False),
        sa.Column("planned_date", sa.Date(), nullable=True),
        sa.Column("created_at_utc", sa.String(length=32), nullable=False),
        sa.Column("updated_at_utc", sa.String(length=32), nullable=False),
        sa.Column("completed_at_utc", sa.String(length=32), nullable=True),
        sa.Column("deleted_at_utc", sa.String(length=32), nullable=True),
        sa.Column("version", sa.Integer(), server_default="1", nullable=False),
        sa.CheckConstraint(
            "status IN ('pending', 'completed')", name="ck_tasks_status"
        ),
        sa.CheckConstraint("version >= 1", name="ck_tasks_version_positive"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_tasks_planned_date_deleted",
        "tasks",
        ["planned_date", "deleted_at_utc"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index("ix_tasks_planned_date_deleted", table_name="tasks")
    op.drop_table("tasks")
