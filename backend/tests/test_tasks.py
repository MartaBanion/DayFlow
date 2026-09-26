from datetime import timezone

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.models.task import Task


def create_task(
    client: TestClient,
    title: str = "Read Linux notes",
    planned_date: str | None = "2026-09-26",
) -> dict:
    response = client.post(
        "/api/v1/tasks",
        json={
            "title": title,
            "description": "A focused session",
            "planned_date": planned_date,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_create_read_and_update_task(client: TestClient) -> None:
    created = create_task(client)
    task_id = created["id"]

    assert created["status"] == "pending"
    assert created["version"] == 1
    assert created["description"] == "A focused session"
    assert created["created_at_utc"].endswith("Z")
    assert created["updated_at_utc"].endswith("Z")

    response = client.get(f"/api/v1/tasks/{task_id}")
    assert response.status_code == 200
    assert response.json()["id"] == task_id

    response = client.patch(
        f"/api/v1/tasks/{task_id}?version=1",
        json={"title": "Read updated Linux notes", "description": None},
    )
    assert response.status_code == 200
    updated = response.json()
    assert updated["title"] == "Read updated Linux notes"
    assert updated["description"] is None
    assert updated["version"] == 2


def test_complete_and_restore_task(client: TestClient) -> None:
    created = create_task(client, title="Complete this task")
    task_id = created["id"]

    completed_response = client.post(
        f"/api/v1/tasks/{task_id}/complete", json={"version": 1}
    )
    assert completed_response.status_code == 200
    completed = completed_response.json()
    assert completed["status"] == "completed"
    assert completed["completed_at_utc"].endswith("Z")
    assert completed["version"] == 2

    restored_response = client.post(
        f"/api/v1/tasks/{task_id}/restore", json={"version": 2}
    )
    assert restored_response.status_code == 200
    restored = restored_response.json()
    assert restored["status"] == "pending"
    assert restored["completed_at_utc"] is None
    assert restored["version"] == 3


def test_soft_delete_hides_task_and_restore_recovers_it(client: TestClient) -> None:
    created = create_task(client, title="Archive this task")
    task_id = created["id"]

    response = client.request(
        "DELETE", f"/api/v1/tasks/{task_id}", json={"version": 1}
    )
    assert response.status_code == 204
    assert client.get(f"/api/v1/tasks/{task_id}").status_code == 404
    assert client.get("/api/v1/tasks").json() == []

    response = client.post(
        f"/api/v1/tasks/{task_id}/restore", json={"version": 2}
    )
    assert response.status_code == 200
    assert response.json()["deleted_at_utc"] is None


def test_today_query_filters_by_date(client: TestClient) -> None:
    create_task(client, title="Today task", planned_date="2026-09-26")
    create_task(client, title="Tomorrow task", planned_date="2026-09-27")
    create_task(client, title="Undated task", planned_date=None)

    response = client.get("/api/v1/today?date=2026-09-26")
    assert response.status_code == 200
    assert [task["title"] for task in response.json()] == ["Today task"]


def test_version_conflict_does_not_overwrite_newer_data(client: TestClient) -> None:
    created = create_task(client, title="Versioned task")
    task_id = created["id"]
    assert client.patch(
        f"/api/v1/tasks/{task_id}?version=1", json={"title": "First update"}
    ).status_code == 200

    response = client.patch(
        f"/api/v1/tasks/{task_id}?version=1", json={"title": "Stale update"}
    )
    assert response.status_code == 409
    assert response.json()["error"]["code"] == "task_version_conflict"
    assert client.get(f"/api/v1/tasks/{task_id}").json()["title"] == "First update"


def test_validation_error_is_consistent(client: TestClient) -> None:
    response = client.post(
        "/api/v1/tasks", json={"title": "   ", "planned_date": "not-a-date"}
    )
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"


def test_persistence_and_test_database_isolation(
    client: TestClient,
    session_factory: sessionmaker[Session],
) -> None:
    created = create_task(client, title="Persist me")
    task_id = created["id"]

    with session_factory() as session:
        stored = session.scalar(select(Task).where(Task.id == task_id))
        assert stored is not None
        assert stored.title == "Persist me"
        assert stored.created_at_utc.tzinfo is not None
        assert stored.created_at_utc.utcoffset() == timezone.utc.utcoffset(None)


def test_transaction_rolls_back_failed_unit_of_work(
    session_factory: sessionmaker[Session],
) -> None:
    session = session_factory()
    try:
        try:
            with session.begin():
                session.add(Task(id="rollback-task", title="Should not persist"))
                raise RuntimeError("forced failure")
        except RuntimeError:
            pass

        assert session.scalar(select(Task).where(Task.id == "rollback-task")) is None
    finally:
        session.close()
