# Test context

Use this file when adding or changing tests. Application code is changed by the developer. A failing assertion is a defect report, not a reason to edit `src/` from the test task.

## Layout

| Directory | Level | What belongs here |
|-----------|-------|-------------------|
| `tests/unit/` | Component | One module, no sockets. Algorithms, decoder, readers, registry, sinks, CLI parsers |
| `tests/integration/` | Integration | API through `httpx` / ASGI, or a real receiver on a free local port |
| `tests/system/` | System | Producer plus server against files in `wytyczne/` |
| `tests/conftest.py`, `tests/support.py` | Shared | Fixtures and helpers used by more than one test module |

Every test runs in CI with no manual setup. Bind port `0` and read the chosen port back. A test finishes in seconds.

## Docstrings

The test docstring names the requirement it checks, for example `"""Verify ALG-2: the average ignores an incomplete window."""`. Requirement IDs come from the `task-requirements` skill.

## Cases that already have a home

Match the existing file before adding a new one.

| Behavior | Test module |
|----------|-------------|
| Window results, chunk independence, statistics | `tests/unit/test_algorithms.py` |
| Registry limit, snapshot dispatch, isolated failure | `tests/unit/test_registry.py` |
| Remainder, split floats, non finite samples | `tests/unit/test_decoder.py` |
| Text and binary readers, skip rules | `tests/unit/test_readers.py` |
| Rate, loop, limit | `tests/unit/test_streaming.py` |
| ASCII boundaries | `tests/unit/test_sinks.py` |
| CLI bounds | `tests/unit/test_cli.py` |
| Create, list, read, delete, 404, 409, 422 | `tests/integration/test_api.py` |
| One producer, disconnect, idle | `tests/integration/test_receiver.py` |
| Example files in `wytyczne/` | `tests/system/test_examples.py` |

## Design techniques

Prefer equivalence partitions and boundaries over a long list of similar values. For windows, cover size 1 or 2, one full window, a remainder shorter than the window, and input split across calls. For the registry, cover an empty registry, the task at `max_tasks`, a failure in one of several running tasks, and a task created while `dispatch` is conceptually in progress.

Run `uv run pytest -q` from the repository root. The CI command also writes `report.html`. See `.github/workflows/ci.yml` and `docs/testing-strategy.md`.
