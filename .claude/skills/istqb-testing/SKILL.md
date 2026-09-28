---
name: istqb-testing
description: Writes simple pytest tests following ISTQB test design techniques (equivalence partitioning, boundary value analysis, decision tables, state transitions) and test levels. Use when writing, extending or reviewing tests, or when the user asks about test coverage.
---

# ISTQB Testing

Tests must be simple. Always follow the `python-code-style` skill as well.

## Test levels

| Level | Scope | Location |
|-------|-------|----------|
| Component | one algorithm, parser, sink | `tests/unit/` |
| Integration | API with registry, TCP receiver with tasks | `tests/integration/` |
| System | producer sends a file, server produces output | `tests/system/` |

Most tests are component tests. Keep a few integration tests and at least one system test.

## Test design techniques

1. **Equivalence partitioning:** one test per class of input (valid window, invalid window, empty stream).
2. **Boundary value analysis:** test at, below and above each limit (`window_size` 0, 1, 2; samples N minus 1, N, N plus 1; ASCII 0, 127, 128, negative).
3. **Decision tables:** use `pytest.mark.parametrize` for combinations (algorithm and sink).
4. **State transition:** task lifecycle created, running, stopped; client connected, disconnected.
5. **Error guessing:** samples split across TCP reads, partial binary float, blank text lines.

## Rules

1. Structure every test as **Arrange, Act, Assert** separated by one blank line. No comments.
2. One behaviour per test. Name it `test_<action>_<condition>_<expected>`.
3. Use plain `assert`. No custom assertion helpers unless reused three times.
4. Use `pytest.mark.parametrize` with `ids` instead of loops inside a test.
5. Fixtures only for shared setup, defined in `conftest.py`.
6. No sleeps, no real network in component tests. Use in memory streams.
7. API tests use `fastapi.testclient.TestClient` with `create_app()` inside a `with` block so lifespan runs.
8. Test observable behaviour, never private attributes.
9. Tests are traceable to a requirement: the docstring states which requirement the test verifies.

## Example

```python
import pytest

from server.algorithms import AverageAlgorithm
from server.sinks import convert_to_ascii


def test_process_samples_incomplete_window_produces_no_result() -> None:
    """Verify that the average ignores the last incomplete window."""
    algorithm = AverageAlgorithm(window_size=3)

    results = []
    for sample in [1, 2, 3, 4, 5, 6, 7]:
        result = algorithm.process_sample(sample)
        if result is not None:
            results.append(result)

    assert results == [2, 5]
    assert algorithm.windows_processed == 2


@pytest.mark.parametrize(
    ("value", "expected"),
    [(-1, "#"), (0, "\x00"), (65.4, "A"), (127, "\x7f"), (128, "#")],
    ids=["below_range", "lower_bound", "rounded", "upper_bound", "above_range"],
)
def test_convert_to_ascii_boundaries(value: float, expected: str) -> None:
    """Verify the stdout ASCII mapping at its range boundaries."""
    character = convert_to_ascii(value)

    assert character == expected
```

## API example

```python
from fastapi import status
from fastapi.testclient import TestClient

from server.main import create_app


def test_read_task_unknown_id_returns_not_found() -> None:
    """Verify that requesting a missing task returns 404."""
    with TestClient(create_app()) as client:
        response = client.get("/tasks/unknown")

    assert response.status_code == status.HTTP_404_NOT_FOUND
```

## Checklist

- [ ] Each requirement has at least one test
- [ ] Boundaries covered for every numeric limit
- [ ] Chunked input gives the same result as whole input
- [ ] Tests run with plain `pytest` and need no running server
