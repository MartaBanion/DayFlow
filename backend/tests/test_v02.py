from __future__ import annotations

from uuid import uuid4

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.models.task import Task


def create_task(
    client: TestClient,
    title: str,
    planned_date: str | None = None,
    **extra: object,
) -> dict:
    response = client.post(
        "/api/v1/tasks",
        json={"title": title, "planned_date": planned_date, **extra},
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_inbox_excludes_completed_deleted_and_scheduled_tasks(client: TestClient) -> None:
    pending = create_task(client, "Inbox pending")
    completed = create_task(client, "Inbox completed")
    assert client.post(
        f"/api/v1/tasks/{completed['id']}/complete", json={"version": 1}
    ).status_code == 200
    deleted = create_task(client, "Inbox deleted")
    assert client.request(
        "DELETE", f"/api/v1/tasks/{deleted['id']}", json={"version": 1}
    ).status_code == 204
    create_task(client, "Scheduled task", planned_date="2026-09-26")

    response = client.get("/api/v1/tasks?inbox=true")
    assert response.status_code == 200
    assert [task["id"] for task in response.json()] == [pending["id"]]


def test_priority_category_tags_and_single_patch_version(client: TestClient) -> None:
    category = client.post("/api/v1/categories", json={"name": "Learning"}).json()
    second_category = client.post(
        "/api/v1/categories", json={"name": "Projects"}
    ).json()
    first_tag = client.post("/api/v1/tags", json={"name": "linux"}).json()
    second_tag = client.post("/api/v1/tags", json={"name": "python"}).json()

    created = create_task(
        client,
        "Organize lab notes",
        priority="low",
        category_id=category["id"],
        tag_ids=[first_tag["id"]],
    )
    assert created["priority"] == "low"
    assert created["category"]["id"] == category["id"]
    assert [tag["id"] for tag in created["tags"]] == [first_tag["id"]]

    response = client.patch(
        f"/api/v1/tasks/{created['id']}?version=1",
        json={
            "title": "Organize updated lab notes",
            "priority": "high",
            "category_id": second_category["id"],
            "tag_ids": [second_tag["id"]],
        },
    )
    assert response.status_code == 200, response.text
    updated = response.json()
    assert updated["version"] == 2
    assert updated["priority"] == "high"
    assert updated["category"]["id"] == second_category["id"]
    assert [tag["id"] for tag in updated["tags"]] == [second_tag["id"]]


def test_invalid_relationship_rolls_back_all_task_changes(client: TestClient) -> None:
    category = client.post("/api/v1/categories", json={"name": "Study"}).json()
    created = create_task(client, "Rollback relationship update")

    response = client.patch(
        f"/api/v1/tasks/{created['id']}?version=1",
        json={
            "priority": "high",
            "category_id": category["id"],
            "tag_ids": [str(uuid4())],
        },
    )
    assert response.status_code == 404
    assert response.json()["error"]["code"] == "tag_not_found"

    unchanged = client.get(f"/api/v1/tasks/{created['id']}").json()
    assert unchanged["version"] == 1
    assert unchanged["priority"] == "normal"
    assert unchanged["category"] is None
    assert unchanged["tags"] == []


def test_category_and_tag_names_are_trimmed_and_case_insensitive(
    client: TestClient,
) -> None:
    category = client.post("/api/v1/categories", json={"name": "  Learning  "})
    assert category.status_code == 201
    assert category.json()["name"] == "Learning"
    duplicate_category = client.post(
        "/api/v1/categories", json={"name": "learning"}
    )
    assert duplicate_category.status_code == 409
    assert duplicate_category.json()["error"]["code"] == "category_name_conflict"

    tag = client.post("/api/v1/tags", json={"name": "  Linux  "})
    assert tag.status_code == 201
    assert tag.json()["name"] == "Linux"
    duplicate_tag = client.post("/api/v1/tags", json={"name": "linux"})
    assert duplicate_tag.status_code == 409
    assert duplicate_tag.json()["error"]["code"] == "tag_name_conflict"


def test_category_and_tag_can_be_updated(client: TestClient) -> None:
    category = client.post("/api/v1/categories", json={"name": "Old category"}).json()
    tag = client.post("/api/v1/tags", json={"name": "old-tag"}).json()

    category_response = client.patch(
        f"/api/v1/categories/{category['id']}", json={"name": "New category"}
    )
    tag_response = client.patch(
        f"/api/v1/tags/{tag['id']}", json={"name": "new-tag"}
    )

    assert category_response.status_code == 200
    assert category_response.json()["name"] == "New category"
    assert tag_response.status_code == 200
    assert tag_response.json()["name"] == "new-tag"


def test_deleting_category_and_tag_updates_each_task_once(
    client: TestClient,
    session_factory: sessionmaker[Session],
) -> None:
    category = client.post("/api/v1/categories", json={"name": "Remove me"}).json()
    tag = client.post("/api/v1/tags", json={"name": "temporary"}).json()
    active = create_task(
        client,
        "Active relationship task",
        category_id=category["id"],
        tag_ids=[tag["id"]],
    )
    deleted = create_task(
        client,
        "Deleted relationship task",
        category_id=category["id"],
        tag_ids=[tag["id"]],
    )
    assert client.request(
        "DELETE", f"/api/v1/tasks/{deleted['id']}", json={"version": 1}
    ).status_code == 204

    assert client.delete(f"/api/v1/categories/{category['id']}").status_code == 204
    with session_factory() as session:
        active_row = session.scalar(select(Task).where(Task.id == active["id"]))
        deleted_row = session.scalar(select(Task).where(Task.id == deleted["id"]))
        assert active_row is not None and deleted_row is not None
        assert active_row.version == 2
        assert deleted_row.version == 3
        assert active_row.category_id is None
        assert deleted_row.category_id is None

    assert client.delete(f"/api/v1/tags/{tag['id']}").status_code == 204
    with session_factory() as session:
        active_row = session.scalar(select(Task).where(Task.id == active["id"]))
        deleted_row = session.scalar(select(Task).where(Task.id == deleted["id"]))
        assert active_row is not None and deleted_row is not None
        assert active_row.version == 3
        assert deleted_row.version == 4
        assert active_row.tags == []
        assert deleted_row.tags == []


def test_search_uses_literal_like_query_and_structured_filters(
    client: TestClient,
) -> None:
    category = client.post("/api/v1/categories", json={"name": "Learning"}).json()
    tag = client.post("/api/v1/tags", json={"name": "linux"}).json()
    matching = create_task(
        client,
        "Linux notes",
        description="Review networking",
        category_id=category["id"],
        tag_ids=[tag["id"]],
    )
    create_task(client, "100% ready")
    deleted = create_task(client, "Linux deleted")
    assert client.request(
        "DELETE", f"/api/v1/tasks/{deleted['id']}", json={"version": 1}
    ).status_code == 204

    response = client.get("/api/v1/tasks?q=linux")
    assert [task["id"] for task in response.json()] == [matching["id"]]

    wildcard_response = client.get("/api/v1/tasks?q=100%")
    assert [task["title"] for task in wildcard_response.json()] == ["100% ready"]

    filtered = client.get(
        f"/api/v1/tasks?category_id={category['id']}&tag_id={tag['id']}&priority=normal"
    )
    assert [task["id"] for task in filtered.json()] == [matching["id"]]
