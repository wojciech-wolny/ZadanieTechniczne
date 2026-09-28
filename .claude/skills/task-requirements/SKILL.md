---
name: task-requirements
description: Numbered functional and project requirements of the streaming data processing task (Producer, Processing Server, algorithms, sinks, REST API, deliverables). Use when designing, implementing, testing or reviewing any part of this project, or when checking scope and traceability.
---

# Task Requirements

Source: `wytyczne/task_python_2608-0.2.md`. This skill is a condensed, numbered version for traceability. When in doubt, the source file wins.

## Guiding principles

1. A smaller working solution beats a large unfinished one. Not every stage must be done.
2. Evaluated on: working solution, correct stream processing, clear design decisions, readability, reasonable tests.
3. The service will evolve: the number of algorithms, output formats and sink types will grow. Adding one must not require changing existing ones.
4. Unspecified runtime situations: make a reasonable assumption and document it in `README.md`.
5. Known limitations left unsolved go to `README.md` with a possible solution.

## Producer (PRD)

| ID | Requirement |
|----|-------------|
| PRD-1 | Thin TCP client that connects to the Processing Server |
| PRD-2 | Reads samples from an input file and sends them over TCP |
| PRD-3 | Parameter: input file name |
| PRD-4 | Parameter: input format `txt` (numbers as text) or `bin` (4 byte little endian float32) |
| PRD-5 | Parameter: samples per second (configurable rate) |
| PRD-6 | Parameter: total samples to send, default `0` means unlimited |
| PRD-7 | Sends the file in a loop until the limit is reached |
| PRD-8 | Stops after the configured number of samples when a limit is set |
| PRD-9 | Arbitrarily large files: never load the whole file into memory, never create a temporary copy |
| PRD-10 | CLI and TCP wire format are free to choose and must be documented in `README.md` |

## Processing Server (SRV)

| ID | Requirement |
|----|-------------|
| SRV-1 | Accepts a TCP connection from one Producer |
| SRV-2 | Continuously receives samples |
| SRV-3 | Delivers every incoming sample to all active tasks from the same input stream |
| SRV-4 | Multiple tasks active at the same time |
| SRV-5 | Provides a REST API to manage and monitor tasks |
| SRV-6 | Handles client disconnection properly (server keeps running, accepts a new Producer) |
| SRV-7 | Task created before the first sample processes the stream from the first sample |
| SRV-8 | Task created while data flows processes only new samples, no history kept |
| SRV-9 | Stream processing: never store the complete input stream, never write temporary files |

## Stream processing (STR)

| ID | Requirement |
|----|-------------|
| STR-1 | Result is independent of network packet and TCP read sizes |
| STR-2 | A window of `N` samples works when its samples arrive across many TCP reads |
| STR-3 | Processing does not depend on the total length of the stream |

## Processing tasks (TSK)

| ID | Requirement |
|----|-------------|
| TSK-1 | A task may have: ID, algorithm, sink type, statistics, optional algorithm parameters |
| TSK-2 | Every task exposes `samples_processed` |
| TSK-3 | Task information contains its configuration and current state |
| TSK-4 | Different algorithms may expose different additional statistics |

## Algorithms (ALG)

| ID | Algorithm | Requirement |
|----|-----------|-------------|
| ALG-1 | `passthrough` | One output per input sample, value unchanged. `1 2 3 4` gives `1 2 3 4` |
| ALG-2 | `average` | Parameter `N`. Consecutive non overlapping windows of `N`, mean of each complete window. `N=3`, `1 2 3 4 5 6 7` gives `2 5` |
| ALG-3 | `average` | Statistics: `windows_processed`, `last_result` (only after at least one window) |
| ALG-4 | `linear_regression` | Parameter `N`. Non overlapping windows, `x = 0..N-1`, `y` = samples, OLS fit `y = a*x + b`, output slope `a`. `N=4`, `1 3 5 7 10 9 8 7` gives `2 -1` |
| ALG-5 | `linear_regression` | Statistics: `windows_processed`, `last_slope`, `min_slope`, `max_slope` |
| ALG-6 | windowed | Incomplete windows produce no result |

Library or own implementation of the math is allowed.

## Output sinks (OUT)

| ID | Requirement |
|----|-------------|
| OUT-1 | Each task produces a stream of numeric results |
| OUT-2 | `null` sink discards results |
| OUT-3 | `stdout` sink writes results to standard output as ASCII |
| OUT-4 | ASCII mapping: round the value; `0..127` becomes that character, anything else becomes `#`. `10` newline, `65` A, `66` B, `111` o, `137` `#` |

## REST API (API)

| ID | Requirement |
|----|-------------|
| API-1 | Create and start a processing task |
| API-2 | List active tasks |
| API-3 | Get information and statistics of a task |
| API-4 | Stop and remove a task |
| API-5 | Endpoints, models, status codes and error responses are free to choose |

## Out of scope

Multiple Producers, multiple server instances, distributed processing, authentication, production deployment, persistent storage of tasks or historical samples.

## Deliverables (DLV)

| ID | Requirement |
|----|-------------|
| DLV-1 | Python 3.10 or newer (project targets 3.13.7) |
| DLV-2 | Producer application code |
| DLV-3 | Processing Server code |
| DLV-4 | Complete project and dependency setup (`pyproject.toml` with `uv`) |
| DLV-5 | Automated tests |
| DLV-6 | `README.md` explaining: install, start server, start producer, REST API usage, running tests, assumptions and design decisions |
| DLV-7 | Project runnable by following the README |
| DLV-8 | Nice to have: script running the entire demo |

## Example data

Files in `wytyczne/` verify the solution end to end with the `stdout` sink:

| File | Configuration | Expected |
|------|---------------|----------|
| `passthrough.txt` | `passthrough` | `Passthrough - It works! ` |
| `example_text.txt` | `passthrough` | `Passthrough works: these samples are printed raw, with no filtering.` |
| `example_text.txt` | `average`, `N=6` | `Hello! Nice work :)` |
| `example_text.txt` | `linear_regression`, `N=4` | `Congratulation! It is correct decoded data for linear regression` |
| `example_binary.f32` | `passthrough` | `Passthrough works on binary too: raw float32 samples, no filtering.` |

Other parts of each file look like noise under a given configuration; that is expected.

## Checklist

- [ ] Every requirement ID above is implemented or listed as a limitation in `README.md`
- [ ] Every implemented requirement has at least one test referencing its ID in the docstring
- [ ] README covers every DLV-6 item
