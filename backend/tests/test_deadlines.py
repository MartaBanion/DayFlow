from fastapi.testclient import TestClient
from datetime import date, datetime, timezone
from app.models.task import Task


def _create_task(client: TestClient, **overrides) -> dict:
    payload = {"title": "Deadline task", "planned_date": "2026-10-20"}
    payload.update(overrides)
    response = client.post("/api/v1/tasks", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_date_only_and_timed_deadline_are_independent_from_schedule(client: TestClient) -> None:
    task = _create_task(
        client,
        schedule={
            "start_time": "14:00",
            "end_time": "15:00",
            "timezone": "Asia/Shanghai",
        },
        deadline={"date": "2026-10-20", "timezone": "America/New_York"},
    )
    assert task["deadline_date"] == "2026-10-20"
    assert task["deadline_at_utc"] is None
    assert task["deadline_timezone"] == "America/New_York"
    assert task["deadline_status"] == "upcoming"
    assert task["start_at_utc"].endswith("06:00:00.000000Z")

    response = client.patch(
        f"/api/v1/tasks/{task['id']}?version={task['version']}",
        json={
            "deadline": {
                "date": "2026-10-20",
                "time": "17:00",
                "timezone": "Asia/Shanghai",
            }
        },
    )
    assert response.status_code == 200, response.text
    updated = response.json()
    assert updated["version"] == 2
    assert updated["deadline_at_utc"].endswith("09:00:00.000000Z")
    assert updated["deadline_timezone"] == "Asia/Shanghai"
    assert updated["start_at_utc"] == task["start_at_utc"]
    assert updated["end_at_utc"] == task["end_at_utc"]


def test_deadline_omitted_is_preserved_and_null_clears_only_deadline(client: TestClient) -> None:
    task = _create_task(
        client,
        deadline={"date": "2026-10-20", "timezone": "Asia/Shanghai"},
    )
    unchanged = client.patch(
        f"/api/v1/tasks/{task['id']}?version=1", json={"title": "Renamed"}
    )
    assert unchanged.status_code == 200
    assert unchanged.json()["deadline_date"] == "2026-10-20"
    assert unchanged.json()["version"] == 2

    cleared = client.patch(
        f"/api/v1/tasks/{task['id']}?version=2", json={"deadline": None}
    )
    assert cleared.status_code == 200, cleared.text
    body = cleared.json()
    assert body["deadline_date"] is None
    assert body["deadline_at_utc"] is None
    assert body["deadline_timezone"] is None
    assert body["planned_date"] == "2026-10-20"
    assert body["version"] == 3


def test_deadline_invalid_timezone_and_dst_return_422_without_mutation(client: TestClient) -> None:
    invalid_timezone = client.post(
        "/api/v1/tasks",
        json={
            "title": "Invalid timezone",
            "deadline": {"date": "2026-10-20", "timezone": "Not/AZone"},
        },
    )
    assert invalid_timezone.status_code == 422

    nonexistent = client.post(
        "/api/v1/tasks",
        json={
            "title": "Nonexistent local time",
            "deadline": {
                "date": "2026-03-08",
                "time": "02:30",
                "timezone": "America/New_York",
            },
        },
    )
    assert nonexistent.status_code == 422

    ambiguous = client.post(
        "/api/v1/tasks",
        json={
            "title": "Ambiguous local time",
            "deadline": {
                "date": "2026-11-01",
                "time": "01:30",
                "timezone": "America/New_York",
            },
        },
    )
    assert ambiguous.status_code == 422

    normal = client.post(
        "/api/v1/tasks",
        json={
            "title": "Normal DST local time",
            "deadline": {
                "date": "2026-03-08",
                "time": "03:30",
                "timezone": "America/New_York",
            },
        },
    )
    assert normal.status_code == 201, normal.text
    assert normal.json()["deadline_at_utc"].endswith("07:30:00.000000Z")


def test_invalid_deadline_patch_does_not_change_task(client: TestClient) -> None:
    task = _create_task(
        client,
        deadline={"date": "2026-10-20", "timezone": "Asia/Shanghai"},
    )
    response = client.patch(
        f"/api/v1/tasks/{task['id']}?version=1",
        json={
            "deadline": {
                "date": "2026-03-08",
                "time": "02:30",
                "timezone": "America/New_York",
            }
        },
    )
    assert response.status_code == 422
    current = client.get(f"/api/v1/tasks/{task['id']}").json()
    assert current["deadline_date"] == "2026-10-20"
    assert current["deadline_at_utc"] is None
    assert current["version"] == 1


def test_saved_timezone_and_utc_deadline_boundaries(monkeypatch):
    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return datetime(2026, 10, 2, 0, 30, tzinfo=timezone.utc).astimezone(tz)
    monkeypatch.setattr("app.models.task.datetime", Clock)
    task = Task(status="pending", deadline_date=date(2026, 10, 1), deadline_timezone="America/Los_Angeles")
    assert task.deadline_status == "due_today"
    task.deadline_timezone = "Asia/Shanghai"
    assert task.deadline_status == "overdue"
    task.deadline_at_utc = datetime(2026, 10, 2, 0, 31, tzinfo=timezone.utc)
    task.deadline_date = date(2026, 10, 2)
    assert task.deadline_status == "due_today"
    task.deadline_at_utc = datetime(2026, 10, 2, 0, 30, tzinfo=timezone.utc)
    assert task.deadline_status == "overdue"
    task.status = "completed"
    assert task.deadline_status == "completed"
    task.deleted_at_utc = Clock.now(timezone.utc)
    assert task.deadline_status == "none"
