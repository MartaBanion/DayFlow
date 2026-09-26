"""Add V0.2 task organization fields and relationships.

Revision ID: 0002_add_priority_categories_tags
Revises: 0001_create_tasks
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0002_add_priority_categories_tags"
down_revision: Union[str, Sequence[str], None] = "0001_create_tasks"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "categories",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=100, collation="NOCASE"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_categories_name"),
    )
    op.create_table(
        "tags",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=50, collation="NOCASE"), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("name", name="uq_tags_name"),
    )

    with op.batch_alter_table("tasks", recreate="always") as batch_op:
        batch_op.add_column(
            sa.Column(
                "priority",
                sa.String(length=20),
                server_default="normal",
                nullable=False,
            )
        )
        batch_op.add_column(sa.Column("category_id", sa.String(length=36), nullable=True))
        batch_op.create_check_constraint(
            "ck_tasks_priority",
            "priority IN ('low', 'normal', 'high')",
        )
        batch_op.create_foreign_key(
            "fk_tasks_category_id_categories",
            "categories",
            ["category_id"],
            ["id"],
            ondelete="SET NULL",
        )

    op.create_index(
        "ix_tasks_category_deleted",
        "tasks",
        ["category_id", "deleted_at_utc"],
        unique=False,
    )
    op.create_table(
        "task_tags",
        sa.Column("task_id", sa.String(length=36), nullable=False),
        sa.Column("tag_id", sa.String(length=36), nullable=False),
        sa.ForeignKeyConstraint(
            ["tag_id"], ["tags.id"], name="fk_task_tags_tag_id_tags", ondelete="CASCADE"
        ),
        sa.ForeignKeyConstraint(
            ["task_id"], ["tasks.id"], name="fk_task_tags_task_id_tasks", ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("task_id", "tag_id"),
    )
    op.create_index("ix_task_tags_tag_id", "task_tags", ["tag_id"], unique=False)


def downgrade() -> None:
    op.drop_index("ix_task_tags_tag_id", table_name="task_tags")
    op.drop_table("task_tags")
    op.drop_index("ix_tasks_category_deleted", table_name="tasks")

    with op.batch_alter_table("tasks", recreate="always") as batch_op:
        batch_op.drop_constraint("fk_tasks_category_id_categories", type_="foreignkey")
        batch_op.drop_constraint("ck_tasks_priority", type_="check")
        batch_op.drop_column("category_id")
        batch_op.drop_column("priority")

    op.drop_table("tags")
    op.drop_table("categories")
