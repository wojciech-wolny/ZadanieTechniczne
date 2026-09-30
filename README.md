# Streaming Data Processing

[![CI](https://github.com/wojciech-wolny/ZadanieTechniczne/actions/workflows/ci.yml/badge.svg)](https://github.com/wojciech-wolny/ZadanieTechniczne/actions/workflows/ci.yml)

A TCP **Producer** reads numeric samples from a file and streams them to a **Processing Server**. The server runs one or more tasks on that stream. Each task is an algorithm (`passthrough`, `average`, `linear_regression`) plus a sink (`null`, `stdout`). Tasks are created and removed through a REST API.

Design notes live in [docs/](docs/README.md). The original task is [`wytyczne/task_python_2608-0.2.md`](wytyczne/task_python_2608-0.2.md).

## Installation

Python 3.13.7 is pinned in `.python-version`. Install [uv](https://docs.astral.sh/uv/), then from the repository root:

```powershell
uv sync
```

`uv sync` creates the virtual environment, installs the locked dependencies, and installs the `producer` and `processing-server` commands.

## Start the Processing Server

```powershell
uv run processing-server
```

| Service | Default |
|---------|---------|
| HTTP API and docs | `http://127.0.0.1:8000` (`/docs` for the interactive API) |
| TCP sample stream | `127.0.0.1:9000` |

These environment variables override the defaults. Both applications bind to localhost unless you change the host.

| Variable | Default | Meaning |
|----------|---------|---------|
| `HTTP_HOST` | `127.0.0.1` | HTTP bind address, must not be empty |
| `HTTP_PORT` | `8000` | HTTP port |
| `TCP_HOST` | `127.0.0.1` | TCP bind address, must not be empty |
| `TCP_PORT` | `9000` | TCP port |
| `MAX_TASKS` | `32` | Maximum tasks kept at once, from 1 to 256 |
| `PRODUCER_IDLE_SECONDS` | `30` | Seconds without data before the Producer connection is closed. Finite, above 0, at most 3600. Keep it above 10 so a Producer at `--rate 0.1` stays connected |
| `DOCS_ENABLED` | `true` | Serve `/docs`, `/redoc` and `/openapi.json`. Set `false` to hide them |

A full window of 100000 samples takes about 3.2 MB, so 256 full tasks take about 820 MB and the default 32 take about 100 MB. HTTP request bodies above 16384 bytes are rejected with 413, and uvicorn accepts at most 64 concurrent connections.

Stdout task output is written to the server process, so watch that terminal.

## Start the Producer

```powershell
uv run producer wytyczne/passthrough.txt --format txt --rate 1000
```

| Option | Meaning | Default |
|--------|---------|---------|
| `input_file` | Path of the input file | required |
| `--format` | `txt` or `bin` | `txt` |
| `--rate` | Samples per second. Finite, from `0.1` to `1000000` | required |
| `--limit` | Samples to send, at most `sys.maxsize`. `0` repeats the file until you stop the process | `0` |
| `--host` | Processing Server host | `127.0.0.1` |
| `--port` | Processing Server TCP port | `9000` |

`txt` files contain whitespace separated numbers. `bin` files contain little endian float32 values (4 bytes each). The Producer reads the file in chunks, reopens it after each pass, and stops after `--limit` samples when the limit is greater than 0. Press Ctrl+C to stop an unlimited stream. A failed connection or a file that contains no samples exits with status 1.

Create a stdout task before starting the Producer if you want to see the decoded text. With the command above and a passthrough stdout task, the server prints `Passthrough - It works! ` and then repeats it.

## REST API

Every resource is under `/api/v1`. A later incompatible API would use a new prefix. `/docs` and `/openapi.json` stay unversioned and are served unless `DOCS_ENABLED` is `false`.

| Method | Path | Success | Other |
|--------|------|---------|-------|
| `POST` | `/api/v1/tasks` | 201 `TaskRead` | 409 when `MAX_TASKS` is reached, 413 when the body is larger than 16384 bytes, 422 when the body is invalid |
| `GET` | `/api/v1/tasks` | 200 list, oldest first | |
| `GET` | `/api/v1/tasks/{task_id}` | 200 `TaskRead` | 404 `{"detail": "Task not found"}` |
| `DELETE` | `/api/v1/tasks/{task_id}` | 204 empty body | 404 |
| `GET` | `/api/v1/stream` | 200 connection status | |

`POST` starts the task. It receives samples dispatched after it is stored. `DELETE` stops the task, closes its sink, and removes it.

PowerShell:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/v1/tasks -Method Post -ContentType application/json -Body '{"algorithm":{"name":"passthrough"},"sink":"stdout"}'
Invoke-RestMethod http://127.0.0.1:8000/api/v1/tasks
Invoke-RestMethod http://127.0.0.1:8000/api/v1/stream
Invoke-RestMethod http://127.0.0.1:8000/api/v1/tasks/TASK_ID -Method Delete
```

bash:

```bash
curl -s -X POST http://127.0.0.1:8000/api/v1/tasks \
  -H "Content-Type: application/json" \
  -d '{"algorithm": {"name": "average", "window_size": 6}, "sink": "stdout"}'
```

Algorithms:

| Name | Parameters | Result | Extra statistics |
|------|------------|--------|------------------|
| `passthrough` | none | each sample unchanged | none |
| `average` | `window_size` N from 1 to 100000 | mean of each non overlapping window | `windows_processed`, `last_result` |
| `linear_regression` | `window_size` N from 2 to 100000 | least squares slope of each window, x = 0..N-1 | `windows_processed`, `last_slope`, `min_slope`, `max_slope` |

Every task also reports `samples_processed`. Statistics that do not exist yet are `null`. An incomplete window produces nothing. Request bodies with unknown fields (for example a misspelled `sink`) are rejected with 422.

The `null` sink discards results. The `stdout` sink rounds each result with Python `round` and writes one character: values from 0 through 127 become that ASCII character, and anything else, including an infinite result, becomes `#`. For example, 10 is a newline, 65 is `A`, and 137 is `#`.

`GET /api/v1/stream` returns `producer_connected` and `samples_received`. The sample count is the number of finite samples accepted since the process started. It does not reset when a producer disconnects.

## TCP format

The Producer sends a raw stream of IEEE 754 float64 values, little endian (`struct` format `<d`, 8 bytes), with no header and no delimiter. The server reassembles samples from whatever chunk sizes TCP delivers. A partial trailing sample is discarded when the connection closes. NaN or infinity closes that connection after the finite samples before it are processed. The next Producer continues the same logical stream, including a window that was only partly filled. Details are in [docs/wire-protocol.md](docs/wire-protocol.md).

## Tests

```powershell
uv run ruff check .
uv run ruff format --check .
uv run pytest -q --html=report.html --self-contained-html
```

The suite does not need a server you start yourself. Integration and system tests bind a free local port.

## Demo

```powershell
uv run python scripts/demo.py
```

The script starts a server, runs each example configuration for one pass, and prints the decoded text:

| File | Task | Readable text |
|------|------|----------------|
| `wytyczne/passthrough.txt` | passthrough | `Passthrough - It works! ` |
| `wytyczne/example_text.txt` | passthrough | `Passthrough works: these samples are printed raw, with no filtering.` |
| `wytyczne/example_text.txt` | average, N = 6 | `Hello! Nice work :)` |
| `wytyczne/example_text.txt` | linear regression, N = 4 | `Congratulation! It is correct decoded data for linear regression` |
| `wytyczne/example_binary.f32` | passthrough | `Passthrough works on binary too: raw float32 samples, no filtering.` |

Other characters in the same output are noise from the rest of the file. That is expected.

## Assumptions

1. Text tokens are split on any whitespace. A token that is not a finite number is skipped. A token longer than 1024 characters is skipped so a broken file cannot grow memory without a bound. Each file pass logs one warning to stderr with the number of skipped tokens.
2. A binary file whose length is not a multiple of 4 bytes ignores the trailing bytes, with a warning. Non finite float32 values are skipped with one summary warning per pass.
3. If a full pass over the file yields no samples, the Producer stops with an error. This covers an empty file, a whitespace only file, a file of invalid tokens, and a binary file shorter than 4 bytes.
4. `rate` has no "as fast as possible" setting. The Producer sends the first batch immediately, then uses a monotonic clock. About 20 ms of samples are sent together. If the process falls behind, it sends immediately instead of accumulating delay.
5. The Producer does not reconnect and gives up connecting after 5 seconds. The server keeps running after a disconnect and accepts another Producer. A Producer that sends nothing for `PRODUCER_IDLE_SECONDS` is disconnected, and TCP keepalive is enabled on its socket. A rejected second Producer is logged once, then at most once every 10 seconds with a count.
6. ASCII rounding is bankers rounding. `65.5` becomes `B`, and `66.5` also becomes `B`.
7. A task is included in the next sample batch after creation. It never joins a batch that is already being processed, and samples from before creation are not replayed.
8. Deleting a task closes its sink. There is no paused state.
9. Task identifiers are server generated UUID4 strings. `created_at` is an RFC 3339 UTC timestamp.
10. Finite samples can still produce an infinite result, for example the average of `1e308` and `1e308`. JSON has no infinity, so such a statistic is reported as `null` even though `windows_processed` has increased.
11. A failed task keeps its place toward `MAX_TASKS` until it is deleted.
12. A text file may start with a UTF-8 byte order mark. It is ignored.

## Design decisions

1. One `uv` project exposes the `producer` and `processing-server` commands. The shared wire format lives in `common`.
2. The server is one asyncio process. FastAPI and the TCP receiver share the loop started by uvicorn. Registry updates and sample dispatch do not interleave.
3. Algorithms and sinks are selected from name registries. A new variant needs its own implementation, configuration model, and registry entry. Existing classes stay unchanged.
4. If one task raises, it is marked `failed`, its `error` field is the exception class name, and other tasks keep running. The failed task remains visible until it is deleted.
5. Window memory is bounded by `window_size` (at most 100000, about 3.2 MB per full task) and by `MAX_TASKS` (at most 256).

The longer form is in [docs/decisions.md](docs/decisions.md) and [docs/architecture.md](docs/architecture.md).

## Limitations

| Limitation | Possible solution |
|------------|-------------------|
| Tasks and partial windows live in memory and disappear on restart | Store task configuration and recreate it at startup |
| A slow or blocked stdout sink stalls every task and the Producer | Give each task a bounded queue and an overflow policy |
| One Python event loop processes every task, so the server can be slower than `--rate`. With the null sink, one passthrough task handled about 13.8 million samples per second, one regression task with `window_size` 100 about 4 million, and 32 such tasks about 0.12 million. The Producer then slows down through TCP backpressure, and each 64 KiB read holds the loop for up to about 66 ms | Keep the task count low for high rates, update regression with running sums, or move tasks to worker processes |
| There is no stop without removal, and no restart of a failed task | Add status transitions and `PATCH /api/v1/tasks/{id}` |
| Only one Producer can be connected | Map connections to named streams and let a task subscribe |
| Bytes of a sample split by disconnect are dropped | Frame samples with sequence numbers if that loss matters |
| Several stdout tasks interleave their batches | Write each task to its own file or WebSocket |
| A Producer that connects and sends nothing holds the only slot for up to `PRODUCER_IDLE_SECONDS` | Lower the timeout, or map connections to named streams |
| There is no authentication, no persistence, and no second server | Out of scope for this task |

## Documentation

| Document | Purpose |
|----------|---------|
| [Design index](docs/README.md) | Documentation map |
| [Architecture](docs/architecture.md) | Components, data flow, concurrency |
| [TCP wire protocol](docs/wire-protocol.md) | Sample encoding |
| [REST API](docs/rest-api.md) | Endpoints and models |
| [Decisions](docs/decisions.md) | Trade offs and assumptions |
| [Acceptance criteria](docs/acceptance-criteria.md) | Pass, Deferred, and out of scope checks from the task |
| [Testing strategy](docs/testing-strategy.md) | Test levels and example oracles |
| [Continuous integration](docs/ci.md) | GitHub Actions on a self hosted runner |
| [Hardening](docs/hardening.md) | Current controls, security review findings, hardening plan |
| [Implementation plan](docs/implementation-plan.md) | How the work was staged |
