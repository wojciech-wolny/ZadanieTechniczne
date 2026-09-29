# Testing strategy

Follows the `istqb-testing` skill. Every test docstring starts with the requirement ID it verifies.

## Levels

| Level | Scope | Location | Network |
|-------|-------|----------|---------|
| Component | algorithms, sinks, decoder, readers, pacing math, registry | `tests/unit/` | none |
| Integration | API with registry via `TestClient`; receiver with a real local socket | `tests/integration/` | localhost, free port |
| System | Producer process against a running server, stdout decoded | `tests/system/` | localhost |

## Key test conditions

| Requirement | Condition | Technique |
|-------------|-----------|-----------|
| ALG-1, ALG-2, ALG-4 | Task examples give the documented output | example based |
| ALG-6 | `N-1`, `N`, `N+1` samples | boundary values |
| ALG-4 | Constant window gives slope 0; `window_size` 1 rejected | equivalence partitioning |
| ALG-5 | min and max slope after several windows | example based |
| OUT-4 | values `-1`, `-0.4`, `0`, `65.4`, `127`, `127.5`, `128` | boundary values |
| STR-1, STR-2 | Same samples decoded whole, byte by byte and in random splits give identical results | error guessing |
| PRD-9 | Text token split across a chunk boundary; overlong token rejected; binary float split across a chunk | error guessing |
| PRD-6, PRD-8 | `limit` 0 unlimited (checked by taking N items), 1, file length, file length plus 1 | boundary values |
| PRD-7 | Samples repeat in file order after the end | example based |
| SRV-7, SRV-8 | Task created before first batch sees all; after one batch sees only later ones | state transition |
| SRV-1, SRV-6 | Second connection refused; reconnect keeps the server alive and completes a retained partial algorithm window | state transition |
| API-1..4 | 201, 200, 404, 204, 422 for invalid window, 409 at task limit | decision table |
| API-3 | Algorithm or sink exception fails one task without interrupting another | error guessing |
| Input validity | Producer skips NaN and infinities; server rejects a custom Producer sending either | equivalence partitioning |
| Empty input | Empty, whitespace-only, all-invalid and too-short binary files fail after one pass | equivalence partitioning |

## Oracles from example data

| File | Configuration | Expected stdout contains |
|------|---------------|--------------------------|
| `passthrough.txt` | passthrough | `Passthrough - It works! ` |
| `example_text.txt` | passthrough | `Passthrough works: these samples are printed raw, with no filtering.` |
| `example_text.txt` | linear_regression, `window_size` 4 | `Congratulation! It is correct decoded data for linear regression` |
| `example_text.txt` | average, `window_size` 6 | `Hello! Nice work :)` |

The oracles hold only when the task starts at the first sample of the file, so system tests create tasks before the Producer connects.

Unit tests create temporary little endian float32 files for chunk boundaries. The
system test also decodes `wytyczne/example_binary.f32`.

## Rules

1. No sleeps in component tests; pacing is tested through an injected clock and sleep function.
2. System tests use a small `limit` and a high `rate` so they finish in seconds.
3. `pytest -q` runs everything without a manually started server.
