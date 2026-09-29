# Implementation plan

Each stage ends with passing tests, a commit and a green CI run. Stages 0 to 6 are the minimum complete solution; stage 7 onward is optional.

| Stage | Goal | Requirements | Tests |
|-------|------|--------------|-------|
| 0 | Project scaffold and CI pipeline | DLV-1, DLV-4 | `pytest` runs locally and in CI |
| 1 | Passthrough and sink components | ALG-1, OUT-1..4 | unit |
| 2 | Task and registry | SRV-3, SRV-4, TSK-1..4 | unit |
| 3 | Decoder and TCP receiver | SRV-1, SRV-2, SRV-6, SRV-9, STR-1..3 | unit, integration |
| 4 | REST API and lifespan | SRV-5, SRV-7, SRV-8, API-1..5 | integration |
| 5 | Producer and first end-to-end path | PRD-1..10, DLV-5 | unit, integration, system |
| 6 | Remaining algorithms, demo and final README | ALG-2..6, DLV-6..8 | unit, system |
| 7 | Security review and hardening | | review report |
| 8 | Optional extras | | as needed |

## Stage 0: scaffold

1. Install `uv` and pin Python 3.13.7 in `.python-version`.
2. `pyproject.toml`: `src` layout, `requires-python = ">=3.13"`, dependencies `fastapi`, `uvicorn`, `pydantic-settings`; dev group `pytest`, `httpx`, `ruff`; console scripts `producer`, `processing-server`.
3. Ruff config with line length 99 and `target-version = "py313"`.
4. Empty packages `common`, `producer`, `server`, `tests/unit`, `tests/integration`, `tests/system`.
5. Committed `uv.lock`.
6. `.github/workflows/ci.yml` from the `github-actions` skill template, running on the self-hosted runner (see [ci.md](ci.md)).
7. Add a root `README.md` that states the current implementation status and grows with each stage.
8. Confirm the first workflow run is green.

## Stage 1: passthrough and sinks

1. `Algorithm` protocol and `PassthroughAlgorithm`.
2. `Sink` protocol, `NullSink` and `StdoutSink` taking a text stream (default `sys.stdout`) so tests can inject `io.StringIO`.
3. `convert_to_ascii(value) -> str`.
4. Factory dictionaries keyed by name.

## Stage 2: task and registry

1. `ProcessingTask.process_samples` counts samples, collects results, writes them to the sink once per batch and records a safe failure if the algorithm or sink raises.
2. `TaskRegistry`: `create_task(config)`, `find_task(id)`, `list_tasks()`, `remove_task(id)`, `dispatch(samples)`, `MAX_TASKS` limit raising a domain exception.

## Stage 3: decoder and receiver

1. `SampleDecoder.decode(chunk) -> list[float]` with remainder and finite-value validation.
2. `SampleReceiver` wrapping `asyncio.start_server`: one active connection, reject extra ones, bounded `read(65536)`, dispatch decoded batches, clean close on disconnect or error, `samples_received` and `producer_connected` for the `/api/v1/stream` endpoint.

## Stage 4: REST API

1. `schemas.py` with the models from [rest-api.md](rest-api.md).
2. `create_app()` with `lifespan` starting the registry and receiver on `app.state`.
3. Routers mounted at `/api/v1/tasks` and `/api/v1/stream`, exception handler mapping the task limit error to 409.
4. `processing-server` entry point calling `uvicorn.run(create_app(), ...)`.

## Stage 5: producer and first end-to-end path

1. `read_text_samples(path)` and `read_binary_samples(path)` generators, chunked, with bounded token handling and finite-value validation.
2. `repeat_samples(path, reader)` reopening the file, error on empty file; limit with `itertools.islice` when `limit > 0`.
3. `send_samples(socket, samples, rate)` with deadline pacing and batching.
4. CLI: `producer FILE --format {txt,bin} --rate N --limit N --host --port`.
5. System test: start the app on free ports, create a passthrough/stdout task, run the Producer against `wytyczne/passthrough.txt`, and assert decoded output.
6. Update the root README with copy-paste installation and passthrough demo commands. At this point the repository has a small working solution.

## Stage 6: complete the required feature set

1. Add `WindowAlgorithm`, `AverageAlgorithm`, `LinearRegressionAlgorithm` and their statistics.
2. Extend unit and system coverage to all required algorithms and sinks.
3. `scripts/demo.py`: start the server, create the tasks that decode `example_text.txt`, run the Producer, print results.
4. Complete the root `README.md`: installation, server and Producer commands, CLI defaults, REST examples, TCP format, tests, assumptions, decisions, limitations and demo, plus links to `docs/` and a CI status badge.

## Stage 7: security review

Run the `security` agent over the whole code base and the workflow files and fix findings rated medium or higher. Findings and the ordered plan are in [hardening.md](hardening.md).

## Stage 8: optional extras

1. `file` sink writing numeric results as text lines.
2. Numeric stdout format (`"format": "ascii" | "numbers"`).
3. Per task queues for sink isolation.
4. If a binary example fixture is supplied later, find its decoding configuration.
