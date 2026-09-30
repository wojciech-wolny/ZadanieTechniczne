# REST API

Base URL `http://127.0.0.1:8000`. Every resource lives under `/api/v1` (API-6). Interactive docs stay at `/docs` unless `DOCS_ENABLED` is `false`. A later API version adds a new prefix and leaves these paths unchanged.

## Endpoints

| Method | Path | Request | Response | Status |
|--------|------|---------|----------|--------|
| POST | `/api/v1/tasks` | `TaskCreate` | `TaskRead` | 201, 422, 409 when the task limit is reached, 413 when the body is too large |
| GET | `/api/v1/tasks` | | `list[TaskRead]` | 200 |
| GET | `/api/v1/tasks/{task_id}` | | `TaskRead` | 200, 404 |
| DELETE | `/api/v1/tasks/{task_id}` | | empty | 204, 404 |
| GET | `/api/v1/stream` | | `StreamRead` | 200 |

`DELETE` stops and removes the task in one step (API-4); a removed task is gone from the list.

## Models

```python
class PassthroughConfig(BaseModel):
    name: Literal["passthrough"]


class AverageConfig(BaseModel):
    name: Literal["average"]
    window_size: int = Field(ge=1, le=100_000)


class LinearRegressionConfig(BaseModel):
    name: Literal["linear_regression"]
    window_size: int = Field(ge=2, le=100_000)


AlgorithmConfig = Annotated[
    PassthroughConfig | AverageConfig | LinearRegressionConfig,
    Field(discriminator="name"),
]


class TaskCreate(BaseModel):
    algorithm: AlgorithmConfig
    sink: Literal["null", "stdout"] = "null"


class TaskRead(BaseModel):
    task_id: str
    algorithm: AlgorithmConfig
    sink: str
    status: Literal["running", "failed"]
    created_at: datetime
    statistics: dict[str, float | int | None]
    error: str | None


class StreamRead(BaseModel):
    producer_connected: bool
    samples_received: int
```

`window_size` is the parameter `N` from the task. Unknown algorithm or sink names, invalid sizes and unknown fields (`extra="forbid"`) are rejected with 422 by Pydantic. A new component requires a configuration model and registry entry so it is represented explicitly in generated OpenAPI.

Task IDs are UUID4 values serialized as lowercase strings. `created_at` is an
RFC 3339 UTC timestamp. `GET /api/v1/tasks` returns tasks in creation order.

## Examples

```http
POST /api/v1/tasks
{"algorithm": {"name": "average", "window_size": 6}, "sink": "stdout"}
```

```http
201 Created
{
  "task_id": "3f2b0c9e-5d5a-4c49-a1c3-b0d1e8f4a2b7",
  "algorithm": {"name": "average", "window_size": 6},
  "sink": "stdout",
  "status": "running",
  "created_at": "2026-09-28T19:47:00Z",
  "statistics": {"samples_processed": 0, "windows_processed": 0, "last_result": null},
  "error": null
}
```

The POST becomes active when the new task has been inserted into the registry. It
receives samples from subsequent dispatches and never joins an in-progress dispatch.
DELETE takes effect before the next dispatch.

## Statistics per algorithm

| Algorithm | Keys |
|-----------|------|
| passthrough | `samples_processed` |
| average | `samples_processed`, `windows_processed`, `last_result` |
| linear_regression | `samples_processed`, `windows_processed`, `last_slope`, `min_slope`, `max_slope` |

Values not yet available are `null`.

## Errors

Client errors use FastAPI's `{"detail": ...}` shape:

| Status | Detail |
|--------|--------|
| 404 | `"Task not found"` |
| 409 | `"Task limit reached"` |
| 413 | `"Request body too large"`, for any request body above 16384 bytes |
| 422 | Pydantic validation details, including a `window_size` that is not a JSON integer |

An algorithm or sink exception changes that task to `failed`; the task remains in GET
responses until deleted. `error` contains only the exception class name, with no message,
traceback or internal path. A failed task still counts toward the task limit until it is deleted.

`/api/v1/stream` field `samples_received` counts finite samples accepted since server startup and
does not reset when a Producer disconnects.
