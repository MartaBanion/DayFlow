from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

from app.core.config import get_settings
from app.models.category import Category
from app.models.project import Project
from app.models.tag import Tag
from app.models.task import Task, TaskStatus

UTC = timezone.utc
FIXED_NOW = datetime(2026, 10, 20, 12, 0, tzinfo=UTC)


def insert_task(
    session: Session,
    title: str,
    *,
    status: str = TaskStatus.PENDING.value,
    planned_date: date | None = None,
    created_at_utc: datetime | None = None,
    completed_at_utc: datetime | None = None,
    deadline_date: date | None = None,
    deadline_at_utc: datetime | None = None,
    deadline_timezone: str | None = None,
    deleted_at_utc: datetime | None = None,
    priority: str = "normal",
    project: Project | None = None,
    category: Category | None = None,
    tags: list[Tag] | None = None,
) -> Task:
    created_at_utc = created_at_utc or FIXED_NOW
    task = Task(
        id=str(uuid4()),
        title=title,
        status=status,
        planned_date=planned_date,
        priority=priority,
        deadline_date=deadline_date,
        deadline_at_utc=deadline_at_utc,
        deadline_timezone=deadline_timezone,
        completed_at_utc=completed_at_utc,
        deleted_at_utc=deleted_at_utc,
        created_at_utc=created_at_utc,
        updated_at_utc=created_at_utc,
        project=project,
        category=category,
        tags=tags or [],
    )
    session.add(task)
    session.flush()
    return task


def set_task_timezone(monkeypatch: pytest.MonkeyPatch, timezone_name: str) -> None:
    settings = get_settings().model_copy(update={"timezone": timezone_name})
    monkeypatch.setattr("app.services.task_service.get_settings", lambda: settings)


def set_task_clock(monkeypatch: pytest.MonkeyPatch, value: datetime = FIXED_NOW) -> None:
    monkeypatch.setattr("app.api.routes.tasks.utc_now", lambda: value)


def task_titles(response) -> list[str]:
    assert response.status_code == 200, response.text
    return [task["title"] for task in response.json()]


def test_legacy_list_defaults_and_parameters_remain_compatible(
    client: TestClient,
    session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    with session_factory() as session:
        planned = insert_task(
            session,
            "planned pending",
            planned_date=date(2026, 10, 20),
            created_at_utc=FIXED_NOW,
        )
        unplanned = insert_task(
            session,
            "unplanned pending",
            created_at_utc=FIXED_NOW + timedelta(minutes=1),
        )
        completed = insert_task(
            session,
            "completed planned",
            status=TaskStatus.COMPLETED.value,
            planned_date=date(2026, 10, 20),
            completed_at_utc=FIXED_NOW,
            created_at_utc=FIXED_NOW + timedelta(minutes=2),
        )
        deleted = insert_task(
            session,
            "deleted",
            planned_date=date(2026, 10, 20),
            deleted_at_utc=FIXED_NOW,
            created_at_utc=FIXED_NOW + timedelta(minutes=3),
        )
        session.commit()

    set_task_clock(monkeypatch, FIXED_NOW)
    response = client.get("/api/v1/tasks")
    assert task_titles(response) == [planned.title, unplanned.title, completed.title]
    assert deleted.title not in task_titles(response)

    assert task_titles(client.get("/api/v1/tasks?planned_date=2026-10-20")) == [
        planned.title,
        completed.title,
    ]
    assert task_titles(client.get("/api/v1/tasks?inbox=true")) == [unplanned.title]


@pytest.mark.parametrize(
    "parameter",
    [
        "status=invalid",
        "planned_bucket=invalid",
        "sort=invalid",
    ],
)
def test_invalid_query_enums_use_existing_validation_envelope(
    client: TestClient, parameter: str
) -> None:
    response = client.get(f"/api/v1/tasks?{parameter}")
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_status_filter_and_soft_delete(client: TestClient, session_factory: sessionmaker[Session]) -> None:
    with session_factory() as session:
        pending = insert_task(session, "pending")
        completed = insert_task(
            session,
            "completed",
            status=TaskStatus.COMPLETED.value,
            completed_at_utc=FIXED_NOW,
        )
        insert_task(session, "deleted", deleted_at_utc=FIXED_NOW)
        session.commit()

    assert task_titles(client.get("/api/v1/tasks?status=pending")) == [pending.title]
    assert task_titles(client.get("/api/v1/tasks?status=completed")) == [completed.title]
    assert set(task_titles(client.get("/api/v1/tasks?status=all"))) == {
        pending.title,
        completed.title,
    }


def test_inbox_and_unscheduled_have_distinct_and_semantics(
    client: TestClient,
    session_factory: sessionmaker[Session],
) -> None:
    with session_factory() as session:
        pending_unscheduled = insert_task(session, "pending unscheduled")
        completed_unscheduled = insert_task(
            session,
            "completed unscheduled",
            status=TaskStatus.COMPLETED.value,
            completed_at_utc=FIXED_NOW,
        )
        pending_today = insert_task(
            session, "pending today", planned_date=date(2026, 10, 20)
        )
        session.commit()

    assert set(
        task_titles(client.get("/api/v1/tasks?planned_bucket=unscheduled&status=all"))
    ) == {pending_unscheduled.title, completed_unscheduled.title}
    assert task_titles(client.get("/api/v1/tasks?inbox=true")) == [
        pending_unscheduled.title
    ]
    assert task_titles(client.get("/api/v1/tasks?inbox=true&status=completed")) == []
    assert task_titles(client.get("/api/v1/tasks?inbox=true&planned_bucket=today")) == []
    assert pending_today.title not in task_titles(
        client.get("/api/v1/tasks?planned_bucket=unscheduled")
    )


def test_planned_buckets_use_configured_timezone(
    client: TestClient,
    session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_task_clock(monkeypatch, datetime(2026, 10, 20, 6, 30, tzinfo=UTC))
    set_task_timezone(monkeypatch, "America/Los_Angeles")
    with session_factory() as session:
        past = insert_task(session, "past", planned_date=date(2026, 10, 18))
        today = insert_task(session, "today", planned_date=date(2026, 10, 19))
        future = insert_task(session, "future", planned_date=date(2026, 10, 20))
        session.commit()

    assert task_titles(client.get("/api/v1/tasks?planned_bucket=today")) == [today.title]
    assert task_titles(client.get("/api/v1/tasks?planned_bucket=past")) == [past.title]
    assert task_titles(client.get("/api/v1/tasks?planned_bucket=future")) == [future.title]


def test_invalid_dayflow_timezone_fails_closed(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_task_clock(monkeypatch)
    set_task_timezone(monkeypatch, "Not/A-Timezone")

    response = client.get("/api/v1/tasks?planned_bucket=today")

    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "code": "task_query_configuration_error",
            "message": "Task query timezone configuration is invalid",
        }
    }


def test_overdue_uses_canonical_deadline_semantics_and_filter_clock(
    client: TestClient,
    session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_task_clock(monkeypatch)
    set_task_timezone(monkeypatch, "UTC")
    with session_factory() as session:
        timed_exact = insert_task(
            session,
            "timed exact",
            deadline_date=date(2026, 10, 20),
            deadline_at_utc=FIXED_NOW,
            deadline_timezone="America/Los_Angeles",
        )
        date_only_old = insert_task(
            session,
            "date old",
            deadline_date=date(2026, 10, 19),
            deadline_timezone="Asia/Tokyo",
        )
        date_only_same = insert_task(
            session,
            "date same",
            deadline_date=date(2026, 10, 20),
            deadline_timezone="America/Los_Angeles",
        )
        future = insert_task(
            session,
            "timed future",
            deadline_date=date(2026, 10, 20),
            deadline_at_utc=FIXED_NOW + timedelta(seconds=1),
            deadline_timezone="UTC",
        )
        insert_task(
            session,
            "completed old deadline",
            status=TaskStatus.COMPLETED.value,
            completed_at_utc=FIXED_NOW,
            deadline_date=date(2026, 10, 1),
            deadline_timezone="UTC",
        )
        insert_task(
            session,
            "deleted old deadline",
            deadline_date=date(2026, 10, 1),
            deadline_timezone="UTC",
            deleted_at_utc=FIXED_NOW,
        )
        session.commit()

    response = client.get("/api/v1/tasks?overdue=true")
    assert set(task_titles(response)) == {timed_exact.title, date_only_old.title}
    assert all(task["deadline_status"] == "overdue" for task in response.json())
    assert task_titles(client.get("/api/v1/tasks?status=completed&overdue=true")) == []
    assert future.title not in task_titles(client.get("/api/v1/tasks?overdue=true"))


def test_task_read_uses_the_same_clock_as_overdue_filter(
    client: TestClient,
    session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_task_clock(monkeypatch)
    monkeypatch.setattr(
        "app.services.task_service.utc_now",
        lambda: pytest.fail("TaskService generated a second request clock"),
    )
    with session_factory() as session:
        insert_task(
            session,
            "clock-consistent",
            deadline_date=date(2026, 10, 20),
            deadline_at_utc=FIXED_NOW,
            deadline_timezone="UTC",
        )
        session.commit()

    response = client.get("/api/v1/tasks?overdue=true")
    assert task_titles(response) == ["clock-consistent"]
    assert response.json()[0]["deadline_status"] == "overdue"


def test_filter_combinations_use_and_semantics(
    client: TestClient,
    session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_task_clock(monkeypatch)
    with session_factory() as session:
        project = Project(id=str(uuid4()), name="Project A")
        category = Category(id=str(uuid4()), name="Category A")
        tag = Tag(id=str(uuid4()), name="Tag A")
        session.add_all([project, category, tag])
        session.flush()
        matching = insert_task(
            session,
            "matching",
            priority="high",
            project=project,
            category=category,
            tags=[tag],
            planned_date=date(2026, 10, 19),
        )
        other_priority = insert_task(
            session,
            "other priority",
            priority="normal",
            project=project,
            category=category,
            tags=[tag],
            planned_date=date(2026, 10, 19),
        )
        other_project = insert_task(
            session,
            "other project",
            priority="high",
            planned_date=date(2026, 10, 19),
        )
        session.commit()

    params = (
        f"project_id={project.id}&priority=high&category_id={category.id}"
        f"&tag_id={tag.id}&status=pending&planned_bucket=past"
    )
    assert task_titles(client.get(f"/api/v1/tasks?{params}")) == [matching.title]
    assert other_priority.title not in task_titles(client.get(f"/api/v1/tasks?{params}"))
    assert other_project.title not in task_titles(client.get(f"/api/v1/tasks?{params}"))


def test_sorts_have_frozen_null_order_and_stable_ties(
    client: TestClient,
    session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    set_task_clock(monkeypatch)
    with session_factory() as session:
        planned_late = insert_task(
            session,
            "planned late",
            planned_date=date(2026, 10, 22),
            created_at_utc=FIXED_NOW,
        )
        planned_early = insert_task(
            session,
            "planned early",
            planned_date=date(2026, 10, 21),
            created_at_utc=FIXED_NOW + timedelta(minutes=1),
        )
        planned_same_date = insert_task(
            session,
            "planned same date",
            planned_date=date(2026, 10, 21),
            created_at_utc=FIXED_NOW + timedelta(minutes=8),
        )
        unscheduled = insert_task(
            session,
            "unscheduled",
            created_at_utc=FIXED_NOW + timedelta(minutes=2),
        )
        date_only = insert_task(
            session,
            "date-only deadline",
            deadline_date=date(2026, 10, 23),
            deadline_timezone="UTC",
            created_at_utc=FIXED_NOW + timedelta(minutes=3),
        )
        timed_late = insert_task(
            session,
            "timed late deadline",
            deadline_date=date(2026, 10, 23),
            deadline_at_utc=FIXED_NOW + timedelta(hours=2),
            deadline_timezone="UTC",
            created_at_utc=FIXED_NOW + timedelta(minutes=4),
        )
        timed_early = insert_task(
            session,
            "timed early deadline",
            deadline_date=date(2026, 10, 23),
            deadline_at_utc=FIXED_NOW + timedelta(hours=1),
            deadline_timezone="UTC",
            created_at_utc=FIXED_NOW + timedelta(minutes=5),
        )
        timed_early_tie = insert_task(
            session,
            "timed early deadline tie",
            deadline_date=date(2026, 10, 23),
            deadline_at_utc=FIXED_NOW + timedelta(hours=1),
            deadline_timezone="UTC",
            created_at_utc=FIXED_NOW + timedelta(minutes=9),
        )
        completed_old = insert_task(
            session,
            "completed old",
            status=TaskStatus.COMPLETED.value,
            completed_at_utc=FIXED_NOW - timedelta(days=1),
            created_at_utc=FIXED_NOW + timedelta(minutes=6),
        )
        completed_new = insert_task(
            session,
            "completed new",
            status=TaskStatus.COMPLETED.value,
            completed_at_utc=FIXED_NOW,
            created_at_utc=FIXED_NOW + timedelta(minutes=7),
        )
        completed_new_tie = insert_task(
            session,
            "completed new tie",
            status=TaskStatus.COMPLETED.value,
            completed_at_utc=FIXED_NOW,
            created_at_utc=FIXED_NOW + timedelta(minutes=10),
        )
        session.commit()

    assert task_titles(client.get("/api/v1/tasks?sort=planned")) == [
        planned_early.title,
        planned_same_date.title,
        planned_late.title,
        unscheduled.title,
        date_only.title,
        timed_late.title,
        timed_early.title,
        completed_old.title,
        completed_new.title,
        timed_early_tie.title,
        completed_new_tie.title,
    ]
    assert task_titles(client.get("/api/v1/tasks?sort=deadline")) == [
        timed_early.title,
        timed_early_tie.title,
        timed_late.title,
        date_only.title,
        planned_late.title,
        planned_early.title,
        unscheduled.title,
        completed_old.title,
        completed_new.title,
        planned_same_date.title,
        completed_new_tie.title,
    ]
    assert task_titles(client.get("/api/v1/tasks?sort=completed")) == [
        completed_new.title,
        completed_new_tie.title,
        completed_old.title,
        planned_late.title,
        planned_early.title,
        unscheduled.title,
        date_only.title,
        timed_late.title,
        timed_early.title,
        planned_same_date.title,
        timed_early_tie.title,
    ]
    assert task_titles(client.get("/api/v1/tasks?status=pending&sort=completed")) == [
        planned_late.title,
        planned_early.title,
        unscheduled.title,
        date_only.title,
        timed_late.title,
        timed_early.title,
        planned_same_date.title,
        timed_early_tie.title,
    ]


def test_task_list_is_read_only_and_query_shape_is_bounded(
    client: TestClient,
    session_factory: sessionmaker[Session],
    database_engine: Engine,
) -> None:
    with session_factory() as session:
        project = Project(id=str(uuid4()), name="Scale project")
        session.add(project)
        session.flush()
        for index in range(150):
            insert_task(
                session,
                f"task-{index}",
                planned_date=date(2026, 10, 19),
                project=project if index % 3 == 0 else None,
            )
        session.commit()

    with session_factory() as session:
        before = session.execute(
            select(Task.id, Task.status, Task.version, Task.updated_at_utc, Task.completed_at_utc)
            .order_by(Task.id)
        ).all()

    select_count = 0

    def count_selects(_conn, _cursor, statement, _parameters, _context, _executemany):
        nonlocal select_count
        if statement.lstrip().upper().startswith("SELECT"):
            select_count += 1

    event.listen(database_engine, "before_cursor_execute", count_selects)
    try:
        response = client.get("/api/v1/tasks?status=pending&planned_bucket=past&sort=planned")
        assert response.status_code == 200, response.text
    finally:
        event.remove(database_engine, "before_cursor_execute", count_selects)

    assert select_count <= 8
    with session_factory() as session:
        after = session.execute(
            select(Task.id, Task.status, Task.version, Task.updated_at_utc, Task.completed_at_utc)
            .order_by(Task.id)
        ).all()
    assert before == after
