from __future__ import annotations

from fastapi.testclient import TestClient
from sqlalchemy import select
from sqlalchemy.orm import Session, sessionmaker

from app.models.project import Project
from app.models.task import Task


def create_project(
    client: TestClient,
    name: str = "Linux learning",
    description: str | None = None,
) -> dict:
    response = client.post(
        "/api/v1/projects",
        json={"name": name, "description": description},
    )
    assert response.status_code == 201, response.text
    return response.json()


def create_task(
    client: TestClient,
    title: str,
    *,
    project_id: str | None = None,
    planned_date: str | None = None,
    **extra: object,
) -> dict:
    payload: dict[str, object] = {
        "title": title,
        "planned_date": planned_date,
        **extra,
    }
    if project_id is not None:
        payload["project_id"] = project_id
    response = client.post("/api/v1/tasks", json=payload)
    assert response.status_code == 201, response.text
    return response.json()


def test_project_crud_progress_and_status_are_independent(client: TestClient) -> None:
    project = create_project(client, description="Build a reliable study plan")
    assert project["status"] == "active"
    assert project["task_count"] == 0
    assert project["completed_task_count"] == 0
    assert project["progress_percent"] == 0
    assert project["version"] == 1
    assert project["created_at_utc"].endswith("Z")

    first = create_task(client, "Read Linux notes", project_id=project["id"])
    second = create_task(client, "Practice networking", project_id=project["id"])
    assert first["project"]["id"] == project["id"]
    assert second["project"]["name"] == project["name"]

    completed_task = client.post(
        f"/api/v1/tasks/{first['id']}/complete", json={"version": 1}
    )
    assert completed_task.status_code == 200
    project_after_task = client.get(f"/api/v1/projects/{project['id']}").json()
    assert project_after_task["status"] == "active"
    assert project_after_task["task_count"] == 2
    assert project_after_task["completed_task_count"] == 1
    assert project_after_task["progress_percent"] == 50

    completed_project = client.post(
        f"/api/v1/projects/{project['id']}/complete", json={"version": 1}
    )
    assert completed_project.status_code == 200
    assert completed_project.json()["status"] == "completed"
    assert completed_project.json()["version"] == 2
    assert client.get(f"/api/v1/tasks/{second['id']}").json()["status"] == "pending"

    reopened = client.post(
        f"/api/v1/projects/{project['id']}/reopen", json={"version": 2}
    )
    assert reopened.status_code == 200
    assert reopened.json()["status"] == "active"
    assert reopened.json()["completed_at_utc"] is None
    assert reopened.json()["version"] == 3

    updated = client.patch(
        f"/api/v1/projects/{project['id']}?version=3",
        json={"description": "Updated description"},
    )
    assert updated.status_code == 200
    assert updated.json()["description"] == "Updated description"
    assert updated.json()["version"] == 4


def test_project_names_are_trimmed_unique_and_restore_conflicts(client: TestClient) -> None:
    project = create_project(client, "  Linux  ")
    assert project["name"] == "Linux"

    duplicate = client.post("/api/v1/projects", json={"name": "linux"})
    assert duplicate.status_code == 409
    assert duplicate.json()["error"]["code"] == "project_name_conflict"

    empty = client.post("/api/v1/projects", json={"name": "   "})
    assert empty.status_code == 422
    assert empty.json()["error"]["code"] == "validation_error"

    deleted = client.request(
        "DELETE",
        f"/api/v1/projects/{project['id']}", json={"version": project["version"]}
    )
    assert deleted.status_code == 204

    replacement = create_project(client, "Linux")
    restore = client.post(
        f"/api/v1/projects/{project['id']}/restore", json={"version": 2}
    )
    assert restore.status_code == 409
    assert restore.json()["error"]["code"] == "project_name_conflict"
    assert client.get(f"/api/v1/projects/{project['id']}").status_code == 404
    assert client.get(f"/api/v1/projects/{replacement['id']}").json()["name"] == "Linux"


def test_task_project_assignment_clear_filter_and_deleted_project_validation(
    client: TestClient,
) -> None:
    project = create_project(client, "Project filter")
    other_project = create_project(client, "Other project")
    task = create_task(client, "Unassigned task")

    assigned = client.patch(
        f"/api/v1/tasks/{task['id']}?version=1",
        json={"project_id": project["id"]},
    )
    assert assigned.status_code == 200
    assert assigned.json()["project_id"] == project["id"]
    assert assigned.json()["project"]["id"] == project["id"]
    assert assigned.json()["version"] == 2

    filtered = client.get(f"/api/v1/tasks?project_id={project['id']}")
    assert filtered.status_code == 200
    assert [item["id"] for item in filtered.json()] == [task["id"]]

    preserved = client.patch(
        f"/api/v1/tasks/{task['id']}?version=2",
        json={"title": "Still assigned"},
    )
    assert preserved.status_code == 200
    assert preserved.json()["project_id"] == project["id"]
    assert preserved.json()["version"] == 3

    cleared = client.patch(
        f"/api/v1/tasks/{task['id']}?version=3",
        json={"project_id": None},
    )
    assert cleared.status_code == 200
    assert cleared.json()["project_id"] is None
    assert cleared.json()["project"] is None
    assert cleared.json()["version"] == 4
    assert client.get(f"/api/v1/tasks?project_id={project['id']}").json() == []

    deleted_project = client.request(
        "DELETE",
        f"/api/v1/projects/{other_project['id']}", json={"version": 1}
    )
    assert deleted_project.status_code == 204
    invalid_assignment = client.patch(
        f"/api/v1/tasks/{task['id']}?version=4",
        json={"title": "Must roll back", "project_id": other_project["id"]},
    )
    assert invalid_assignment.status_code == 404
    assert invalid_assignment.json()["error"]["code"] == "project_not_found"
    unchanged = client.get(f"/api/v1/tasks/{task['id']}").json()
    assert unchanged["title"] == "Still assigned"
    assert unchanged["project_id"] is None
    assert unchanged["version"] == 4


def test_project_delete_clears_active_and_soft_deleted_task_relationships(
    client: TestClient,
    session_factory: sessionmaker[Session],
) -> None:
    project = create_project(client, "Delete relationship project")
    active = create_task(client, "Active project task", project_id=project["id"])
    deleted = create_task(client, "Deleted project task", project_id=project["id"])
    assert client.request(
        "DELETE", f"/api/v1/tasks/{deleted['id']}", json={"version": 1}
    ).status_code == 204

    response = client.request(
        "DELETE",
        f"/api/v1/projects/{project['id']}", json={"version": project["version"]}
    )
    assert response.status_code == 204
    assert client.get(f"/api/v1/projects/{project['id']}").status_code == 404

    with session_factory() as session:
        active_row = session.scalar(select(Task).where(Task.id == active["id"]))
        deleted_row = session.scalar(select(Task).where(Task.id == deleted["id"]))
        assert active_row is not None and deleted_row is not None
        assert active_row.project_id is None
        assert deleted_row.project_id is None
        assert active_row.version == 2
        assert deleted_row.version == 3

    restored = client.post(
        f"/api/v1/projects/{project['id']}/restore", json={"version": 2}
    )
    assert restored.status_code == 200
    assert restored.json()["version"] == 3
    assert restored.json()["task_count"] == 0
    assert client.get(f"/api/v1/tasks/{active['id']}").json()["project_id"] is None


def test_progress_excludes_deleted_tasks_and_empty_projects_are_zero(
    client: TestClient,
) -> None:
    empty = create_project(client, "Empty project")
    assert client.get(f"/api/v1/projects/{empty['id']}").json()["progress_percent"] == 0

    project = create_project(client, "Progress project")
    pending = create_task(client, "Pending", project_id=project["id"])
    completed = create_task(client, "Completed", project_id=project["id"])
    deleted = create_task(client, "Deleted", project_id=project["id"])
    assert client.post(
        f"/api/v1/tasks/{completed['id']}/complete", json={"version": 1}
    ).status_code == 200
    assert client.request(
        "DELETE", f"/api/v1/tasks/{deleted['id']}", json={"version": 1}
    ).status_code == 204

    project_read = client.get(f"/api/v1/projects/{project['id']}")
    assert project_read.status_code == 200
    assert project_read.json()["task_count"] == 2
    assert project_read.json()["completed_task_count"] == 1
    assert project_read.json()["progress_percent"] == 50
    assert pending["project_id"] == project["id"]


def test_project_tasks_keep_inbox_today_and_calendar_semantics(
    client: TestClient,
) -> None:
    project = create_project(client, "Existing view semantics")
    inbox_task = create_task(client, "Project inbox task", project_id=project["id"])
    today_task = create_task(
        client,
        "Project today task",
        project_id=project["id"],
        planned_date="2026-09-26",
    )

    inbox = client.get("/api/v1/tasks?inbox=true")
    assert inbox.status_code == 200
    assert [task["id"] for task in inbox.json()] == [inbox_task["id"]]

    today = client.get("/api/v1/today?date=2026-09-26")
    assert today.status_code == 200
    assert [task["id"] for task in today.json()] == [today_task["id"]]
    assert today.json()[0]["project"]["id"] == project["id"]

    calendar = client.get("/api/v1/calendar?start=2026-09-26&end=2026-09-26")
    assert calendar.status_code == 200
    assert [task["id"] for task in calendar.json()] == [today_task["id"]]


def test_project_list_status_filter_and_soft_deleted_projects_are_hidden(
    client: TestClient,
) -> None:
    active = create_project(client, "Active project")
    completed = create_project(client, "Completed project")
    assert client.post(
        f"/api/v1/projects/{completed['id']}/complete", json={"version": 1}
    ).status_code == 200
    deleted = create_project(client, "Deleted project")
    assert client.request(
        "DELETE",
        f"/api/v1/projects/{deleted['id']}", json={"version": 1}
    ).status_code == 204

    active_projects = client.get("/api/v1/projects?status=active")
    assert active_projects.status_code == 200
    assert {item["id"] for item in active_projects.json()} == {active["id"]}
    completed_projects = client.get("/api/v1/projects?status=completed")
    assert completed_projects.status_code == 200
    assert {item["id"] for item in completed_projects.json()} == {completed["id"]}
    assert deleted["id"] not in {
        item["id"] for item in client.get("/api/v1/projects").json()
    }


def test_project_list_include_deleted_supports_restore_without_mutation(
    client: TestClient,
) -> None:
    active = create_project(client, "Visible active project")
    completed = create_project(client, "Visible completed project")
    assert client.post(
        f"/api/v1/projects/{completed['id']}/complete", json={"version": 1}
    ).status_code == 200
    deleted = create_project(client, "Restorable project")
    assert client.request(
        "DELETE", f"/api/v1/projects/{deleted['id']}", json={"version": 1}
    ).status_code == 204

    default_projects = client.get("/api/v1/projects")
    assert default_projects.status_code == 200
    assert deleted["id"] not in {item["id"] for item in default_projects.json()}

    included = client.get("/api/v1/projects?include_deleted=true")
    assert included.status_code == 200
    included_by_id = {item["id"]: item for item in included.json()}
    assert set(included_by_id) == {active["id"], completed["id"], deleted["id"]}
    deleted_read = included_by_id[deleted["id"]]
    assert deleted_read["version"] == 2
    assert deleted_read["deleted_at_utc"] is not None

    active_included = client.get(
        "/api/v1/projects?status=active&include_deleted=true"
    )
    assert {item["id"] for item in active_included.json()} == {
        active["id"],
        deleted["id"],
    }
    completed_included = client.get(
        "/api/v1/projects?status=completed&include_deleted=true"
    )
    assert {item["id"] for item in completed_included.json()} == {completed["id"]}

    unchanged = client.get("/api/v1/projects?include_deleted=true").json()
    unchanged_deleted = next(
        item for item in unchanged if item["id"] == deleted["id"]
    )
    assert unchanged_deleted["version"] == deleted_read["version"]
    assert unchanged_deleted["deleted_at_utc"] == deleted_read["deleted_at_utc"]

    restored = client.post(
        f"/api/v1/projects/{deleted['id']}/restore", json={"version": 2}
    )
    assert restored.status_code == 200
    assert restored.json()["deleted_at_utc"] is None
    assert restored.json()["version"] == 3
    assert deleted["id"] in {
        item["id"] for item in client.get("/api/v1/projects").json()
    }


def test_project_optimistic_version_and_task_patch_progression(
    client: TestClient,
) -> None:
    project = create_project(client, "Version project")
    stale_project_update = client.patch(
        f"/api/v1/projects/{project['id']}?version=1",
        json={"name": "Renamed project"},
    )
    assert stale_project_update.status_code == 200
    assert stale_project_update.json()["version"] == 2

    conflict = client.patch(
        f"/api/v1/projects/{project['id']}?version=1",
        json={"description": "Must not overwrite"},
    )
    assert conflict.status_code == 409
    assert conflict.json()["error"]["code"] == "project_version_conflict"
    unchanged = client.get(f"/api/v1/projects/{project['id']}").json()
    assert unchanged["description"] is None
    assert unchanged["version"] == 2

    task = create_task(client, "One combined task patch")
    combined = client.patch(
        f"/api/v1/tasks/{task['id']}?version=1",
        json={
            "title": "Updated combined task",
            "priority": "high",
            "project_id": project["id"],
        },
    )
    assert combined.status_code == 200
    assert combined.json()["version"] == 2
    assert combined.json()["priority"] == "high"
    assert combined.json()["project_id"] == project["id"]

    stale_delete = client.request(
        "DELETE",
        f"/api/v1/projects/{project['id']}", json={"version": 1}
    )
    assert stale_delete.status_code == 409
    assert stale_delete.json()["error"]["code"] == "project_version_conflict"
    after_stale_delete = client.get(f"/api/v1/tasks/{task['id']}").json()
    assert after_stale_delete["project_id"] == project["id"]
    assert after_stale_delete["version"] == 2


def test_project_foreign_key_sets_task_project_to_null(
    client: TestClient,
    session_factory: sessionmaker[Session],
) -> None:
    project = create_project(client, "Foreign key project")
    task = create_task(client, "Foreign key task", project_id=project["id"])

    with session_factory() as session:
        project_row = session.scalar(select(Project).where(Project.id == project["id"]))
        assert project_row is not None
        session.delete(project_row)
        session.commit()

    with session_factory() as session:
        task_row = session.scalar(select(Task).where(Task.id == task["id"]))
        assert task_row is not None
        assert task_row.project_id is None
