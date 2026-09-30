# Decisions, assumptions and limitations

## Decisions

1. **Two packages in one project.** `producer` and `server` share one `pyproject.toml` managed by `uv`, with console scripts `producer` and `processing-server`. A tiny `common` package holds the wire format.
2. **Wire format float64 LE, unframed.** Fixed size makes chunk reassembly trivial and keeps text precision. See [wire-protocol.md](wire-protocol.md).
3. **Single asyncio loop on the server.** FastAPI and the TCP receiver share the loop started by `uvicorn`; the receiver is started and stopped in `lifespan`. No threads, no locks, deterministic ordering of task creation versus samples.
4. **Synchronous Producer.** A plain socket and a blocking loop are the simplest correct client. Pacing uses `time.monotonic()` deadlines and batches of about 20 ms of samples, so high rates do not need one syscall per sample.
5. **Chunked readers.** Text is read in 64 KiB chunks and split on whitespace, carrying a partial token to the next chunk, because a text file may be one huge line (the examples are). Binary is read in multiples of 4 bytes and decoded with `struct.iter_unpack("<f")`.
6. **Tasks survive a Producer disconnect.** Complete decoded samples from successive connections form one logical stream. Statistics and partial algorithm windows survive reconnects, so a later Producer can complete a window started by an earlier one. A partial 8 byte wire sample is discarded.
7. **Registries by name.** Algorithms and sinks are selected by a name in dictionaries of factories; the API uses a discriminated union so validation and OpenAPI stay explicit. A new variant requires a new implementation, configuration model and registry entry, but no changes to existing component classes.
8. **Windows stored as lists of at most N samples.** Memory per task is O(N), bounded by `window_size <= 100_000`; `MAX_TASKS` defaults to 32. The worst-case window storage is therefore bounded, while deployments can choose lower limits. Linear regression uses the closed form OLS slope over positions `0..N-1`; no NumPy needed.
9. **Delete means stop.** There is no paused state; `DELETE /api/v1/tasks/{id}` closes the sink and removes the task.
10. **Settings from environment** via `pydantic_settings`: `TCP_HOST`, `TCP_PORT`, `HTTP_HOST`, `HTTP_PORT`, `MAX_TASKS`. Defaults bind to `127.0.0.1`.
11. **Python 3.13.7.** The task requires 3.10 or newer; 3.13.7 is the newest interpreter available. `requires-python = ">=3.13"` and ruff `target-version = "py313"`.
12. **Task failures are isolated.** An algorithm or sink exception marks only that task as failed. Its safe error summary is exposed by the API, and other tasks continue receiving samples.
13. **Path versioning.** REST resources use the prefix `/api/v1` (API-6). The next incompatible contract is `/api/v2`. `/docs` and `/openapi.json` stay unversioned.
14. **Raw stream kept, packet protocol deferred.** [proposal-packet-protocol.md](proposal-packet-protocol.md) would let the server tell a clean end from a crash and reject foreign clients. The task needs neither: one trusted Producer, and a disconnect is handled the same way either way. The proposal stays as the next step if the format has to evolve.

## Assumptions

1. Text input tokens are separated by any whitespace. Invalid or non-finite tokens are skipped with a warning; the Producer does not stop. A token is limited to 1 KiB so malformed input cannot grow the carry buffer without bound.
2. A binary file whose size is not a multiple of 4 has its trailing bytes ignored with a warning.
3. A complete file pass that yields no valid samples is an error. This covers empty, whitespace-only, all-invalid and binary files shorter than four bytes.
4. `rate` is a finite number of samples per second from 0.1 to 1_000_000, so a sample arrives at least every 10 s, within the default `PRODUCER_IDLE_SECONDS`. There is no "as fast as possible" mode. `limit` defaults to 0 and counts successfully parsed samples sent over TCP.
5. The Producer skips non-finite file values. The server also closes a custom Producer connection that sends NaN or infinity, keeping algorithm statistics JSON-safe.
6. Rounding for ASCII uses Python `round` (banker's rounding). `65.5` becomes `B`, `66.5` also becomes `B`; this only matters on exact halves.
7. Task activation and removal follow the serialized dispatch boundary defined in [architecture.md](architecture.md).
8. Multiple stdout tasks write serialized batch strings, so their batches can interleave and the combined output may not be human-readable.
9. The Producer sends its first sample immediately, uses monotonic deadlines for later batches, and sends immediately when behind schedule rather than accumulating delay.

## Known limitations and possible solutions

| Limitation | Possible solution |
|------------|-------------------|
| Tasks live in memory and vanish on restart | Persist task configs and recreate them on startup |
| Slow sink slows all tasks and the Producer | Per task `asyncio.Queue` with bounded size and a drop or block policy |
| No stop without removal, no restart | Add task status transitions and `PATCH /api/v1/tasks/{id}` |
| One Producer only | Map connections to named streams and let tasks subscribe to a stream |
| Samples in a disconnect remainder are lost | Framing with sequence numbers if exactness across reconnects matters |
| stdout output of many tasks interleaves | File or WebSocket sink per task |
| Processing speed is bounded by one Python event loop, about 0.12 million samples per second with 32 regression tasks | Fewer tasks at high rates, running sums for regression, or worker processes |
| A blocked stdout sink stalls all stream processing | Move each sink behind a bounded queue with an explicit overflow policy |
