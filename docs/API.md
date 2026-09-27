# API

## Base Path

```text
/api/v1
```

## Current System Endpoint

```http
GET /healthz
```

`/healthz` remains a lightweight liveness endpoint. Frontend runtime timezone
information is provided by the separate read-only endpoint below.

## Runtime Endpoint

```http
GET /api/v1/runtime
```

Response:

```json
{
  "timezone": "Asia/Shanghai",
  "local_date": "2026-09-26"
}
```

`timezone` is the configured IANA timezone. `local_date` is calculated by the
Backend in that timezone. Frontend “今天” logic must use this runtime value
instead of the browser's local date.

## V0.1 Endpoints

- `POST /api/v1/tasks`
- `GET /api/v1/tasks`
- `GET /api/v1/tasks/{id}`
- `PATCH /api/v1/tasks/{id}`
- `DELETE /api/v1/tasks/{id}` — Soft Delete
- `POST /api/v1/tasks/{id}/complete`
- `POST /api/v1/tasks/{id}/restore`
- `GET /api/v1/today?date=YYYY-MM-DD`

Mutation requests include the current `version` for optimistic concurrency
control. Existing request and response behavior remains compatible.

## V0.2 Endpoints and Filters

The existing Task paths remain unchanged. Task listing accepts:

```text
GET /api/v1/tasks?inbox=true
GET /api/v1/tasks?q=linux
GET /api/v1/tasks?priority=high
GET /api/v1/tasks?category_id=<uuid>&tag_id=<uuid>
```

`inbox=true` returns only pending, active Tasks with `planned_date = null`.
`q` is trimmed, parameterized, and searches title and description. Percent and
underscore are treated as literal characters. Category, Tag, and Priority are
structured filters.

Task Create and Patch accept:

```json
{
  "priority": "normal",
  "category_id": "<uuid-or-null>",
  "tag_ids": ["<uuid>"]
}
```

One Task Patch that changes multiple fields or relationships increments
`version` once. Relationship IDs are validated before any mutation; failures
roll back the entire transaction.

Category resources:

```text
GET    /api/v1/categories
POST   /api/v1/categories
PATCH  /api/v1/categories/{id}
DELETE /api/v1/categories/{id}
```

Tag resources:

```text
GET    /api/v1/tags
POST   /api/v1/tags
PATCH  /api/v1/tags/{id}
DELETE /api/v1/tags/{id}
```

## V0.3 Phase 1 Calendar API

V0.3 Phase 1 adds one read-only Calendar range endpoint:

```http
GET /api/v1/calendar?start=2026-09-21&end=2026-09-27
```

Rules:

- `start` and `end` are inclusive local dates in the configured runtime
  timezone.
- `start > end` returns HTTP 422.
- The initial implementation limits the range to a practical bounded window,
  such as 62 days.
- Soft-deleted Tasks are excluded.
- Completed Tasks remain visible, matching current Today behavior.
- Date-only Tasks and scheduled Tasks are both returned.
- The endpoint reuses the Task service and `TaskRead` representation; it does
  not create a second Task CRUD system.

Day, Week, and Month views calculate their local date range and call this same
endpoint. The frontend uses a Day range for Day View, seven dates for Week
View, and the visible month grid range for Month View; all stay within the
Backend's 62-day limit.

## V0.3 Phase 1 Task Schedule Write API

Task Create and Patch gain one structured `schedule` field:

```json
{
  "planned_date": "2026-09-26",
  "schedule": {
    "start_time": "14:00",
    "end_time": "15:00",
    "timezone": "Asia/Shanghai"
  }
}
```

`timezone` is optional. If omitted, the Backend uses `DAYFLOW_TIMEZONE`.
The value must be a valid IANA timezone when supplied.

### Partial Update Semantics

- `schedule` omitted: preserve the existing Time Block.
- `schedule: null`: clear the Time Block and preserve `planned_date` by
  default.
- `planned_date: null` plus `schedule: null`: clear the schedule and return the
  Task to Inbox.
- Changing only `planned_date` for a scheduled Task preserves local start/end
  clock times in the stored `schedule_timezone` and recalculates UTC instants.

The API response adds these nullable fields to `TaskRead`:

```json
{
  "start_at_utc": "2026-09-26T06:00:00.000000Z",
  "end_at_utc": "2026-09-26T07:00:00.000000Z",
  "schedule_timezone": "Asia/Shanghai"
}
```

When no Time Block exists, all three values are `null`.

The Backend must enforce:

- A Time Block requires `planned_date`.
- The start and end values are both present.
- The end is later than the start.
- `planned_date` equals the local date of the start instant in
  `schedule_timezone`.
- V0.3 Time Blocks do not cross a local date.
- DST ambiguous or nonexistent local times return HTTP 422.

## Conflict Handling

The Backend checks a new or changed Time Block against active, pending,
non-deleted Tasks using UTC intervals.

When overlap is found, the default response is:

```http
409 Conflict
```

```json
{
  "error": {
    "code": "schedule_conflict",
    "message": "The requested time overlaps another task",
    "details": {
      "task_ids": ["..."]
    }
  }
}
```

The user may explicitly confirm the overlap by retrying the same mutation with
the one-request query flag:

```text
PATCH /api/v1/tasks/{id}?version=3&allow_schedule_conflict=true
```

The flag is not persisted. The Backend never automatically moves or reschedules
another Task.

Conflict and stale-version failures are atomic: no Task field, relationship,
Time Block, or version may be partially changed.

## Date and Time Serialization

- Date-only values use `YYYY-MM-DD`.
- Stored and returned instants use RFC3339 UTC strings ending in `Z`.
- IANA timezone names use values such as `Asia/Shanghai`.
- The API does not treat `planned_date` as a UTC date.
- Frontend must not parse a date-only value through JavaScript UTC conversion.

## Error Contract

Errors use the existing envelope:

```json
{
  "error": {
    "code": "task_version_conflict",
    "message": "Task changed since it was loaded; refresh before saving",
    "details": {}
  }
}
```

V0.3 Phase 1 adds or uses:

- `schedule_validation_error` — invalid date/time, timezone, or schedule state.
- `calendar_range_invalid` — invalid or oversized Calendar date range.
- `schedule_conflict` — overlapping active pending Task.
- `task_version_conflict` — stale optimistic version.
- `task_not_found` — missing or inaccessible Task.

## Transaction and Version Rules

Task fields, relationships, and schedule changes in one PATCH execute in one
transaction. Any validation, conflict, or stale-version failure rolls back all
changes.

One successful Task PATCH increments `version` at most once, regardless of how
many fields and relationships change.
