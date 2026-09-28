# Design documentation

Proposed design for solving `wytyczne/task_python_2608-0.2.md`. The repository is
currently in the design phase; these documents describe intended behavior, not an
implemented or runnable system. Requirement IDs (PRD, SRV, STR, TSK, ALG, OUT, API,
DLV) come from the `task-requirements` skill.

| Document | Content |
|----------|---------|
| [architecture.md](architecture.md) | Components, data flow, module layout, interfaces |
| [wire-protocol.md](wire-protocol.md) | TCP format between Producer and Processing Server |
| [rest-api.md](rest-api.md) | REST endpoints, models, status codes |
| [decisions.md](decisions.md) | Design decisions, assumptions, known limitations |
| [implementation-plan.md](implementation-plan.md) | Ordered stages with requirement coverage |
| [testing-strategy.md](testing-strategy.md) | Test levels, techniques, oracles from example data |
| [ci.md](ci.md) | GitHub Actions pipeline on a self-hosted runner |

## Proposed solution

A synchronous Python **Producer** streams a text or binary file as little endian float64 samples over one TCP connection, paced by a monotonic clock, looping the file until an optional limit. The **Processing Server** is a single asyncio process: `uvicorn` runs the FastAPI app, and the app lifespan starts an `asyncio` TCP server. The receiver reassembles samples from arbitrary TCP chunks and hands each batch to a task registry, which feeds every active task. A task is an **algorithm** (passthrough, average, linear_regression) plus a **sink** (null, stdout). Both are looked up by name in registries.

Algorithms and sinks are selected through small factory registries. Adding a variant is
localized to its implementation, configuration model and registry entry; the existing
algorithm and sink implementations remain unchanged.

## Fixture availability

The task description says binary example data may be provided, but
`wytyczne/example_binary.f32` is not present in this checkout. Binary-reader tests will
therefore generate small float32 fixtures during the test run.
