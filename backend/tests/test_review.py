from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime, timedelta, timezone
from hashlib import sha256
from pathlib import Path
from uuid import uuid4

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import event, select
from sqlalchemy.engine import Engine
from sqlalchemy.orm import Session, sessionmaker

import app.api.routes.review as review_route
import app.services.review_service as review_service_module
from app.core.config import get_settings
from app.models.project import Project
from app.models.recurrence import RecurrenceRule
from app.models.reminder import Reminder
from app.models.task import Task
from app.services.recurrence_service import RecurrenceService

UTC = timezone.utc


def _set_review_context(
    monkeypatch: pytest.MonkeyPatch,
    generated_at_utc: datetime | Callable[[], datetime],
    timezone_name: str = "UTC",
) -> None:
    clock = (
        generated_at_utc
        if callable(generated_at_utc)
        else lambda: generated_at_utc
    )
    monkeypatch.setattr(review_service_module, "utc_now", clock)
    settings = get_settings().model_copy(update={"timezone": timezone_name})
    monkeypatch.setattr(review_route, "get_settings", lambda: settings)


def _add_task(
    session_factory: sessionmaker[Session],
    *,
    title: str,
    task_id: str | None = None,
    status: str = "pending",
    planned_date: date | None = None,
    project_id: str | None = None,
    completed_at_utc: datetime | None = None,
    deleted_at_utc: datetime | None = None,
    created_at_utc: datetime | None = None,
    updated_at_utc: datetime | None = None,
    deadline_date: date | None = None,
    deadline_at_utc: datetime | None = None,
    deadline_timezone: str | None = None,
    recurrence_rule_id: str | None = None,
    recurrence_occurrence_date: date | None = None,
) -> str:
    task = Task(
        id=task_id or str(uuid4()),
        title=title,
        status=status,
        planned_date=planned_date,
        project_id=project_id,
        completed_at_utc=completed_at_utc,
        deleted_at_utc=deleted_at_utc,
        created_at_utc=created_at_utc or datetime(2026, 1, 1, tzinfo=UTC),
        updated_at_utc=updated_at_utc or datetime(2026, 1, 1, tzinfo=UTC),
        deadline_date=deadline_date,
        deadline_at_utc=deadline_at_utc,
        deadline_timezone=deadline_timezone,
        recurrence_rule_id=recurrence_rule_id,
        recurrence_occurrence_date=recurrence_occurrence_date,
    )
    with session_factory() as session:
        session.add(task)
        session.commit()
    return task.id


def _add_project(
    session_factory: sessionmaker[Session],
    name: str,
    *,
    status: str = "active",
    deleted_at_utc: datetime | None = None,
) -> str:
    project = Project(
        id=str(uuid4()),
        name=name,
        status=status,
        deleted_at_utc=deleted_at_utc,
    )
    with session_factory() as session:
        session.add(project)
        session.commit()
    return project.id


def _review(client: TestClient, scope: str = "today") -> dict:
    response = client.get(f"/api/v1/review?scope={scope}")
    assert response.status_code == 200, response.text
    return response.json()


def _section_ids(body: dict, section: str) -> list[str]:
    return [task["id"] for task in body[section]["tasks"]]


def test_review_scopes_contract_and_invalid_scope(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixed = datetime(2026, 10, 3, 4, tzinfo=UTC)
    _set_review_context(monkeypatch, fixed, "Asia/Shanghai")

    today = _review(client, "today")
    assert today == {
        "scope": "today",
        "local_timezone": "Asia/Shanghai",
        "local_date": "2026-10-03",
        "range_start_utc": "2026-10-02T16:00:00.000000Z",
        "range_end_utc": "2026-10-03T16:00:00.000000Z",
        "generated_at_utc": "2026-10-03T04:00:00.000000Z",
        "completed": {"count": 0, "tasks": []},
        "overdue": {"count": 0, "tasks": []},
        "carryover": {"count": 0, "tasks": []},
        "projects": [],
    }

    week = _review(client, "week")
    assert week["range_start_utc"] == "2026-09-27T16:00:00.000000Z"
    assert week["range_end_utc"] == "2026-10-04T16:00:00.000000Z"
    assert week["scope"] == "week"

    invalid = client.get("/api/v1/review?scope=month")
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "validation_error"
    missing = client.get("/api/v1/review")
    assert missing.status_code == 422
    assert missing.json()["error"]["code"] == "validation_error"


def test_daily_completed_half_open_boundaries_and_stable_order(
    client: TestClient,
    session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixed = datetime(2026, 10, 3, 12, tzinfo=UTC)
    _set_review_context(monkeypatch, fixed)
    start = datetime(2026, 10, 3, tzinfo=UTC)
    end = datetime(2026, 10, 4, tzinfo=UTC)
    start_id = _add_task(
        session_factory,
        title="At start",
        status="completed",
        completed_at_utc=start,
    )
    before_end_id = _add_task(
        session_factory,
        title="Before end",
        status="completed",
        completed_at_utc=end - timedelta(microseconds=1),
    )
    _add_task(
        session_factory,
        title="At end",
        status="completed",
        completed_at_utc=end,
    )
    tie_ids = sorted([str(uuid4()), str(uuid4())])
    for task_id in reversed(tie_ids):
        _add_task(
            session_factory,
            title=f"Tie {task_id}",
            task_id=task_id,
            status="completed",
            completed_at_utc=datetime(2026, 10, 3, 8, tzinfo=UTC),
        )

    body = _review(client)
    assert _section_ids(body, "completed") == [
        before_end_id,
        *tie_ids,
        start_id,
    ]
    assert body["completed"]["count"] == len(body["completed"]["tasks"])


def test_weekly_completed_monday_boundaries(
    client: TestClient,
    session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_review_context(monkeypatch, datetime(2026, 10, 7, 12, tzinfo=UTC))
    monday = datetime(2026, 10, 5, tzinfo=UTC)
    next_monday = datetime(2026, 10, 12, tzinfo=UTC)
    included = _add_task(
        session_factory,
        title="Monday boundary",
        status="completed",
        completed_at_utc=monday,
    )
    _add_task(
        session_factory,
        title="Next Monday boundary",
        status="completed",
        completed_at_utc=next_monday,
    )

    body = _review(client, "week")
    assert body["range_start_utc"] == "2026-10-05T00:00:00.000000Z"
    assert body["range_end_utc"] == "2026-10-12T00:00:00.000000Z"
    assert _section_ids(body, "completed") == [included]


@pytest.mark.parametrize(
    ("timezone_name", "expected_start", "expected_end"),
    [
        (
            "Asia/Kathmandu",
            "2026-10-02T18:15:00.000000Z",
            "2026-10-03T18:15:00.000000Z",
        ),
        (
            "America/Los_Angeles",
            "2026-10-03T07:00:00.000000Z",
            "2026-10-04T07:00:00.000000Z",
        ),
    ],
)
def test_daily_range_supports_positive_and_negative_offsets(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    timezone_name: str,
    expected_start: str,
    expected_end: str,
) -> None:
    _set_review_context(
        monkeypatch,
        datetime(2026, 10, 3, 12, tzinfo=UTC),
        timezone_name,
    )
    body = _review(client)
    assert body["local_date"] == "2026-10-03"
    assert body["range_start_utc"] == expected_start
    assert body["range_end_utc"] == expected_end


@pytest.mark.parametrize(
    ("generated_at", "expected_start", "expected_end", "hours"),
    [
        (
            datetime(2026, 3, 8, 12, tzinfo=UTC),
            "2026-03-08T05:00:00.000000Z",
            "2026-03-09T04:00:00.000000Z",
            23,
        ),
        (
            datetime(2026, 11, 1, 12, tzinfo=UTC),
            "2026-11-01T04:00:00.000000Z",
            "2026-11-02T05:00:00.000000Z",
            25,
        ),
    ],
)
def test_daily_range_converts_dst_boundaries_independently(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    generated_at: datetime,
    expected_start: str,
    expected_end: str,
    hours: int,
) -> None:
    _set_review_context(monkeypatch, generated_at, "America/New_York")
    body = _review(client)
    assert body["range_start_utc"] == expected_start
    assert body["range_end_utc"] == expected_end
    start = datetime.fromisoformat(expected_start.replace("Z", "+00:00"))
    end = datetime.fromisoformat(expected_end.replace("Z", "+00:00"))
    assert end - start == timedelta(hours=hours)


def test_completed_uses_current_retained_state_not_updated_time(
    client: TestClient,
    session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixed = datetime(2026, 10, 3, 12, tzinfo=UTC)
    _set_review_context(monkeypatch, fixed)
    included = _add_task(
        session_factory,
        title="Latest completion",
        status="completed",
        completed_at_utc=datetime(2026, 10, 3, 10, tzinfo=UTC),
    )
    _add_task(
        session_factory,
        title="Reopened",
        status="pending",
        completed_at_utc=None,
        updated_at_utc=datetime(2026, 10, 3, 11, tzinfo=UTC),
    )
    _add_task(
        session_factory,
        title="Restore to pending",
        status="pending",
        completed_at_utc=None,
    )
    _add_task(
        session_factory,
        title="Pending with malformed completion",
        status="pending",
        completed_at_utc=datetime(2026, 10, 3, 9, tzinfo=UTC),
    )
    _add_task(
        session_factory,
        title="Soft deleted completion",
        status="completed",
        completed_at_utc=datetime(2026, 10, 3, 9, tzinfo=UTC),
        deleted_at_utc=datetime(2026, 10, 3, 10, tzinfo=UTC),
    )
    _add_task(
        session_factory,
        title="Missing completion timestamp",
        status="completed",
        completed_at_utc=None,
    )
    _add_task(
        session_factory,
        title="Updated today but completed yesterday",
        status="completed",
        completed_at_utc=datetime(2026, 10, 2, 23, 59, tzinfo=UTC),
        updated_at_utc=datetime(2026, 10, 3, 11, 30, tzinfo=UTC),
    )

    assert _section_ids(_review(client), "completed") == [included]


def test_timed_overdue_uses_exact_common_instant_and_excludes_inactive_tasks(
    client: TestClient,
    session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixed = datetime(2026, 10, 3, 12, tzinfo=UTC)
    _set_review_context(monkeypatch, fixed)
    before = _add_task(
        session_factory,
        title="Before current instant",
        deadline_date=date(2026, 10, 3),
        deadline_at_utc=fixed - timedelta(seconds=1),
        deadline_timezone="UTC",
    )
    exact = _add_task(
        session_factory,
        title="Exact current instant",
        deadline_date=date(2026, 10, 3),
        deadline_at_utc=fixed,
        deadline_timezone="UTC",
    )
    _add_task(
        session_factory,
        title="After current instant",
        deadline_date=date(2026, 10, 3),
        deadline_at_utc=fixed + timedelta(seconds=1),
        deadline_timezone="UTC",
    )
    _add_task(
        session_factory,
        title="Completed timed deadline",
        status="completed",
        completed_at_utc=fixed - timedelta(hours=1),
        deadline_date=date(2026, 10, 3),
        deadline_at_utc=fixed - timedelta(hours=2),
        deadline_timezone="UTC",
    )
    _add_task(
        session_factory,
        title="Deleted timed deadline",
        deleted_at_utc=fixed,
        deadline_date=date(2026, 10, 3),
        deadline_at_utc=fixed - timedelta(hours=2),
        deadline_timezone="UTC",
    )
    _add_task(session_factory, title="No deadline")

    body = _review(client)
    assert _section_ids(body, "overdue") == [before, exact]
    assert all(task["deadline_status"] == "overdue" for task in body["overdue"]["tasks"])
    assert body["overdue"]["count"] == 2


def test_date_only_overdue_uses_each_deadline_timezone_not_review_timezone(
    client: TestClient,
    session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixed = datetime(2026, 10, 2, 0, 30, tzinfo=UTC)
    _set_review_context(monkeypatch, fixed, "America/New_York")
    due_today_los_angeles = _add_task(
        session_factory,
        title="Still deadline day in Los Angeles",
        deadline_date=date(2026, 10, 1),
        deadline_timezone="America/Los_Angeles",
    )
    overdue_shanghai = _add_task(
        session_factory,
        title="Already next day in Shanghai",
        deadline_date=date(2026, 10, 1),
        deadline_timezone="Asia/Shanghai",
    )
    _add_task(
        session_factory,
        title="Future date-only deadline",
        deadline_date=date(2026, 10, 3),
        deadline_timezone="Asia/Shanghai",
    )

    body = _review(client)
    assert _section_ids(body, "overdue") == [overdue_shanghai]
    assert due_today_los_angeles not in _section_ids(body, "overdue")


def test_carryover_membership_order_and_overlap_with_overdue(
    client: TestClient,
    session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixed = datetime(2026, 10, 3, 12, tzinfo=UTC)
    _set_review_context(monkeypatch, fixed)
    oldest = _add_task(
        session_factory,
        title="Oldest carryover",
        planned_date=date(2026, 9, 30),
    )
    overlap = _add_task(
        session_factory,
        title="Overdue carryover",
        planned_date=date(2026, 10, 2),
        deadline_date=date(2026, 10, 1),
        deadline_timezone="UTC",
    )
    _add_task(
        session_factory,
        title="Planned today",
        planned_date=date(2026, 10, 3),
    )
    _add_task(
        session_factory,
        title="Planned future",
        planned_date=date(2026, 10, 4),
    )
    _add_task(
        session_factory,
        title="Completed old plan",
        status="completed",
        planned_date=date(2026, 10, 1),
        completed_at_utc=fixed,
    )
    _add_task(
        session_factory,
        title="Deleted old plan",
        planned_date=date(2026, 10, 1),
        deleted_at_utc=fixed,
    )
    deadline_only = _add_task(
        session_factory,
        title="Deadline only",
        deadline_date=date(2026, 10, 1),
        deadline_timezone="UTC",
    )

    body = _review(client)
    assert _section_ids(body, "carryover") == [oldest, overlap]
    assert overlap in _section_ids(body, "overdue")
    assert deadline_only in _section_ids(body, "overdue")
    assert deadline_only not in _section_ids(body, "carryover")
    assert body["carryover"]["count"] == len(body["carryover"]["tasks"])


def test_recurrence_occurrences_use_task_state_without_materialization(
    client: TestClient,
    session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixed = datetime(2026, 10, 3, 12, tzinfo=UTC)
    _set_review_context(monkeypatch, fixed)
    rule = RecurrenceRule(
        id=str(uuid4()),
        frequency="daily",
        starts_on=date(2026, 10, 1),
        timezone="UTC",
        stopped_at_utc=fixed,
    )
    with session_factory() as session:
        session.add(rule)
        session.commit()
    completed = _add_task(
        session_factory,
        title="Completed occurrence",
        status="completed",
        completed_at_utc=fixed - timedelta(hours=1),
        recurrence_rule_id=rule.id,
        recurrence_occurrence_date=date(2026, 10, 1),
    )
    _add_task(
        session_factory,
        title="Pending next occurrence",
        recurrence_rule_id=rule.id,
        recurrence_occurrence_date=date(2026, 10, 2),
    )
    _add_task(
        session_factory,
        title="Skipped occurrence",
        deleted_at_utc=fixed,
        recurrence_rule_id=rule.id,
        recurrence_occurrence_date=date(2026, 10, 3),
    )
    _add_task(
        session_factory,
        title="Deleted completed occurrence",
        status="completed",
        completed_at_utc=fixed - timedelta(hours=2),
        deleted_at_utc=fixed,
        recurrence_rule_id=rule.id,
        recurrence_occurrence_date=date(2026, 10, 4),
    )
    with session_factory() as session:
        before_count = len(session.scalars(select(Task)).all())

    monkeypatch.setattr(
        RecurrenceService,
        "materialize",
        lambda *args, **kwargs: pytest.fail("Review GET must not materialize"),
    )
    body = _review(client)
    assert _section_ids(body, "completed") == [completed]
    with session_factory() as session:
        assert len(session.scalars(select(Task)).all()) == before_count
        retained_rule = session.get(RecurrenceRule, rule.id)
        assert retained_rule is not None
        assert retained_rule.stopped_at_utc == fixed


def test_project_review_snapshot_counts_progress_latest_and_order(
    client: TestClient,
    session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixed = datetime(2026, 10, 3, 12, tzinfo=UTC)
    _set_review_context(monkeypatch, fixed)
    empty_id = _add_project(session_factory, "Empty")
    active_id = _add_project(session_factory, "Zulu Active")
    completed_project_id = _add_project(
        session_factory, "Alpha Completed", status="completed"
    )
    deleted_id = _add_project(
        session_factory,
        "Deleted",
        deleted_at_utc=fixed,
    )

    older = fixed - timedelta(days=30)
    latest = fixed - timedelta(days=20)
    _add_task(
        session_factory,
        title="Active completed older",
        status="completed",
        project_id=active_id,
        completed_at_utc=older,
    )
    _add_task(
        session_factory,
        title="Active completed latest",
        status="completed",
        project_id=active_id,
        completed_at_utc=latest,
    )
    _add_task(
        session_factory,
        title="Active pending overdue",
        project_id=active_id,
        deadline_date=date(2026, 10, 3),
        deadline_at_utc=fixed,
        deadline_timezone="UTC",
    )
    _add_task(
        session_factory,
        title="Active pending current",
        project_id=active_id,
    )
    _add_task(
        session_factory,
        title="Deleted project task",
        status="completed",
        project_id=active_id,
        completed_at_utc=fixed,
        deleted_at_utc=fixed,
    )
    _add_task(
        session_factory,
        title="Completed project pending date overdue",
        project_id=completed_project_id,
        deadline_date=date(2026, 10, 2),
        deadline_timezone="UTC",
    )
    _add_task(
        session_factory,
        title="Completed project completed task",
        status="completed",
        project_id=completed_project_id,
        completed_at_utc=fixed - timedelta(days=1),
    )

    projects = _review(client)["projects"]
    assert [project["id"] for project in projects] == [
        empty_id,
        active_id,
        completed_project_id,
    ]
    assert deleted_id not in {project["id"] for project in projects}
    by_id = {project["id"]: project for project in projects}
    assert by_id[empty_id] == {
        "id": empty_id,
        "name": "Empty",
        "status": "active",
        "task_count": 0,
        "completed_task_count": 0,
        "pending_task_count": 0,
        "overdue_task_count": 0,
        "progress_percent": 0,
        "latest_completed_at_utc": None,
    }
    assert by_id[active_id]["task_count"] == 4
    assert by_id[active_id]["completed_task_count"] == 2
    assert by_id[active_id]["pending_task_count"] == 2
    assert by_id[active_id]["overdue_task_count"] == 1
    assert by_id[active_id]["progress_percent"] == 50
    assert by_id[active_id]["latest_completed_at_utc"] == "2026-09-13T12:00:00.000000Z"
    assert by_id[completed_project_id]["status"] == "completed"
    assert by_id[completed_project_id]["task_count"] == 2
    assert by_id[completed_project_id]["completed_task_count"] == 1
    assert by_id[completed_project_id]["pending_task_count"] == 1
    assert by_id[completed_project_id]["overdue_task_count"] == 1
    assert by_id[completed_project_id]["progress_percent"] == 50


def test_project_progress_uses_existing_integer_floor_semantics(
    client: TestClient,
    session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixed = datetime(2026, 10, 3, 12, tzinfo=UTC)
    _set_review_context(monkeypatch, fixed)
    project_id = _add_project(session_factory, "One third")
    _add_task(
        session_factory,
        title="Done",
        status="completed",
        project_id=project_id,
        completed_at_utc=fixed,
    )
    _add_task(session_factory, title="Pending one", project_id=project_id)
    _add_task(session_factory, title="Pending two", project_id=project_id)

    project = _review(client)["projects"][0]
    assert project["progress_percent"] == 33


def test_request_captures_clock_once_for_all_sections(
    client: TestClient,
    session_factory: sessionmaker[Session],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixed = datetime(2026, 10, 3, 12, tzinfo=UTC)
    calls = 0

    def clock() -> datetime:
        nonlocal calls
        calls += 1
        if calls > 1:
            raise AssertionError("Review request clock called more than once")
        return fixed

    _set_review_context(monkeypatch, clock)
    due = _add_task(
        session_factory,
        title="Due at generated instant",
        planned_date=date(2026, 10, 2),
        deadline_date=date(2026, 10, 3),
        deadline_at_utc=fixed,
        deadline_timezone="UTC",
    )

    body = _review(client)
    assert calls == 1
    assert body["generated_at_utc"] == "2026-10-03T12:00:00.000000Z"
    assert due in _section_ids(body, "overdue")
    assert due in _section_ids(body, "carryover")


def test_invalid_configured_timezone_fails_closed(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _set_review_context(
        monkeypatch,
        datetime(2026, 10, 3, 12, tzinfo=UTC),
        "Not/A-Timezone",
    )
    response = client.get("/api/v1/review?scope=today")
    assert response.status_code == 500
    assert response.json() == {
        "error": {
            "code": "review_configuration_error",
            "message": "Review timezone configuration is invalid",
        }
    }


def _table_rows(
    session_factory: sessionmaker[Session], model: type
) -> list[tuple]:
    columns = tuple(model.__table__.columns)
    with session_factory() as session:
        return [
            tuple(row)
            for row in session.execute(
                select(*columns).order_by(model.id)
            ).all()
        ]


def test_review_get_is_select_only_and_preserves_all_business_state(
    client: TestClient,
    session_factory: sessionmaker[Session],
    database_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixed = datetime(2026, 10, 3, 12, tzinfo=UTC)
    _set_review_context(monkeypatch, fixed)
    project_id = _add_project(session_factory, "Read only project")
    rule = RecurrenceRule(
        id=str(uuid4()),
        frequency="daily",
        starts_on=date(2026, 10, 1),
        timezone="UTC",
    )
    with session_factory() as session:
        session.add(rule)
        session.commit()
    task_id = _add_task(
        session_factory,
        title="Read only occurrence",
        status="completed",
        project_id=project_id,
        completed_at_utc=fixed,
        recurrence_rule_id=rule.id,
        recurrence_occurrence_date=date(2026, 10, 1),
    )
    with session_factory() as session:
        session.add(
            Reminder(
                id=str(uuid4()),
                task_id=task_id,
                trigger_at_utc=fixed,
                reminder_timezone="UTC",
            )
        )
        session.commit()

    models = (Task, Project, RecurrenceRule, Reminder)
    before_rows = {model: _table_rows(session_factory, model) for model in models}
    database_path = Path(str(database_engine.url.database))
    before_sha = sha256(database_path.read_bytes()).hexdigest()
    statements: list[str] = []

    def capture_statement(
        _connection,
        _cursor,
        statement: str,
        _parameters,
        _context,
        _executemany,
    ) -> None:
        statements.append(statement.strip())

    monkeypatch.setattr(
        RecurrenceService,
        "materialize",
        lambda *args, **kwargs: pytest.fail("Review GET must not materialize"),
    )
    event.listen(database_engine, "before_cursor_execute", capture_statement)
    try:
        body = _review(client)
    finally:
        event.remove(database_engine, "before_cursor_execute", capture_statement)

    assert body["completed"]["count"] == 1
    assert statements
    assert all(statement.upper().startswith("SELECT") for statement in statements)
    assert {model: _table_rows(session_factory, model) for model in models} == before_rows
    assert sha256(database_path.read_bytes()).hexdigest() == before_sha


def _count_review_selects(client: TestClient, engine: Engine) -> int:
    statements: list[str] = []

    def capture(
        _connection,
        _cursor,
        statement: str,
        _parameters,
        _context,
        _executemany,
    ) -> None:
        if statement.lstrip().upper().startswith("SELECT"):
            statements.append(statement)

    event.listen(engine, "before_cursor_execute", capture)
    try:
        _review(client)
    finally:
        event.remove(engine, "before_cursor_execute", capture)
    return len(statements)


def test_project_query_count_is_bounded_not_per_project(
    client: TestClient,
    session_factory: sessionmaker[Session],
    database_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fixed = datetime(2026, 10, 3, 12, tzinfo=UTC)
    _set_review_context(monkeypatch, fixed)
    first_project = _add_project(session_factory, "Project 0")
    _add_task(
        session_factory,
        title="First complete",
        status="completed",
        project_id=first_project,
        completed_at_utc=fixed,
    )
    _add_task(
        session_factory,
        title="First attention",
        project_id=first_project,
        planned_date=date(2026, 10, 1),
    )
    one_project_queries = _count_review_selects(client, database_engine)

    for index in range(1, 9):
        project_id = _add_project(session_factory, f"Project {index}")
        _add_task(
            session_factory,
            title=f"Completed {index}",
            status="completed",
            project_id=project_id,
            completed_at_utc=fixed - timedelta(minutes=index),
        )
        _add_task(
            session_factory,
            title=f"Attention {index}",
            project_id=project_id,
            deadline_date=date(2026, 10, 1),
            deadline_timezone="UTC",
        )

    many_project_queries = _count_review_selects(client, database_engine)
    assert one_project_queries <= 12
    assert many_project_queries == one_project_queries
