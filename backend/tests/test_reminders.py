from fastapi.testclient import TestClient
from datetime import datetime, timezone
from sqlalchemy import event, select
from app.models.reminder import Reminder
from app.services.reminder_service import ReminderService


def _create_task(client: TestClient, title: str = "Reminder task") -> dict:
    response = client.post("/api/v1/tasks", json={"title": title})
    assert response.status_code == 201, response.text
    return response.json()


def test_due_is_read_only_and_acknowledge_changes_state(client: TestClient) -> None:
    task = _create_task(client)
    response = client.post(
        f"/api/v1/tasks/{task['id']}/reminders",
        json={"date": "2020-01-01", "time": "10:00", "timezone": "Asia/Shanghai"},
    )
    assert response.status_code == 201, response.text
    reminder = response.json()
    assert reminder["status"] == "pending"
    assert reminder["version"] == 1

    due = client.get("/api/v1/reminders/due")
    assert due.status_code == 200
    assert [item["id"] for item in due.json()] == [reminder["id"]]
    unchanged = client.get(f"/api/v1/tasks/{task['id']}/reminders").json()[0]
    assert unchanged["status"] == "pending"
    assert unchanged["version"] == 1

    acknowledged = client.post(
        f"/api/v1/reminders/{reminder['id']}/acknowledge", json={"version": 1}
    )
    assert acknowledged.status_code == 200, acknowledged.text
    assert acknowledged.json()["status"] == "acknowledged"
    assert acknowledged.json()["version"] == 2
    assert client.get("/api/v1/reminders/due").json() == []


def test_dismiss_and_stale_reminder_updates(client: TestClient) -> None:
    task = _create_task(client, "Dismiss reminder")
    reminder = client.post(
        f"/api/v1/tasks/{task['id']}/reminders",
        json={"date": "2020-01-01", "time": "10:00", "timezone": "Asia/Shanghai"},
    ).json()
    dismissed = client.post(
        f"/api/v1/reminders/{reminder['id']}/dismiss", json={"version": 1}
    )
    assert dismissed.status_code == 200
    assert dismissed.json()["status"] == "dismissed"

    stale = client.post(
        f"/api/v1/reminders/{reminder['id']}/acknowledge", json={"version": 1}
    )
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "reminder_version_conflict"


def test_due_excludes_completed_and_deleted_tasks(client: TestClient) -> None:
    completed_task = _create_task(client, "Completed reminder")
    completed_reminder = client.post(
        f"/api/v1/tasks/{completed_task['id']}/reminders",
        json={"date": "2020-01-01", "time": "10:00", "timezone": "Asia/Shanghai"},
    ).json()
    assert client.post(
        f"/api/v1/tasks/{completed_task['id']}/complete",
        json={"version": completed_task["version"]},
    ).status_code == 200

    deleted_task = _create_task(client, "Deleted reminder")
    deleted_reminder = client.post(
        f"/api/v1/tasks/{deleted_task['id']}/reminders",
        json={"date": "2020-01-01", "time": "10:00", "timezone": "Asia/Shanghai"},
    ).json()
    assert client.request(
        "DELETE",
        f"/api/v1/tasks/{deleted_task['id']}",
        json={"version": deleted_task["version"]},
    ).status_code == 204

    due_ids = {item["id"] for item in client.get("/api/v1/reminders/due").json()}
    assert completed_reminder["id"] not in due_ids
    assert deleted_reminder["id"] not in due_ids


def test_reminder_dst_validation(client: TestClient) -> None:
    task = _create_task(client, "DST reminder")
    response = client.post(
        f"/api/v1/tasks/{task['id']}/reminders",
        json={
            "date": "2026-11-01",
            "time": "01:30",
            "timezone": "America/New_York",
        },
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "reminder_validation_error"


def test_due_utc_boundary_read_only_and_pending_survives_reconnect(client, database_engine, session_factory, monkeypatch):
    task = _create_task(client)
    reminder = client.post(f"/api/v1/tasks/{task['id']}/reminders", json={
        "date": "2026-10-01", "time": "08:00", "timezone": "Asia/Shanghai",
    }).json()
    monkeypatch.setattr("app.services.reminder_service.utc_now", lambda: datetime(2026, 10, 1, tzinfo=timezone.utc))
    statements = []
    def capture(conn, cursor, statement, parameters, context, many):
        statements.append(statement.strip().split()[0].upper())
    event.listen(database_engine, "before_cursor_execute", capture)
    try:
        assert client.get("/api/v1/reminders/due").json() == [reminder]
        assert client.get("/api/v1/reminders/due").json() == [reminder]
    finally:
        event.remove(database_engine, "before_cursor_execute", capture)
    assert set(statements) == {"SELECT"}
    database_engine.dispose()
    with session_factory() as session:
        due = ReminderService().due(session)
        assert [r.id for r in due] == [reminder["id"]]
        assert due[0].status == "pending" and due[0].version == 1
    assert client.get(f"/api/v1/tasks/{task['id']}").json() == task


def test_repeated_ack_has_no_side_effect_and_edit_delete_are_versioned(client):
    task = _create_task(client)
    reminder = client.post(f"/api/v1/tasks/{task['id']}/reminders", json={"date": "2020-01-01", "time": "10:00"}).json()
    url = f"/api/v1/reminders/{reminder['id']}"
    acknowledged = client.post(url + "/acknowledge", json={"version": 1}).json()
    stale = client.post(url + "/acknowledge", json={"version": 1})
    assert stale.status_code == 409
    assert stale.json()["error"]["code"] == "reminder_version_conflict"
    repeated = client.post(url + "/acknowledge", json={"version": 2})
    assert repeated.status_code == 409
    assert repeated.json()["error"]["code"] == "reminder_state_conflict"
    assert client.get(f"/api/v1/tasks/{task['id']}/reminders").json() == [acknowledged]
    assert client.get(f"/api/v1/tasks/{task['id']}").json() == task
    updated = client.patch(url + "?version=2", json={"date": "2030-01-01", "time": "10:00"})
    assert updated.status_code == 200
    assert updated.json()["version"] == 3 and updated.json()["status"] == "pending"
    assert client.request("DELETE", url, json={"version": 2}).status_code == 409
    assert client.request("DELETE", url, json={"version": 3}).status_code == 204
    assert client.get(f"/api/v1/tasks/{task['id']}/reminders").json() == []
