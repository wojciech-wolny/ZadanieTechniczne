---
name: codebase-context
description: >-
  Maps the Producer and Processing Server modules, invariants and extension
  points, and points to colocated CLAUDE.md files. Use before exploring the
  tree when implementing, reviewing, testing or designing any change under
  src/, tests/, the REST API, or the TCP sample pipeline.
---

# Codebase context

Read `CLAUDE.md` at the repository root first. Then read only the package file for the code you will change:

| Area | Context file |
|------|----------------|
| Processing Server, tasks, algorithms, sinks, REST | `src/server/CLAUDE.md` |
| Producer CLI, readers, pacing | `src/producer/CLAUDE.md` |
| Wire format `<d` and default hosts | `src/common/CLAUDE.md` |
| pytest layout and requirement IDs | `tests/CLAUDE.md` |

Those files are the current contracts. `docs/architecture.md` and `docs/decisions.md` explain why. The `task-requirements` skill is the numbered requirement list.

## Fast facts

1. Producer file formats and the TCP format differ. Text and float32 files go in. Float32 layout and input limits live in `producer.constants`. Little endian float64 (`<d`, 8 bytes) goes on the wire through `common.protocol.pack_samples`.
2. `TaskRegistry.dispatch` snapshots `status == "running"` before it calls tasks. A task created during that call waits for the next dispatch. One task failure marks that task `failed`, closes its sink, and leaves the others running.
3. `src/server/services/` does not import FastAPI. New algorithms and sinks are a new class, a schema entry, and one factory registration. Existing classes stay unchanged.
4. Python here has no code comments. Docstrings are one sentence and contain no hyphen characters. A function name is the comment for an action. Nested or long blocks are split so the caller stays a short flat sequence. Three or more related values travel on a dataclass. Shared method sets use a protocol.
