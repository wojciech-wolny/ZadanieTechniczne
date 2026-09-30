# Acceptance criteria

Source: `wytyczne/task_python_2608-0.2.md`. Each criterion uses the requirement ID from the `task-requirements` skill. When this document or the skill disagrees with the task file, the task file wins.

A criterion is **Pass** when the observable behavior holds.

A criterion is **Deferred** when the behavior is missing and `README.md` names the limitation together with a possible solution. The working solution the task asks to see is the Producer, the Processing Server, correct stream processing, the three algorithms, the two sinks, the four REST operations, tests, and the README. A Deferred item on that list is a recorded gap.

A criterion is **Out of scope** when the task lists it as unnecessary. Absence is Pass.

A nice-to-have that is absent is Pass.

Where the task allows a choice, Pass means `README.md` states the choice and the running project matches that statement. The choices this repository made are collected at the end.

## Quality bar

| ID | Passes when |
|----|-------------|
| GOAL-1 | The repository contains a working Producer and Processing Server, readable code, written design decisions, and automated tests. |
| GOAL-2 | The solution stays within the task. Features the task does not ask for are absent or clearly optional. |
| GOAL-3 | Runtime cases the task leaves open, and that the solution relies on, are written as assumptions in `README.md`. |
| GOAL-4 | A limitation left unsolved is written in `README.md` with a possible later solution. |
| GOAL-5 | A further algorithm or sink can be added without changing the existing algorithm and sink classes. |

## Producer

| ID | Passes when |
|----|-------------|
| PRD-1 | The Producer is a TCP client. Started against a listening Processing Server, it opens a connection to that server. |
| PRD-2 | Samples read from the input file are the samples written to that connection. |
| PRD-3 | The command line accepts the input file name. |
| PRD-4 | The command line accepts format `txt` or `bin`. Text input is numbers stored as text. Binary input is 4 byte little endian floating point values. |
| PRD-5 | The command line accepts a rate in samples per second, and the Producer sends at that rate. |
| PRD-6 | The command line accepts a total number of samples. The default `0` means the Producer does not stop because a count was reached. |
| PRD-7 | When the file ends before the send count is satisfied, reading continues from the start of the same file, in file order. With the default unlimited count, the file repeats. |
| PRD-8 | When the limit is greater than `0`, the Producer stops after that many samples have been sent. |
| PRD-9 | A file larger than available memory can be streamed. The Producer does not load the complete file into memory and does not write a temporary copy of it. |
| PRD-10 | The command line and the TCP wire format are described in `README.md`. The Producer and the Processing Server use that format. |

## Processing Server

| ID | Passes when |
|----|-------------|
| SRV-1 | The server accepts a TCP connection from one Producer. |
| SRV-2 | While that Producer stays connected and keeps sending, the server keeps receiving samples. |
| SRV-3 | Each received sample is delivered to every task that is active for that sample. All active tasks see the same input stream. |
| SRV-4 | Two or more tasks can be active at the same time, and each of them receives the stream. |
| SRV-5 | The server exposes a REST API that manages and monitors processing tasks. |
| SRV-6 | After the Producer disconnects, the server process keeps running and can accept another Producer. |
| SRV-7 | A task created before the first sample processes the stream from that first sample. |
| SRV-8 | A task created while samples are already flowing processes only samples that arrive after it is active. The server does not keep historical samples to replay. |
| SRV-9 | The server processes the input as a stream. It does not store the complete input and does not write it to a temporary file. |

## Stream processing

| ID | Passes when |
|----|-------------|
| STR-1 | The same sample sequence produces the same task results when the Producer uses different packet sizes and the server reads different chunk sizes. |
| STR-2 | A window of `N` samples produces its result when those `N` samples arrive across many TCP reads. This holds for a large window, such as `N = 100`. |
| STR-3 | Results for the samples already received do not depend on the total length of the stream and do not require samples that have not arrived. |

## Processing tasks

| ID | Passes when |
|----|-------------|
| TSK-1 | A task has an identifier, an algorithm, a sink type, processing statistics, and any parameters that algorithm requires. |
| TSK-2 | Every task exposes `samples_processed`, the number of input samples that task has processed. |
| TSK-3 | Task information from the API contains the task configuration and its current state. |
| TSK-4 | Algorithms may expose different extra statistics. Average and linear regression expose the statistics named in ALG-3 and ALG-5. |

The internal module layout is a project choice. This repository records it in [architecture.md](architecture.md).

## Algorithms

Ordinary least squares may be a library call or local code. Either satisfies ALG-4.

| ID | Passes when |
|----|-------------|
| ALG-1 | Passthrough emits one result per input sample, value unchanged. Input `1 2 3 4` yields `1 2 3 4`. |
| ALG-2 | Average takes `N` and splits the input into consecutive non overlapping windows of `N`. Each complete window yields its arithmetic mean. For `N = 3`, input `1 2 3 4 5 6 7` yields `2 5`. |
| ALG-3 | Average exposes `windows_processed` and `last_result`. `last_result` is present only after at least one complete window. |
| ALG-4 | Linear regression takes `N` and uses the same non overlapping windows. Positions inside a window are `x = 0 .. N-1` and the samples are `y`. The result is the ordinary least squares slope `a` in `y = a*x + b`. For `N = 4`, input `1 3 5 7 10 9 8 7` yields `2` then `-1`. |
| ALG-5 | Linear regression exposes `windows_processed`, `last_slope`, `min_slope`, and `max_slope`. |
| ALG-6 | A window that is still shorter than `N` yields no result. In the average example, the final `7` yields nothing. |

## Output

| ID | Passes when |
|----|-------------|
| OUT-1 | Each task produces a stream of numeric results: one per sample for passthrough, one per complete window for average and linear regression. |
| OUT-2 | The `null` sink discards those results. |
| OUT-3 | The `stdout` sink writes results to standard output as ASCII. |
| OUT-4 | The value is rounded to an integer. A rounded value in `0..127` is written as that ASCII character. Any other rounded value is written as `#`. The task examples hold: `10` is a newline, `65` is `A`, `66` is `B`, `111` is `o`, `137` is `#`. |

Further sinks or formats are optional. Their absence is Pass.

## REST API

| ID | Passes when |
|----|-------------|
| API-1 | A client can create a task and that task starts processing samples that arrive after it is active. |
| API-2 | A client can list the active tasks. |
| API-3 | A client can read one task, including its configuration, state, and statistics. |
| API-4 | A client can stop a task and remove it. After removal it is absent from the list and receives no further samples. |
| API-5 | Paths, request and response models, status codes, and error bodies are documented in `README.md` and match the running server. |

The task file leaves the URL layout free. This repository's contract, which satisfies API-5, serves every resource under `/api/v1` and leaves that prefix unchanged if a later prefix is added. Details are in [rest-api.md](rest-api.md).

## Deliverables

| ID | Passes when |
|----|-------------|
| DLV-1 | The project runs on Python 3.10 or newer. This repository targets 3.13.7. |
| DLV-2 | The Producer application code is in the repository. |
| DLV-3 | The Processing Server code is in the repository. |
| DLV-4 | Dependencies are installable from the repository. `uv` with `pyproject.toml`, Poetry, or `requirements.txt` all qualify. This repository uses `uv`. |
| DLV-5 | Automated tests are included and the README says how to run them. |
| DLV-6 | `README.md` explains installation, how to start the Processing Server, how to start the Producer, how to use the REST API, how to run the tests, and the important assumptions and design decisions. |
| DLV-7 | Following `README.md` is enough to install and run the project. |
| DLV-8 | A script that runs the whole demo is present. This is a nice to have: absence is Pass. This repository provides `scripts/demo.py`. |

## Example files

The task says that finding human readable output in the example files is not required to finish. These checks add confidence. A miss here is not, by itself, a failed delivery.

| File | Configuration | Readable result |
|------|---------------|-----------------|
| `wytyczne/passthrough.txt` | passthrough, stdout | `Passthrough - It works! ` |
| `wytyczne/example_text.txt` | passthrough, stdout | `Passthrough works: these samples are printed raw, with no filtering.` |
| `wytyczne/example_text.txt` | average, `N = 6`, stdout | `Hello! Nice work :)` |
| `wytyczne/example_text.txt` | linear regression, `N = 4`, stdout | `Congratulation! It is correct decoded data for linear regression` |
| `wytyczne/example_binary.f32` | passthrough, stdout | `Passthrough works on binary too: raw float32 samples, no filtering.` |

The strings above are embedded in longer files. Other bytes under the same configuration are noise. The task must exist before the first sample of the file, which is SRV-7.

## Out of scope

Absence of the following is Pass:

| Item | Task statement |
|------|----------------|
| Several Producers connected at once | The solution only needs one connected Producer. |
| Several Processing Server instances | Not required. |
| Distributed processing | Not required. |
| Authentication | Not required. |
| Production deployment | Not required. |
| Persistent tasks or stored historical samples | Not required. Tasks may live only in memory. |

## Contract chosen by this repository

These statements close choices and gaps the task left open. They are Pass for this repository when the behavior matches `README.md` and [decisions.md](decisions.md). A different choice would still meet the task if it were documented and implemented. It would fail acceptance of this repository.

| Topic | Passes when |
|-------|-------------|
| Wire format | Samples on the socket are unframed IEEE 754 float64, little endian, 8 bytes each. A remainder shorter than 8 bytes is kept until the next read. On disconnect that remainder is dropped. |
| CLI | `producer FILE --format {txt,bin} --rate N --limit N` connects to the configured host and port. `limit` defaults to `0`. |
| Text input | Tokens are split on whitespace. A non finite or invalid token is skipped. A token longer than 1024 characters is skipped. |
| Binary input | A trailing fragment shorter than 4 bytes is ignored. |
| Empty input | A complete pass that yields no valid sample is an error. |
| One Producer | A second connection is closed. The first Producer keeps the slot. |
| Disconnect | Complete samples, algorithm windows, and statistics remain, so the next Producer continues the same logical stream. |
| Activation | A task receives samples only from dispatches that start after creation finishes. Removal takes effect before the next dispatch. |
| Delete | Delete stops the task and removes it. There is no paused state. |
| Failure | An exception in one task marks that task failed, closes its sink, and leaves the other tasks running. The failed task stays readable until it is deleted. |
| ASCII halves | Rounding is Python `round`. `65.5` and `66.5` both become `B`. |
| Rate | `rate` is a finite value from `0.1` to `1000000`. The first batch is sent immediately. Later batches follow a monotonic schedule. |
| Settings | Hosts, ports, and the task limit come from `.env`, then the process environment. `.env.example` is not loaded. Defaults bind to `127.0.0.1` when `.env` matches the example. |
