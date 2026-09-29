from datetime import date

from fastapi.testclient import TestClient

from app.core.time import today_in_timezone
import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from app.models.task import Task
from app.models.recurrence import RecurrenceRule
from app.services.recurrence_service import RecurrenceService
from app.core.errors import RecurrenceRuleConflictError
from app.core.errors import RecurrenceVersionConflictError


def _today() -> str:
    return today_in_timezone("Asia/Shanghai").isoformat()


def _create_task(client: TestClient, title: str = "Recurring task") -> dict:
    response = client.post(
        "/api/v1/tasks",
        json={"title": title, "planned_date": _today()},
    )
    assert response.status_code == 201, response.text
    return response.json()


def _create_rule(client: TestClient, task: dict, **overrides) -> dict:
    payload = {
        "version": task["version"],
        "frequency": "daily",
        "starts_on": task["planned_date"],
        "timezone": "Asia/Shanghai",
    }
    payload.update(overrides)
    response = client.post(f"/api/v1/tasks/{task['id']}/recurrence", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_complete_occurrence_materializes_one_next_task_and_is_idempotent(
    client: TestClient,
) -> None:
    task = _create_task(client)
    rule = _create_rule(client, task)
    assert client.get(f"/api/v1/tasks/{task['id']}").json()["version"] == 2

    completed = client.post(
        f"/api/v1/tasks/{task['id']}/complete", json={"version": 2}
    )
    assert completed.status_code == 200, completed.text
    assert completed.json()["status"] == "completed"
    assert completed.json()["version"] == 3

    tasks = client.get("/api/v1/tasks").json()
    assert len(tasks) == 2
    next_task = next(item for item in tasks if item["status"] == "pending")
    assert next_task["recurrence_rule_id"] == rule["id"]
    assert date.fromisoformat(next_task["planned_date"]) > date.fromisoformat(task["planned_date"])
    assert next_task["deadline_date"] is None
    assert next_task["start_at_utc"] is None

    materialized = client.post(f"/api/v1/recurrence-rules/{rule['id']}/materialize")
    assert materialized.status_code == 200, materialized.text
    assert materialized.json()["id"] == next_task["id"]
    assert len(client.get("/api/v1/tasks").json()) == 2


def test_skip_soft_deletes_current_and_creates_next_in_one_flow(client: TestClient) -> None:
    task = _create_task(client, "Skip this occurrence")
    _create_rule(client, task)

    response = client.post(
        f"/api/v1/tasks/{task['id']}/skip", json={"version": 2}
    )
    assert response.status_code == 200, response.text
    assert response.json()["deleted_at_utc"] is not None
    assert response.json()["version"] == 3
    visible = client.get("/api/v1/tasks").json()
    assert len(visible) == 1
    assert visible[0]["status"] == "pending"
    assert visible[0]["recurrence_occurrence_date"] != task["planned_date"]


def test_stop_prevents_generation_and_restore_does_not_restart_rule(client: TestClient) -> None:
    task = _create_task(client, "Stop this rule")
    rule = _create_rule(client, task)
    stopped = client.post(
        f"/api/v1/recurrence-rules/{rule['id']}/stop", json={"version": 1}
    )
    assert stopped.status_code == 200, stopped.text
    assert stopped.json()["stopped_at_utc"] is not None

    completed = client.post(
        f"/api/v1/tasks/{task['id']}/complete", json={"version": 2}
    )
    assert completed.status_code == 200
    assert len(client.get("/api/v1/tasks").json()) == 1

    restored = client.post(
        f"/api/v1/tasks/{task['id']}/restore", json={"version": 3}
    )
    assert restored.status_code == 200
    assert len(client.get("/api/v1/tasks").json()) == 1


def test_weekly_and_monthly_rules_require_valid_selectors(client: TestClient) -> None:
    weekly_task = _create_task(client, "Weekly task")
    weekly = _create_rule(client, weekly_task, frequency="weekly", weekdays=[0, 2, 4])
    assert weekly["weekdays"] == [0, 2, 4]

    monthly_task = _create_task(client, "Monthly task")
    monthly = _create_rule(client, monthly_task, frequency="monthly", month_day=28)
    assert monthly["month_day"] == 28

    invalid_task = _create_task(client, "Invalid weekly task")
    response = client.post(
        f"/api/v1/tasks/{invalid_task['id']}/recurrence",
        json={
            "version": invalid_task["version"],
            "frequency": "weekly",
            "starts_on": invalid_task["planned_date"],
            "timezone": "Asia/Shanghai",
            "weekdays": [],
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "recurrence_validation_error"


def test_rule_update_and_stale_version_are_transactional(client: TestClient) -> None:
    task = _create_task(client, "Editable rule")
    rule = _create_rule(client, task)
    updated = client.patch(
        f"/api/v1/recurrence-rules/{rule['id']}?version=1",
        json={"frequency": "monthly", "month_day": 15, "weekdays": None},
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["version"] == 2
    assert updated.json()["frequency"] == "monthly"

    stale = client.patch(
        f"/api/v1/recurrence-rules/{rule['id']}?version=1",
        json={"frequency": "daily"},
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "recurrence_version_conflict"
    current = client.get(f"/api/v1/recurrence-rules/{rule['id']}").json()
    assert current["frequency"] == "monthly"
    assert current["version"] == 2


def test_stale_occurrence_version_does_not_complete_or_materialize(client: TestClient) -> None:
    task = _create_task(client, "Stale occurrence")
    _create_rule(client, task)
    stale = client.post(
        f"/api/v1/tasks/{task['id']}/complete", json={"version": 1}
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "task_version_conflict"
    current = client.get(f"/api/v1/tasks/{task['id']}").json()
    assert current["status"] == "pending"
    assert current["version"] == 2
    assert len(client.get("/api/v1/tasks").json()) == 1


def test_normal_delete_does_not_generate_next_occurrence(client: TestClient) -> None:
    task = _create_task(client, "Delete occurrence")
    rule = _create_rule(client, task)
    deleted = client.request(
        "DELETE", f"/api/v1/tasks/{task['id']}", json={"version": 2}
    )
    assert deleted.status_code == 204
    assert client.get("/api/v1/tasks").json() == []

    generated = client.post(f"/api/v1/recurrence-rules/{rule['id']}/materialize")
    assert generated.status_code == 200, generated.text
    assert generated.json()["recurrence_rule_id"] == rule["id"]


@pytest.mark.parametrize("frequency,selectors,after,expected", [
    ("daily", {}, "2026-12-31", "2027-01-01"),
    ("weekly", {"weekdays_mask": 5}, "2026-09-28", "2026-09-30"),
    ("weekly", {"weekdays_mask": 1}, "2026-09-28", "2026-10-05"),
    ("monthly", {"month_day": 28}, "2026-02-01", "2026-02-28"),
    ("monthly", {"month_day": 28}, "2026-02-28", "2026-03-28"),
    ("monthly", {"month_day": 1}, "2026-12-31", "2027-01-01"),
])
def test_next_date_boundaries(frequency, selectors, after, expected):
    rule = RecurrenceRule(frequency=frequency, **selectors)
    assert RecurrenceService._next_date(rule, date.fromisoformat(after)) == date.fromisoformat(expected)


@pytest.mark.parametrize("operation", ["complete", "skip"])
def test_generation_failure_rolls_back_occurrence(client, session_factory, monkeypatch, operation):
    task = _create_task(client)
    _create_rule(client, task)
    before = client.get(f"/api/v1/tasks/{task['id']}").json()
    def fail(*args):
        raise IntegrityError("injected unique collision", {}, Exception("duplicate"))
    monkeypatch.setattr(RecurrenceService, "_materialize_next_in_session", fail)
    with session_factory() as session:
        method = getattr(RecurrenceService(), f"{operation}_occurrence")
        with pytest.raises(RecurrenceRuleConflictError):
            method(session, task["id"], 2)
    assert client.get(f"/api/v1/tasks/{task['id']}").json() == before
    assert len(client.get("/api/v1/tasks").json()) == 1


def test_no_backlog_deleted_history_and_future_rule_start(client, monkeypatch):
    task = client.post("/api/v1/tasks", json={"title": "Old occurrence", "planned_date": "2020-01-01"}).json()
    rule = _create_rule(client, task)
    monkeypatch.setattr("app.services.recurrence_service.today_in_timezone", lambda zone: date(2026, 9, 29))
    assert client.request("DELETE", f"/api/v1/tasks/{task['id']}", json={"version": 2}).status_code == 204
    assert client.patch(f"/api/v1/recurrence-rules/{rule['id']}?version=1", json={"starts_on": "2026-10-10"}).status_code == 200
    next_task = client.post(f"/api/v1/recurrence-rules/{rule['id']}/materialize").json()
    assert next_task["planned_date"] == "2026-10-10"
    assert client.request("DELETE", f"/api/v1/tasks/{next_task['id']}", json={"version": 1}).status_code == 204
    later = client.post(f"/api/v1/recurrence-rules/{rule['id']}/materialize").json()
    assert later["planned_date"] == "2026-10-11"
    assert client.post(f"/api/v1/recurrence-rules/{rule['id']}/materialize").json()["id"] == later["id"]


def test_generated_metadata_and_no_deadline_or_reminder_copy(client):
    category = client.post("/api/v1/categories", json={"name": "valid"}).json()
    tag = client.post("/api/v1/tags", json={"name": "valid"}).json()
    project = client.post("/api/v1/projects", json={"name": "valid"}).json()
    task = client.post("/api/v1/tasks", json={
        "title": "Metadata", "planned_date": _today(), "category_id": category["id"],
        "tag_ids": [tag["id"]], "project_id": project["id"],
        "deadline": {"date": "2020-01-01"},
    }).json()
    rule = _create_rule(client, task)
    assert client.post(f"/api/v1/tasks/{task['id']}/reminders", json={"date": "2020-01-01", "time": "10:00"}).status_code == 201
    assert client.post(f"/api/v1/tasks/{task['id']}/complete", json={"version": 2}).status_code == 200
    next_task = client.post(f"/api/v1/recurrence-rules/{rule['id']}/materialize").json()
    assert next_task["category"]["id"] == category["id"]
    assert next_task["project_id"] == project["id"]
    assert [t["id"] for t in next_task["tags"]] == [tag["id"]]
    assert next_task["deadline_date"] is None
    assert next_task["start_at_utc"] is None
    assert client.get(f"/api/v1/tasks/{next_task['id']}/reminders").json() == []
    assert client.delete(f"/api/v1/categories/{category['id']}").status_code == 204
    assert client.delete(f"/api/v1/tags/{tag['id']}").status_code == 204
    assert client.request("DELETE", f"/api/v1/projects/{project['id']}", json={"version": 1}).status_code == 204
    current = client.get(f"/api/v1/tasks/{next_task['id']}").json()
    assert client.post(f"/api/v1/tasks/{current['id']}/complete", json={"version": current["version"]}).status_code == 200
    later = client.post(f"/api/v1/recurrence-rules/{rule['id']}/materialize").json()
    assert later["category"] is None and later["project_id"] is None and later["tags"] == []


def test_attach_rule_checks_task_version(client):
    task = _create_task(client)
    assert client.patch(f"/api/v1/tasks/{task['id']}?version=1", json={"title": "Newer"}).status_code == 200
    response = client.post(f"/api/v1/tasks/{task['id']}/recurrence", json={
        "version": 1, "frequency": "daily", "starts_on": task["planned_date"],
    })
    assert response.status_code == 409
    current = client.get(f"/api/v1/tasks/{task['id']}").json()
    assert current["title"] == "Newer" and current["version"] == 2
    assert current["recurrence_rule_id"] is None


def test_stale_rule_snapshot_cannot_generate_after_stop(client, session_factory):
    task = _create_task(client)
    rule = _create_rule(client, task)
    assert client.request("DELETE", f"/api/v1/tasks/{task['id']}", json={"version": 2}).status_code == 204
    service = RecurrenceService()
    with session_factory() as stale:
        loaded = service.get(stale, rule["id"])
        # End the read transaction, retaining the old optimistic version.
        stale.commit()
        assert client.post(f"/api/v1/recurrence-rules/{rule['id']}/stop", json={"version": 1}).status_code == 200
        with pytest.raises(RecurrenceVersionConflictError):
            service._materialize_next_in_session(stale, loaded)
    assert client.get("/api/v1/tasks").json() == []


def test_unique_collision_rolls_back_complete_and_next_task(client, database_engine):
    from sqlalchemy import event
    task = _create_task(client)
    _create_rule(client, task)
    before = client.get(f"/api/v1/tasks/{task['id']}").json()
    def duplicate(conn, cursor, statement, parameters, context, many):
        if statement.startswith("INSERT INTO tasks"):
            # Execute the same INSERT once so the normal execution encounters
            # a real SQLite uniqueness error inside the transaction.
            cursor.execute(statement, parameters)
    event.listen(database_engine, "before_cursor_execute", duplicate)
    try:
        result = client.post(f"/api/v1/tasks/{task['id']}/complete", json={"version": 2})
    finally:
        event.remove(database_engine, "before_cursor_execute", duplicate)
    assert result.status_code == 409
    assert result.json()["error"]["code"] == "recurrence_rule_conflict"
    assert client.get(f"/api/v1/tasks/{task['id']}").json() == before
    assert len(client.get("/api/v1/tasks").json()) == 1


def test_occurrence_pair_unique_even_after_soft_delete(client, session_factory):
    task = _create_task(client)
    rule = _create_rule(client, task)
    assert client.request("DELETE", f"/api/v1/tasks/{task['id']}", json={"version": 2}).status_code == 204
    with session_factory() as session:
        session.add(Task(title="Duplicate historical date", recurrence_rule_id=rule["id"], recurrence_occurrence_date=date.fromisoformat(task["planned_date"])))
        with pytest.raises(IntegrityError):
            session.commit()
        session.rollback()
        assert len(session.scalars(select(Task)).all()) == 1
