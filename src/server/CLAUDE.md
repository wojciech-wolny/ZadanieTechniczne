# Processing Server context

Use this file when changing anything under `src/server/`. The repository map is `CLAUDE.md`.

`services/` never imports FastAPI. Routes stay thin: validate with Pydantic, call the registry, map errors to status codes.

## Runtime

`create_app` in `src/server/main.py` builds the app from `Settings`. `run_lifespan` creates one `TaskRegistry` and one `SampleReceiver`, stores both on `app.state`, stops the receiver on shutdown, then calls `TaskRegistry.close_all` so every stored task closes its sink. `TaskLimitError` becomes HTTP 409 with `{"detail": "Task limit reached"}`.

`create_app` calls `load_env_file` before `Settings()`. `Settings` reads the process environment. `.env.example` is not loaded. Hosts and ports have no literal default in Python.

| Setting | Value in the example `.env` | Bound |
|---------|-------------------------|-------|
| `HTTP_HOST` / `HTTP_PORT` | `127.0.0.1:8000` | host non empty |
| `TCP_HOST` / `TCP_PORT` | `127.0.0.1:9000` | same |
| `MAX_TASKS` | 32 | at least 1 |
| `PRODUCER_IDLE_SECONDS` | 30 | above 0 |
## Sample path

1. `SampleReceiver` accepts one producer. Further connections are closed. Reads are 64 KiB. Idle longer than `producer_idle_seconds` closes the socket.
2. `SampleDecoder.decode` prepends the remainder, unpacks complete `<d` samples, and stores a tail shorter than 8 bytes. NaN or infinity raises `NonFiniteSampleError` with the finite samples decoded before it, clears the remainder, and the receiver closes that connection after dispatching those finite samples.
3. `discard_remainder` runs on disconnect. The next connection continues the same decoder instance only for new bytes. Windows already stored in algorithms stay.
4. `TaskRegistry.dispatch` delivers that list to running tasks.

## TaskRegistry

`src/server/services/registry.py`. Insertion order is creation order. Failed tasks stay until `remove_task`.

| Method | Contract |
|--------|----------|
| `create_task` | Raises `TaskLimitError` when `len(tasks) >= max_tasks`. Otherwise `ProcessingTask.create`, then store. |
| `find_task` | Returns the task, or `None` when the id is absent. The API turns `None` into 404. |
| `list_tasks` | Oldest to newest, including `failed`. |
| `remove_task` | Pops the task, then `close_sink`. Unknown id returns `None`. |
| `dispatch` | Copies tasks whose `status == "running"` first. Then calls `process_samples` on that copy. A task created during this call waits for the next dispatch. The copy, the per task call, and the sink close are separate methods. |

On `process_samples` failure, `dispatch` calls `record_failure(type(error).__name__)` and `close_sink`. A sink close error is logged and does not stop the remaining tasks. The stored error is the exception class name, with no traceback.

## ProcessingTask

`ProcessingTask.create` builds a lowercase UUID4, looks up `ALGORITHM_FACTORIES` and `SINK_FACTORIES`, and starts `status="running"`. `process_samples` counts every sample, including ones that emit no result, then writes one batch when any result is present. `close_sink` runs once. `read_statistics` always includes `samples_processed` plus the algorithm map. Missing statistics are `None`, which the API serializes as `null`.

## Algorithms and sinks

`Algorithm.process_sample` returns `float | None`. `None` means no result yet. `WindowAlgorithm` emits once per non overlapping window and clears the window. An incomplete window emits nothing.

`average` uses `window_size` from 1 to 100000 and reports `windows_processed`, `last_result`. `linear_regression` uses `window_size` from 2 to 100000, slope at x = 0..N-1 via `calculate_slope`, and reports `windows_processed`, `last_slope`, `min_slope`, `max_slope`.

`StdoutSink` rounds with Python `round`. Codes 0 through 127 become that character. Every other value, including a non finite result, becomes `#`.

## REST

Router prefix `/tasks` and `/stream`, mounted at `/api/v1`.

| Call | Success | Other |
|------|---------|-------|
| `POST /tasks` | 201 `TaskRead` | 409 limit, 422 invalid body |
| `GET /tasks` | 200 list | |
| `GET /tasks/{task_id}` | 200 | 404 `{"detail": "Task not found"}` |
| `DELETE /tasks/{task_id}` | 204 empty | 404 |
| `GET /stream` | 200 `producer_connected`, `samples_received` | |

`samples_received` counts finite samples dispatched since process start. It stays across disconnects. Task ids come from the server. Unknown JSON fields fail validation because models use `extra="forbid"`.
