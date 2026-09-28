"""Add V0.4 Projects and Task project relationships.

Revision ID: 0004_add_projects
Revises: 0003_add_task_schedule
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "0004_add_projects"
down_revision: Union[str, Sequence[str], None] = "0003_add_task_schedule"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_TASK_TAGS_BACKUP_TABLE = "_dayflow_task_tags_backup_0004"


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
        "projects",
        sa.Column("id", sa.String(length=36), nullable=False),
        sa.Column("name", sa.String(length=200, collation="NOCASE"), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "status",
            sa.String(length=20),
            nullable=False,
            server_default="active",
        ),
        sa.Column("created_at_utc", sa.String(length=32), nullable=False),
        sa.Column("updated_at_utc", sa.String(length=32), nullable=False),
        sa.Column("completed_at_utc", sa.String(length=32), nullable=True),
        sa.Column("deleted_at_utc", sa.String(length=32), nullable=True),
        sa.Column("version", sa.Integer(), nullable=False, server_default="1"),
        sa.CheckConstraint(
            "status IN ('active', 'completed')",
            name="ck_projects_status",
        ),
        sa.CheckConstraint("version >= 1", name="ck_projects_version_positive"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_projects_active_name",
        "projects",
        ["name"],
        unique=True,
        sqlite_where=sa.text("deleted_at_utc IS NULL"),
    )
    op.create_index(
        "ix_projects_deleted_status",
        "projects",
        ["deleted_at_utc", "status"],
    )

    _backup_task_tags()
    with op.batch_alter_table("tasks", recreate="always") as batch_op:
        batch_op.add_column(sa.Column("project_id", sa.String(length=36), nullable=True))
        batch_op.create_foreign_key(
            "fk_tasks_project_id_projects",
            "projects",
            ["project_id"],
            ["id"],
            ondelete="SET NULL",
        )
        batch_op.create_index(
            "ix_tasks_project_deleted",
            ["project_id", "deleted_at_utc"],
        )
    _restore_task_tags()


def downgrade() -> None:
    connection = op.get_bind()
    project_count = connection.execute(
        sa.text("SELECT COUNT(*) FROM projects")
    ).scalar_one()
    assigned_count = connection.execute(
        sa.text("SELECT COUNT(*) FROM tasks WHERE project_id IS NOT NULL")
    ).scalar_one()
    if project_count or assigned_count:
        raise RuntimeError(
            "Cannot downgrade 0004_add_projects while project data or relationships exist"
        )

    _backup_task_tags()
    with op.batch_alter_table("tasks", recreate="always") as batch_op:
        batch_op.drop_index("ix_tasks_project_deleted")
        batch_op.drop_constraint("fk_tasks_project_id_projects", type_="foreignkey")
        batch_op.drop_column("project_id")
    _restore_task_tags()

    op.drop_index("ix_projects_deleted_status", table_name="projects")
    op.drop_index("uq_projects_active_name", table_name="projects")
    op.drop_table("projects")
