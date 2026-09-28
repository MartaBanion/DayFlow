from __future__ import annotations

from dataclasses import dataclass
import logging

from sqlalchemy import case, func, select
from sqlalchemy.exc import IntegrityError, SQLAlchemyError
from sqlalchemy.orm import Session
from sqlalchemy.orm.exc import StaleDataError

from app.core.errors import (
    ProjectNameConflictError,
    ProjectNotFoundError,
    ProjectVersionConflictError,
)
from app.core.time import utc_now
from app.models.project import Project, ProjectStatus
from app.models.task import Task, TaskStatus
from app.schemas.project import ProjectCreate, ProjectStatusValue, ProjectUpdate

logger = logging.getLogger("dayflow.project")


@dataclass(frozen=True)
class ProjectView:
    project: Project
    task_count: int
    completed_task_count: int

    @property
    def progress_percent(self) -> int:
        if self.task_count == 0:
            return 0
        return int(self.completed_task_count * 100 / self.task_count)


class ProjectService:
    def list(
        self,
        session: Session,
        status: ProjectStatusValue | None = None,
        *,
        include_deleted: bool = False,
    ) -> list[ProjectView]:
        statement = select(Project)
        if not include_deleted:
            statement = statement.where(Project.deleted_at_utc.is_(None))
        if status is not None:
            statement = statement.where(Project.status == status.value)
        projects = list(
            session.scalars(
                statement.order_by(Project.updated_at_utc.desc(), Project.name)
            ).all()
        )
        return self._with_stats(session, projects)

    def get(self, session: Session, project_id: str) -> ProjectView:
        project = self._get_active(session, project_id)
        return self._with_stats(session, [project])[0]

    def create(self, session: Session, payload: ProjectCreate) -> ProjectView:
        name = payload.name.strip()
        try:
            self._ensure_name_available(session, name)
            project = Project(name=name, description=payload.description)
            session.add(project)
            self._commit(session, "create project")
            session.refresh(project)
            return ProjectView(project, 0, 0)
        except IntegrityError:
            session.rollback()
            raise ProjectNameConflictError(name)
        except Exception:
            session.rollback()
            raise

    def update(
        self,
        session: Session,
        project_id: str,
        expected_version: int,
        payload: ProjectUpdate,
    ) -> ProjectView:
        try:
            project = self._get_active(session, project_id)
            self._check_version(project, expected_version)
            changes = payload.model_dump(exclude_unset=True)
            if not changes:
                return self._with_stats(session, [project])[0]

            changed = False
            if "name" in changes:
                name = changes["name"].strip()
                if project.name != name:
                    self._ensure_name_available(session, name, excluding=project.id)
                    project.name = name
                    changed = True
            if "description" in changes and project.description != changes["description"]:
                project.description = changes["description"]
                changed = True

            if not changed:
                return self._with_stats(session, [project])[0]

            self._touch(project)
            self._commit(session, "update project", (project.id, expected_version))
            session.refresh(project)
            return self._with_stats(session, [project])[0]
        except IntegrityError:
            session.rollback()
            name = changes.get("name", project.name).strip()
            raise ProjectNameConflictError(name)
        except Exception:
            session.rollback()
            raise

    def complete(
        self, session: Session, project_id: str, expected_version: int
    ) -> ProjectView:
        try:
            project = self._get_active(session, project_id)
            self._check_version(project, expected_version)
            if project.status == ProjectStatus.COMPLETED.value:
                return self._with_stats(session, [project])[0]
            project.status = ProjectStatus.COMPLETED.value
            project.completed_at_utc = utc_now()
            self._touch(project)
            self._commit(session, "complete project", (project.id, expected_version))
            session.refresh(project)
            return self._with_stats(session, [project])[0]
        except Exception:
            session.rollback()
            raise

    def reopen(
        self, session: Session, project_id: str, expected_version: int
    ) -> ProjectView:
        try:
            project = self._get_active(session, project_id)
            self._check_version(project, expected_version)
            if project.status == ProjectStatus.ACTIVE.value:
                return self._with_stats(session, [project])[0]
            project.status = ProjectStatus.ACTIVE.value
            project.completed_at_utc = None
            self._touch(project)
            self._commit(session, "reopen project", (project.id, expected_version))
            session.refresh(project)
            return self._with_stats(session, [project])[0]
        except Exception:
            session.rollback()
            raise

    def soft_delete(
        self, session: Session, project_id: str, expected_version: int
    ) -> None:
        try:
            project = self._get_active(session, project_id)
            self._check_version(project, expected_version)
            tasks = list(
                session.scalars(select(Task).where(Task.project_id == project.id)).all()
            )
            for task in tasks:
                task.project_id = None
                self._touch_task(task)
            project.deleted_at_utc = utc_now()
            self._touch(project)
            self._commit(session, "delete project", (project.id, expected_version))
        except Exception:
            session.rollback()
            raise

    def restore(
        self, session: Session, project_id: str, expected_version: int
    ) -> ProjectView:
        try:
            project = session.scalar(
                select(Project).where(
                    Project.id == project_id,
                    Project.deleted_at_utc.is_not(None),
                )
            )
            if project is None:
                raise ProjectNotFoundError(project_id)
            self._check_version(project, expected_version)
            self._ensure_name_available(session, project.name, excluding=project.id)
            project.deleted_at_utc = None
            self._touch(project)
            self._commit(session, "restore project", (project.id, expected_version))
            session.refresh(project)
            return self._with_stats(session, [project])[0]
        except IntegrityError:
            session.rollback()
            raise ProjectNameConflictError(project.name)
        except Exception:
            session.rollback()
            raise

    @staticmethod
    def _get_active(session: Session, project_id: str) -> Project:
        project = session.scalar(
            select(Project).where(
                Project.id == project_id,
                Project.deleted_at_utc.is_(None),
            )
        )
        if project is None:
            raise ProjectNotFoundError(project_id)
        return project

    @staticmethod
    def _with_stats(session: Session, projects: list[Project]) -> list[ProjectView]:
        if not projects:
            return []
        project_ids = [project.id for project in projects]
        rows = session.execute(
            select(
                Task.project_id,
                func.count(Task.id).label("task_count"),
                func.sum(
                    case(
                        (Task.status == TaskStatus.COMPLETED.value, 1),
                        else_=0,
                    )
                ).label("completed_task_count"),
            )
            .where(
                Task.project_id.in_(project_ids),
                Task.deleted_at_utc.is_(None),
            )
            .group_by(Task.project_id)
        ).all()
        counts = {
            row.project_id: (int(row.task_count), int(row.completed_task_count or 0))
            for row in rows
        }
        return [
            ProjectView(project, *counts.get(project.id, (0, 0)))
            for project in projects
        ]

    @staticmethod
    def _ensure_name_available(
        session: Session,
        name: str,
        excluding: str | None = None,
    ) -> None:
        statement = select(Project).where(
            Project.deleted_at_utc.is_(None),
            func.lower(Project.name) == name.lower(),
        )
        if excluding is not None:
            statement = statement.where(Project.id != excluding)
        if session.scalar(statement) is not None:
            raise ProjectNameConflictError(name)

    @staticmethod
    def _check_version(project: Project, expected_version: int) -> None:
        if project.version != expected_version:
            raise ProjectVersionConflictError(
                project.id, expected_version, project.version
            )

    @staticmethod
    def _touch(project: Project) -> None:
        project.version += 1
        project.updated_at_utc = utc_now()

    @staticmethod
    def _touch_task(task: Task) -> None:
        task.version += 1
        task.updated_at_utc = utc_now()

    @staticmethod
    def _commit(
        session: Session,
        operation: str,
        conflict: tuple[str, int] | None = None,
    ) -> None:
        try:
            session.commit()
        except StaleDataError:
            session.rollback()
            if conflict is not None:
                project_id, expected_version = conflict
                actual_version = session.scalar(
                    select(Project.version).where(Project.id == project_id)
                )
                raise ProjectVersionConflictError(
                    project_id,
                    expected_version,
                    actual_version if actual_version is not None else -1,
                )
            logger.exception("Database transaction rolled back during %s", operation)
            raise
        except SQLAlchemyError:
            session.rollback()
            logger.exception("Database transaction rolled back during %s", operation)
            raise
