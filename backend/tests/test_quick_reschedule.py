from __future__ import annotations

from copy import deepcopy

from fastapi.testclient import TestClient


def create_task(client: TestClient, **payload) -> dict:
    response = client.post("/api/v1/tasks", json={"title": "Reschedule task", **payload})
    assert response.status_code == 201, response.text
    return response.json()


def create_scheduled_task(client: TestClient, **payload) -> dict:
    return create_task(
        client,
        planned_date=payload.pop("planned_date", "2026-10-05"),
        schedule=payload.pop(
            "schedule",
            {
                "start_time": "09:00",
                "end_time": "10:00",
                "timezone": "Asia/Shanghai",
            },
        ),
        **payload,
    )


def patch_planned_date(client: TestClient, task: dict, planned_date: str | None, **extra) -> dict:
    response = client.patch(
        f"/api/v1/tasks/{task['id']}?version={task['version']}",
        json={"planned_date": planned_date, **extra},
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_move_scheduled_task_preserves_local_clock_and_recalculates_utc(client: TestClient) -> None:
    created = create_scheduled_task(client)

    moved = patch_planned_date(client, created, "2026-10-06")

    assert moved["planned_date"] == "2026-10-06"
    assert moved["start_at_utc"] == "2026-10-06T01:00:00.000000Z"
    assert moved["end_at_utc"] == "2026-10-06T02:00:00.000000Z"
    assert moved["schedule_timezone"] == "Asia/Shanghai"


def test_move_scheduled_task_across_dst_preserves_local_clock(client: TestClient) -> None:
    created = create_scheduled_task(
        client,
        planned_date="2026-10-31",
        schedule={
            "start_time": "09:00",
            "end_time": "10:00",
            "timezone": "America/New_York",
        },
    )
    assert created["start_at_utc"] == "2026-10-31T13:00:00.000000Z"

    moved = patch_planned_date(client, created, "2026-11-02")

    assert moved["planned_date"] == "2026-11-02"
    assert moved["start_at_utc"] == "2026-11-02T14:00:00.000000Z"
    assert moved["end_at_utc"] == "2026-11-02T15:00:00.000000Z"
    assert moved["schedule_timezone"] == "America/New_York"


def test_move_to_inbox_clears_schedule_in_one_patch(client: TestClient) -> None:
    created = create_scheduled_task(client)

    response = client.patch(
        f"/api/v1/tasks/{created['id']}?version={created['version']}",
        json={"planned_date": None, "schedule": None},
    )

    assert response.status_code == 200, response.text
    moved = response.json()
    assert moved["planned_date"] is None
    assert moved["start_at_utc"] is None
    assert moved["end_at_utc"] is None
    assert moved["schedule_timezone"] is None
    assert client.get("/api/v1/tasks?inbox=true").json() == [moved]


def test_reschedule_preserves_deadline_and_reminder(client: TestClient) -> None:
    created = create_task(
        client,
        planned_date="2026-10-05",
        deadline={
            "date": "2026-10-05",
            "time": "09:00",
            "timezone": "America/New_York",
        },
    )
    reminder_response = client.post(
        f"/api/v1/tasks/{created['id']}/reminders",
        json={"date": "2026-10-05", "time": "08:00", "timezone": "Asia/Shanghai"},
    )
    assert reminder_response.status_code == 201, reminder_response.text
    before_reminders = client.get(f"/api/v1/tasks/{created['id']}/reminders").json()
    before_deadline = {
        key: created[key]
        for key in ("deadline_date", "deadline_at_utc", "deadline_timezone")
    }

    moved = patch_planned_date(client, created, "2026-10-06")

    assert {key: moved[key] for key in before_deadline} == before_deadline
    assert client.get(f"/api/v1/tasks/{created['id']}/reminders").json() == before_reminders


def test_move_to_inbox_preserves_reminder(client: TestClient) -> None:
    created = create_scheduled_task(client)
    reminder_response = client.post(
        f"/api/v1/tasks/{created['id']}/reminders",
        json={"date": "2026-10-05", "time": "08:00", "timezone": "Asia/Shanghai"},
    )
    assert reminder_response.status_code == 201, reminder_response.text
    before_reminders = client.get(f"/api/v1/tasks/{created['id']}/reminders").json()

    moved = patch_planned_date(client, created, None, schedule=None)

    assert moved["planned_date"] is None
    assert client.get(f"/api/v1/tasks/{created['id']}/reminders").json() == before_reminders


def test_reschedule_preserves_recurrence_occurrence_without_materializing(client: TestClient) -> None:
    created = create_task(client, planned_date="2026-10-05")
    rule_response = client.post(
        f"/api/v1/tasks/{created['id']}/recurrence",
        json={
            "version": created["version"],
            "frequency": "daily",
            "starts_on": "2026-10-05",
            "timezone": "Asia/Shanghai",
        },
    )
    assert rule_response.status_code == 201, rule_response.text
    rule = rule_response.json()
    before_task = client.get(f"/api/v1/tasks/{created['id']}").json()
    before_rule = deepcopy(client.get(f"/api/v1/recurrence-rules/{rule['id']}").json())

    moved = patch_planned_date(client, before_task, "2026-10-06")

    assert moved["planned_date"] == "2026-10-06"
    assert moved["recurrence_rule_id"] == before_task["recurrence_rule_id"]
    assert moved["recurrence_occurrence_date"] == before_task["recurrence_occurrence_date"]
    assert client.get(f"/api/v1/recurrence-rules/{rule['id']}").json() == before_rule
    assert len(client.get("/api/v1/tasks").json()) == 1


def test_stale_and_deleted_tasks_cannot_be_rescheduled(client: TestClient) -> None:
    created = create_task(client, planned_date="2026-10-05")
    advanced = client.patch(
        f"/api/v1/tasks/{created['id']}?version={created['version']}",
        json={"title": "New title"},
    )
    assert advanced.status_code == 200

    stale = client.patch(
        f"/api/v1/tasks/{created['id']}?version={created['version']}",
        json={"planned_date": "2026-10-06"},
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "task_version_conflict"
    assert client.get(f"/api/v1/tasks/{created['id']}").json()["planned_date"] == "2026-10-05"

    deleted = create_task(client, planned_date="2026-10-05")
    remove = client.request(
        "DELETE",
        f"/api/v1/tasks/{deleted['id']}",
        json={"version": deleted["version"]},
    )
    assert remove.status_code == 204
    blocked = client.patch(
        f"/api/v1/tasks/{deleted['id']}?version={deleted['version']}",
        json={"planned_date": "2026-10-06"},
    )
    assert blocked.status_code == 404


def test_schedule_conflict_keeps_existing_force_contract(client: TestClient) -> None:
    first = create_scheduled_task(
        client,
        planned_date="2026-10-06",
        schedule={"start_time": "09:00", "end_time": "10:00", "timezone": "Asia/Shanghai"},
    )
    second = create_scheduled_task(
        client,
        planned_date="2026-10-05",
        schedule={"start_time": "09:00", "end_time": "10:00", "timezone": "Asia/Shanghai"},
    )

    conflict = client.patch(
        f"/api/v1/tasks/{second['id']}?version={second['version']}",
        json={"planned_date": "2026-10-06"},
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "schedule_conflict"
    unchanged = client.get(f"/api/v1/tasks/{second['id']}").json()
    assert unchanged["planned_date"] == "2026-10-05"
    assert unchanged["version"] == second["version"]

    forced = client.patch(
        f"/api/v1/tasks/{second['id']}?version={second['version']}&allow_schedule_conflict=true",
        json={"planned_date": "2026-10-06"},
    )
    assert forced.status_code == 200, forced.text
    assert forced.json()["planned_date"] == "2026-10-06"
    assert forced.json()["version"] == second["version"] + 1
    assert first["id"] != second["id"]
