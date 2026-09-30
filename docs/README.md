# Design documentation

Design for the solution of `wytyczne/task_python_2608-0.2.md`. These documents
describe the behavior implemented in `src/`. Requirement IDs (PRD, SRV, STR, TSK,
ALG, OUT, API, DLV) come from the `task-requirements` skill.

| Document | Content |
|----------|---------|
| [architecture.md](architecture.md) | Components, data flow, module layout, interfaces |
| [wire-protocol.md](wire-protocol.md) | TCP format between Producer and Processing Server |
| [rest-api.md](rest-api.md) | REST endpoints, models, status codes |
| [decisions.md](decisions.md) | Design decisions, assumptions, known limitations |
| [implementation-plan.md](implementation-plan.md) | Ordered stages with requirement coverage |
| [acceptance-criteria.md](acceptance-criteria.md) | Pass, Deferred, and out of scope checks from the task |
| [testing-strategy.md](testing-strategy.md) | Test levels, techniques, oracles from example data |
| [ci.md](ci.md) | GitHub Actions pipeline on a self-hosted runner |
| [hardening.md](hardening.md) | Current controls, security review findings, hardening plan |

## Solution

A synchronous Python **Producer** streams a text or binary file as little endian float64 samples over one TCP connection, paced by a monotonic clock, looping the file until an optional limit. The **Processing Server** is a single asyncio process: `uvicorn` runs the FastAPI app, and the app lifespan starts an `asyncio` TCP server. The receiver reassembles samples from arbitrary TCP chunks and hands each batch to a task registry, which feeds every active task. A task is an **algorithm** (passthrough, average, linear_regression) plus a **sink** (null, stdout). Both are looked up by name in registries.

Algorithms and sinks are selected through small factory registries. Adding a variant is
localized to its implementation, configuration model and registry entry; the existing
algorithm and sink implementations remain unchanged.

## Fixture availability

`wytyczne/example_binary.f32` is part of the example set. Unit tests still build small
float32 fixtures so reader checks do not depend on that file. The system test and the
demo script also run the real fixture.
