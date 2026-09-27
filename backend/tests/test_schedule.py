from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import select

from app.core.schedule import validate_persisted_schedule
from app.core.errors import ScheduleValidationError
from app.core.time import today_in_timezone
from app.models.task import Task


def create_scheduled_task(
    client: TestClient,
    title: str,
    *,
    planned_date: str = "2026-09-26",
    start_time: str = "14:00",
    end_time: str = "15:00",
    timezone_name: str = "Asia/Shanghai",
) -> dict:
    response = client.post(
        "/api/v1/tasks",
        json={
            "title": title,
            "planned_date": planned_date,
            "schedule": {
                "start_time": start_time,
                "end_time": end_time,
                "timezone": timezone_name,
            },
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_date_only_task_and_timed_task_are_distinct(client: TestClient) -> None:
    date_only = client.post(
        "/api/v1/tasks", json={"title": "Date only", "planned_date": "2026-09-26"}
    )
    assert date_only.status_code == 201
    assert date_only.json()["start_at_utc"] is None
    assert date_only.json()["end_at_utc"] is None
    assert date_only.json()["schedule_timezone"] is None

    timed = create_scheduled_task(client, "Timed task")
    assert timed["start_at_utc"] == "2026-09-26T06:00:00.000000Z"
    assert timed["end_at_utc"] == "2026-09-26T07:00:00.000000Z"
    assert timed["schedule_timezone"] == "Asia/Shanghai"


def test_schedule_patch_clear_and_clear_planned_date(client: TestClient) -> None:
    created = create_scheduled_task(client, "Clear schedule")

    cleared_schedule = client.patch(
        f"/api/v1/tasks/{created['id']}?version=1",
        json={"schedule": None},
    )
    assert cleared_schedule.status_code == 200
    cleared = cleared_schedule.json()
    assert cleared["planned_date"] == "2026-09-26"
    assert cleared["start_at_utc"] is None
    assert cleared["version"] == 2

    rescheduled = client.patch(
        f"/api/v1/tasks/{created['id']}?version=2",
        json={
            "schedule": {
                "start_time": "16:00",
                "end_time": "17:00",
            }
        },
    )
    assert rescheduled.status_code == 200
    assert rescheduled.json()["start_at_utc"] == "2026-09-26T08:00:00.000000Z"

    cleared_all = client.patch(
        f"/api/v1/tasks/{created['id']}?version=3",
        json={"planned_date": None, "schedule": None},
    )
    assert cleared_all.status_code == 200
    assert cleared_all.json()["planned_date"] is None
    assert cleared_all.json()["start_at_utc"] is None
    assert cleared_all.json()["version"] == 4


def test_changing_planned_date_preserves_local_schedule_clock(client: TestClient) -> None:
    created = create_scheduled_task(client, "Move date")
    response = client.patch(
        f"/api/v1/tasks/{created['id']}?version=1",
        json={"planned_date": "2026-09-27"},
    )
    assert response.status_code == 200, response.text
    moved = response.json()
    assert moved["planned_date"] == "2026-09-27"
    assert moved["start_at_utc"] == "2026-09-27T06:00:00.000000Z"
    assert moved["end_at_utc"] == "2026-09-27T07:00:00.000000Z"
    assert moved["schedule_timezone"] == "Asia/Shanghai"
    assert moved["version"] == 2


def test_cannot_clear_planned_date_without_clearing_schedule(client: TestClient) -> None:
    created = create_scheduled_task(client, "Keep schedule invariant")
    response = client.patch(
        f"/api/v1/tasks/{created['id']}?version=1",
        json={"planned_date": None},
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "schedule_validation_error"

    unchanged = client.get(f"/api/v1/tasks/{created['id']}").json()
    assert unchanged["planned_date"] == "2026-09-26"
    assert unchanged["start_at_utc"] == "2026-09-26T06:00:00.000000Z"
    assert unchanged["end_at_utc"] == "2026-09-26T07:00:00.000000Z"
    assert unchanged["schedule_timezone"] == "Asia/Shanghai"
    assert unchanged["version"] == 1


def test_schedule_validation_rejects_invalid_requests(client: TestClient) -> None:
    invalid_payloads = [
        {
            "title": "No planned date",
            "schedule": {"start_time": "14:00", "end_time": "15:00"},
        },
        {
            "title": "Reversed schedule",
            "planned_date": "2026-09-26",
            "schedule": {"start_time": "15:00", "end_time": "14:00"},
        },
        {
            "title": "Invalid timezone",
            "planned_date": "2026-09-26",
            "schedule": {
                "start_time": "14:00",
                "end_time": "15:00",
                "timezone": "Not/A_Timezone",
            },
        },
        {
            "title": "Ambiguous time",
            "planned_date": "2026-11-01",
            "schedule": {
                "start_time": "01:30",
                "end_time": "02:30",
                "timezone": "America/New_York",
            },
        },
        {
            "title": "Nonexistent time",
            "planned_date": "2026-03-08",
            "schedule": {
                "start_time": "02:30",
                "end_time": "03:30",
                "timezone": "America/New_York",
            },
        },
    ]

    for payload in invalid_payloads:
        response = client.post("/api/v1/tasks", json=payload)
        assert response.status_code == 422, response.text
        assert response.json()["error"]["code"] == "schedule_validation_error"


def test_dst_normal_local_time_converts_in_new_york(client: TestClient) -> None:
    response = client.post(
        "/api/v1/tasks",
        json={
            "title": "Normal New York time",
            "planned_date": "2026-01-15",
            "schedule": {
                "start_time": "09:00",
                "end_time": "10:00",
                "timezone": "America/New_York",
            },
        },
    )
    assert response.status_code == 201, response.text
    assert response.json()["start_at_utc"] == "2026-01-15T14:00:00.000000Z"
    assert response.json()["end_at_utc"] == "2026-01-15T15:00:00.000000Z"


def test_schedule_validation_checks_persisted_date_consistency() -> None:
    with pytest.raises(ScheduleValidationError):
        validate_persisted_schedule(
            date(2026, 9, 27),
            datetime(2026, 9, 26, 6, tzinfo=timezone.utc),
            datetime(2026, 9, 26, 7, tzinfo=timezone.utc),
            "Asia/Shanghai",
        )


def test_calendar_range_includes_date_only_completed_and_excludes_deleted(
    client: TestClient,
) -> None:
    pending = create_scheduled_task(client, "Calendar pending", start_time="09:00", end_time="10:00")
    date_only = client.post(
        "/api/v1/tasks",
        json={"title": "Calendar date only", "planned_date": "2026-09-26"},
    ).json()
    completed = create_scheduled_task(client, "Calendar completed", start_time="10:00", end_time="11:00")
    assert client.post(
        f"/api/v1/tasks/{completed['id']}/complete", json={"version": 1}
    ).status_code == 200
    deleted = create_scheduled_task(client, "Calendar deleted", start_time="11:00", end_time="12:00")
    assert client.request(
        "DELETE", f"/api/v1/tasks/{deleted['id']}", json={"version": 1}
    ).status_code == 204

    response = client.get("/api/v1/calendar?start=2026-09-26&end=2026-09-27")
    assert response.status_code == 200
    returned_ids = {task["id"] for task in response.json()}
    assert {pending["id"], date_only["id"], completed["id"]} <= returned_ids
    assert deleted["id"] not in returned_ids
    assert client.get("/api/v1/calendar?start=2026-09-27&end=2026-09-26").status_code == 422
    assert client.get("/api/v1/calendar?start=2026-01-01&end=2026-03-05").status_code == 422


def test_schedule_conflict_is_atomic_and_override_is_explicit(client: TestClient) -> None:
    first = create_scheduled_task(client, "First scheduled task")
    conflict_create = client.post(
        "/api/v1/tasks",
        json={
            "title": "Conflicting create",
            "planned_date": "2026-09-26",
            "schedule": {"start_time": "14:30", "end_time": "15:30"},
        },
    )
    assert conflict_create.status_code == 409
    assert conflict_create.json()["error"]["code"] == "schedule_conflict"

    second = create_scheduled_task(
        client, "Second scheduled task", start_time="16:00", end_time="17:00"
    )
    conflict_update = client.patch(
        f"/api/v1/tasks/{second['id']}?version=1",
        json={
            "title": "Must not partially update",
            "schedule": {"start_time": "14:30", "end_time": "15:30"},
        },
    )
    assert conflict_update.status_code == 409
    unchanged = client.get(f"/api/v1/tasks/{second['id']}").json()
    assert unchanged["title"] == "Second scheduled task"
    assert unchanged["version"] == 1
    assert unchanged["start_at_utc"] == "2026-09-26T08:00:00.000000Z"

    override = client.patch(
        f"/api/v1/tasks/{second['id']}?version=1&allow_schedule_conflict=true",
        json={"schedule": {"start_time": "14:30", "end_time": "15:30"}},
    )
    assert override.status_code == 200
    assert override.json()["version"] == 2
    assert override.json()["start_at_utc"] == "2026-09-26T06:30:00.000000Z"
    assert first["version"] == 1


def test_stale_version_cannot_be_bypassed_by_conflict_override(client: TestClient) -> None:
    first = create_scheduled_task(client, "Conflict source")
    second = create_scheduled_task(
        client, "Versioned conflict target", start_time="16:00", end_time="17:00"
    )
    current = client.patch(
        f"/api/v1/tasks/{second['id']}?version=1",
        json={"title": "Current target"},
    )
    assert current.status_code == 200

    stale_override = client.patch(
        f"/api/v1/tasks/{second['id']}?version=1&allow_schedule_conflict=true",
        json={
            "title": "Must not write",
            "schedule": {"start_time": "14:30", "end_time": "15:30"},
        },
    )
    assert stale_override.status_code == 409
    assert stale_override.json()["error"]["code"] == "task_version_conflict"
    unchanged = client.get(f"/api/v1/tasks/{second['id']}").json()
    assert unchanged["title"] == "Current target"
    assert unchanged["version"] == 2
    assert unchanged["start_at_utc"] == "2026-09-26T08:00:00.000000Z"
    assert first["version"] == 1


def test_combined_task_and_schedule_patch_increments_once(client: TestClient) -> None:
    category = client.post("/api/v1/categories", json={"name": "Schedule category"}).json()
    tag = client.post("/api/v1/tags", json={"name": "schedule-tag"}).json()
    created = client.post(
        "/api/v1/tasks",
        json={"title": "Combined patch", "planned_date": "2026-09-26"},
    ).json()

    response = client.patch(
        f"/api/v1/tasks/{created['id']}?version=1",
        json={
            "title": "Combined patch updated",
            "description": "One transaction",
            "planned_date": "2026-09-27",
            "priority": "high",
            "category_id": category["id"],
            "tag_ids": [tag["id"]],
            "schedule": {"start_time": "14:00", "end_time": "15:00"},
        },
    )
    assert response.status_code == 200, response.text
    updated = response.json()
    assert updated["version"] == 2
    assert updated["planned_date"] == "2026-09-27"
    assert updated["priority"] == "high"
    assert updated["category"]["id"] == category["id"]
    assert [item["id"] for item in updated["tags"]] == [tag["id"]]
    assert updated["start_at_utc"] == "2026-09-27T06:00:00.000000Z"


def test_stale_schedule_patch_does_not_change_data(client: TestClient) -> None:
    created = create_scheduled_task(client, "Stale schedule")
    current = client.patch(
        f"/api/v1/tasks/{created['id']}?version=1",
        json={"title": "Current update"},
    )
    assert current.status_code == 200

    stale = client.patch(
        f"/api/v1/tasks/{created['id']}?version=1",
        json={"title": "Stale update", "schedule": None},
    )
    assert stale.status_code == 409
    unchanged = client.get(f"/api/v1/tasks/{created['id']}").json()
    assert unchanged["title"] == "Current update"
    assert unchanged["version"] == 2
    assert unchanged["start_at_utc"] == "2026-09-26T06:00:00.000000Z"


def test_runtime_reports_configured_timezone_and_local_date(client: TestClient) -> None:
    response = client.get("/api/v1/runtime")
    assert response.status_code == 200
    body = response.json()
    assert body["timezone"] == "Asia/Shanghai"
    assert body["local_date"] == today_in_timezone("Asia/Shanghai").isoformat()


def test_schedule_persists_after_database_engine_restart(
    client: TestClient,
    session_factory,
    database_engine,
) -> None:
    created = create_scheduled_task(client, "Restart persistence")
    database_engine.dispose()

    with session_factory() as session:
        stored = session.scalar(select(Task).where(Task.id == created["id"]))
        assert stored is not None
        assert stored.start_at_utc.isoformat() == "2026-09-26T06:00:00+00:00"
        assert stored.end_at_utc.isoformat() == "2026-09-26T07:00:00+00:00"
        assert stored.schedule_timezone == "Asia/Shanghai"
