---
name: crucial-information
description: >-
  Records only the crucial facts from a change, split by audience. Use when
  writing or updating README.md, docs/, CLAUDE.md, skills, or agent files,
  or when a change should be kept for a later reader.
---

# Crucial information

After a change, keep the fact a later reader still needs. Drop the rest.

| Place | Reader | Write |
|-------|--------|--------|
| `CLAUDE.md`, `.claude/skills/`, `.claude/agents/` | models | Contract, invariant, and enough detail to edit the code |
| `README.md` | humans | Install, run, call, and the limit they will hit. No module names, no why |
| `docs/` | humans and models | The fact and one short reason. Link to code for the steps |

## What is crucial

Keep a fact when a later person or model would do the wrong thing without it:

1. A default, limit, or command that usage depends on.
2. A behavior that surprises (skip, disconnect, continue the same stream).
3. One home for a constant or rule, and why that home is not the other obvious file.
4. A contract a model must not break (dispatch snapshot, wire format, no FastAPI under `services/`).

Leave it out when it is only the shape of the current functions. Named helpers and dataclasses belong in the package `CLAUDE.md` when the next edit must preserve them. They do not belong in the README.

## Where to put it

1. Human can hit it while running the program: one line in `README.md`.
2. Human or model needs the reason: one or two sentences in `docs/` (`decisions.md` for a choice, `architecture.md` for where something lives).
3. Model must follow it while editing: `CLAUDE.md` or the package file beside the code. Repeat the rule in a skill only when every edit of that kind should load it.

Do not paste the same paragraph into all three. The README states the fact. `docs/` adds the reason. The model file adds the edit rule.

## Examples

Wire format `<d` is shared, so it stays in `src/common/protocol.py`. File float32 `<f` is not the wire format, so it stays in `src/producer/constants.py`. Say that in `docs/architecture.md` and in `src/common/CLAUDE.md`. The README only says the wire is little endian float64, 8 bytes.

`MAX_WINDOW_SIZE` validates the request. It is not an operator setting, so it stays in `schemas.py`. One sentence in `docs/architecture.md`. Nothing in the README beyond the window range in the algorithm table.

`TextReadState` and `SendSchedule` group fields that travel together. Name them in `src/producer/CLAUDE.md`. Do not mention them in the README.
