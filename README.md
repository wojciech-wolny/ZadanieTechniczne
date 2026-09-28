# Streaming Data Processing

Design for a Python solution to the recruitment task in
[`wytyczne/task_python_2608-0.2.md`](wytyczne/task_python_2608-0.2.md): a file-based
TCP Producer and a Processing Server with streaming algorithms and a REST API.

## Status

The project is currently in the **design phase**. Application code and project setup
have not been implemented yet, so there are no valid installation or run commands at
this stage. See the [implementation plan](docs/implementation-plan.md) for the intended
delivery order.

This README will become the runnable user guide as implementation progresses. It will
cover installation, starting both applications, Producer options, REST API examples,
tests, the wire format, assumptions, design decisions and known limitations.

## Documentation

| Document | Purpose |
|----------|---------|
| [Design index](docs/README.md) | Documentation map and proposed solution |
| [Architecture](docs/architecture.md) | Components, data flow and concurrency |
| [TCP wire protocol](docs/wire-protocol.md) | Producer-to-server sample encoding |
| [REST API](docs/rest-api.md) | Endpoints, models and errors |
| [Decisions](docs/decisions.md) | Assumptions, trade-offs and limitations |
| [Testing strategy](docs/testing-strategy.md) | Test levels, conditions and oracles |
| [Continuous integration](docs/ci.md) | Planned GitHub Actions checks |
| [Implementation plan](docs/implementation-plan.md) | Incremental delivery stages |
