# Agent context

Read this file before searching the repository. It is the shared map for the architect, developer, tester and security reviewer.

Package contracts, read only when you change that package:

- `src/server/CLAUDE.md` for the Processing Server, tasks and REST API
- `src/producer/CLAUDE.md` for the TCP Producer
- `src/common/CLAUDE.md` for the wire format
- `tests/CLAUDE.md` for pytest layout and requirement IDs

Numbered requirements live in the `task-requirements` skill and in `wytyczne/task_python_2608-0.2.md`. Style, FastAPI, tests and CI live in the matching skills under `.claude/skills/`.

## What this project is

Two processes share one repository. The Producer reads a sample file in chunks and sends an unframed little endian float64 TCP stream. The Processing Server decodes that stream on one asyncio loop and runs many tasks. Each task is one algorithm (`passthrough`, `average`, `linear_regression`) and one sink (`null`, `stdout`). Tasks are created and removed with REST under `/api/v1`.

```
file -> Producer (chunked read, pace, loop, limit) -> TCP <d
     -> SampleReceiver -> SampleDecoder -> TaskRegistry.dispatch
     -> ProcessingTask -> Algorithm -> Sink
REST -> TaskRegistry (create, list, find, remove)
```

## Commands

From the repository root, with Python 3.13.7 and uv:

```powershell
uv sync
uv run processing-server
uv run producer wytyczne/passthrough.txt --format txt --rate 1000
uv run ruff check .
uv run ruff format --check .
uv run pytest -q
```

HTTP defaults to `127.0.0.1:8000`. TCP defaults to `127.0.0.1:9000`. Overrides are environment variables on `Settings` in `src/server/settings.py`.

## Invariants

1. Memory stays bounded. File reads and TCP reads use fixed chunk sizes. A windowed algorithm keeps at most `window_size` samples.
2. One Producer connection is active. A disconnect leaves the server running. The decoder drops a partial trailing sample. Algorithm windows and task statistics survive, so the next Producer continues the same logical stream.
3. A task receives samples only from dispatches that start after `TaskRegistry.create_task` returns. `dispatch` copies the running tasks before it calls them.
4. The same samples produce the same results whether they arrive in one TCP read or many. `SampleDecoder` keeps a remainder shorter than 8 bytes.
5. One event loop runs the API and the receiver. A batch is processed without awaiting. A slow stdout sink can stall that loop. That trade off is accepted.
6. Modules in `src/server/services/` stay free of FastAPI. Status codes are mapped in `src/server/main.py` and `src/server/api/`.
7. The wire format has one home, `src/common/protocol.py`: `struct` format `<d`, 8 bytes. Input files are different. Text is whitespace separated numbers. Binary files are little endian float32, format `<f`, 4 bytes.
8. Python in this repository has no code comments. Docstrings are one sentence plus `:param:`, `:return:`, `:raises:` and `:attr:` when useful, and they contain no hyphen characters. Use `X | None`, builtin generics and the `type` statement. Do not add `from __future__ import annotations`. A function name is the comment for an action. Split a nested or long block into those functions so the caller stays a short flat sequence. Three or more related values that travel together go on a dataclass. A protocol is the type when several classes share the same methods.

## Add an algorithm

1. Add the class in `src/server/services/algorithms.py`. A windowed algorithm subclasses `WindowAlgorithm` and implements `calculate_result`.
2. Add a config model in `src/server/schemas.py` and include it in the `AlgorithmConfig` union.
3. Add a factory and one `ALGORITHM_FACTORIES` entry.
4. Leave existing algorithm classes unchanged.

## Add a sink

1. Add a class that implements `Sink` in `src/server/services/sinks.py`.
2. Extend the `SinkName` literal in `src/server/schemas.py`.
3. Add a factory and one `SINK_FACTORIES` entry.

## Where to look

| Question | File |
|----------|------|
| Task create, list, remove, dispatch | `src/server/services/registry.py` |
| One task, statistics, failure | `src/server/services/tasks.py` |
| Algorithms and slope formula | `src/server/services/algorithms.py` |
| ASCII mapping | `src/server/services/sinks.py` |
| TCP accept and idle timeout | `src/server/services/receiver.py` |
| Partial samples and NaN | `src/server/services/decoder.py` |
| Request and response models | `src/server/schemas.py` |
| App, lifespan, task limit 409 | `src/server/main.py` |
| Producer CLI | `src/producer/__main__.py` |
| File readers | `src/producer/readers.py` |
| Producer input limits and binary file format | `src/producer/constants.py` |
| Rate, loop, limit, send | `src/producer/streaming.py` |

Design notes that are already decided: `docs/architecture.md`, `docs/decisions.md`, `docs/rest-api.md`, `docs/wire-protocol.md`, `docs/testing-strategy.md`, `docs/ci.md`.

## When the current design does not fit

Stop and report the mismatch to the architect. Record a new decision in `docs/decisions.md` and, when usage changes, in `README.md`. Keep the implementation on the written plan.
