# API

## Base Path

```text
/api/v1
```

## V0.1 Endpoints

- `GET /healthz`
- `POST /api/v1/tasks`
- `GET /api/v1/tasks`
- `GET /api/v1/tasks/{id}`
- `PATCH /api/v1/tasks/{id}`
- `DELETE /api/v1/tasks/{id}` — Soft Delete
- `POST /api/v1/tasks/{id}/complete`
- `POST /api/v1/tasks/{id}/restore`
- `GET /api/v1/today?date=YYYY-MM-DD`

Mutation requests include the current `version` for optimistic concurrency control.

## Task Payloads

Create:

```json
{
  "title": "Study Linux networking",
  "description": "Review the lab notes",
  "planned_date": "2026-09-26"
}
```

`title` is required and is trimmed. `description` and `planned_date` may be
`null`.

Patch uses the current version as a query parameter:

```text
PATCH /api/v1/tasks/{id}?version=1
```

The body may contain any of `title`, `description`, and `planned_date`. Complete,
restore, and delete use a JSON body such as `{ "version": 1 }`.

## Status and Responses

The only V0.1 statuses are `pending` and `completed`. A successful mutation
increments `version`, except for an idempotent no-op. Delete returns `204` and
sets `deleted_at_utc`; it does not physically remove the row.

Errors use this shape:

```json
{
  "error": {
    "code": "task_version_conflict",
    "message": "Task changed since it was loaded; refresh before saving",
    "details": {}
  }
}
```

Important codes include `validation_error`, `task_not_found`,
`task_version_conflict`, `database_error`, and `internal_error`.
