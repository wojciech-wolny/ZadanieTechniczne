# Hardening

Robustness controls in the current Producer and Processing Server, the gaps found by the Stage 7 security review, and the plan to close them. Authentication, a second concurrent Producer, persistence, and production deployment are out of scope; see the limitations table in [README.md](../README.md).

Review status: the first review found no critical or high issues, 2 medium and 11 low, verdict changes required. Every finding below was reproduced with a probe against the code at that time unless marked otherwise. H1 through H13 are done. The follow up review of the fixes found no critical, high, or medium issues and **approved** them. Its low findings are fixed: a `Content-Length` too long for `int` returned 500, and `PRODUCER_IDLE_SECONDS` accepted infinity.

## Trust boundary

Both sockets bind to `127.0.0.1` by default. The HTTP API and the TCP sample port have no authentication, so any local process can create tasks and inject samples. Setting `HTTP_HOST` or `TCP_HOST` to another address exposes that port on the chosen interface. An empty value is rejected at startup.

`MAX_TASKS` is at least 1 and defaults to 32. `PRODUCER_IDLE_SECONDS` is above 0 and defaults to 30. Keep it above 10 seconds, the longest gap between samples at the minimum rate of 0.1, or slow Producers are disconnected. Ports, the task maximum, and the idle timeout are operator settings, so they have no upper bound. A port outside 0 through 65535 fails at startup with an `OverflowError` from the socket. Unknown environment variables are ignored.

## Current controls

### Memory

Every buffer below has a fixed bound. Neither application loads an input file or keeps the sample stream.

| Bound | Value | What it limits |
|-------|-------|----------------|
| Text read | 65,536 characters | One file read |
| Text token carry | 1,024 characters | A longer token is skipped and does not grow across the file |
| Binary read | 65,536 bytes | One file read |
| Binary carry | at most 3 bytes | A float32 split across reads |
| TCP read | 65,536 bytes | One socket read |
| Decoder remainder | at most 7 bytes | A float64 split across reads |
| Send batch | about 20 ms of samples, at least 1 | 20,000 samples at the rate cap |
| Sample rate | finite, from 0.1 to 1,000,000 per second | CLI input, batch size, and the longest sleep |
| Sample limit | 0 or more | CLI input |
| Window | at most 100,000 samples | State of one windowed task |
| Tasks | 32 by default, set through `MAX_TASKS` | Tasks stored at once |
A full window holds about 3.2 MB, so the default 32 tasks hold about 100 MB and the maximum 256 tasks about 820 MB. One 64 KiB read dispatched to 32 linear regression tasks blocks the event loop for about 65 ms (measured).

No module under `src/` creates a temporary file or calls `eval`, `exec`, `pickle`, or a shell. Input files are opened read only. `scripts/demo.py` starts processes with list arguments and no shell.

### Producer input

The CLI accepts `txt` or `bin` only. The rate and limit are validated before any socket is opened.

Text tokens that are not finite numbers or longer than 1,024 characters are skipped, and each file pass logs one warning on stderr with the skipped count. Non finite float32 values are skipped the same way, with one summary per pass. A binary tail shorter than 4 bytes is ignored with a warning. A full pass with no samples stops the Producer with status 1.

A failed connection, a missing file, or a text decode error prints one line and exits with status 1. Ctrl+C exits with status 0. The Producer does not reconnect. The connect times out after 5 seconds, and the socket is then blocking again so `sendall` applies backpressure.

### TCP stream

Wire format and reassembly are in [wire-protocol.md](wire-protocol.md).

1. The receiver accepts one Producer. The Producer slot is checked and taken with no `await` in between, so two connections cannot both get it. A second connection is closed without being read, and the first keeps its slot. The first rejection is logged, then at most one warning every 10 seconds with the count since the last warning.
2. On disconnect or on an error in the read loop, the server drops the partial sample, clears the connected flag, closes the writer, and keeps listening. Task windows stay in memory, and the next Producer continues the stream.
3. NaN or infinity closes that connection. Finite samples before the bad value are dispatched first, so the result does not depend on read boundaries (H13). The decoder clears its remainder, so the next Producer starts on an 8 byte boundary.
4. Each read waits at most `PRODUCER_IDLE_SECONDS`, 30 by default. A silent Producer is logged and closed, the slot is freed, and the next Producer is accepted. `SO_KEEPALIVE` is set on the accepted socket.

### Tasks and the API

Request and error shapes are in [rest-api.md](rest-api.md).

Task identifiers are server generated UUID4 strings, used only as dictionary keys. Algorithm and sink names are a closed `Literal` set, with no dynamic import. Unknown fields, unknown names, and window sizes outside 1 to 100,000 (average) or 2 to 100,000 (linear regression) return 422. `window_size` is strict, so `"6"`, `6.0`, and `true` also return 422. A full registry returns 409, and a missing task returns 404. Deeply nested JSON returns 400.

Dispatch works on a snapshot of the running tasks. Creation and deletion take effect on the next batch.

If one task raises, only that task is marked `failed` and its sink is closed. `error` holds the exception class name only, with no message, traceback, or path. A non finite statistic becomes JSON `null`, and the stdout sink writes `#` for a non finite result. A NaN slope is reported as `last_slope` but does not change `min_slope` or `max_slope`.

FastAPI runs with debug off, so an unexpected error returns a generic 500. `/docs`, `/redoc`, and `/openapi.json` are always served.

Stdout writes run on the event loop, so a blocked terminal stalls every task and the Producer. OUT-4 maps 0 through 127 to characters. That range includes ESC and other control codes, so the Producer can send ANSI escape sequences to the server terminal (accepted, see Residual risk).

### Dependencies and CI

Runtime dependencies are FastAPI, Uvicorn, and Pydantic Settings. `uv.lock` pins them. `pyproject.toml` sets floors near the locked versions: `fastapi>=0.141`, `uvicorn>=0.54`, `pydantic-settings>=2.15`, and `h11>=0.16`. `requires-python` is `>=3.13`, and the interpreter pin is 3.13.7. `pip-audit` reports no known vulnerabilities. It audits the installed environment, so it includes dev tools and skips the local package.

The workflow in [ci.md](ci.md) meets these rules:

- **Permissions and triggers:** it grants `contents: read`, skips pull requests from forks, and does not use `pull_request_target`.
- **Runner:** it runs on a self hosted Linux runner, without Docker.
- **Actions:** it uses `actions/checkout@v4` with `persist-credentials: false`, and `astral-sh/setup-uv@v6`.
- **Job:** it times out after 10 minutes, cancels superseded runs, and installs with `uv sync --locked`.
- **Audit:** `pip-audit` is pinned to major version 2. It still audits the installed environment, not the lock.

These controls work only after `src/`, `tests/`, `pyproject.toml`, `uv.lock`, `.python-version`, and `.github/` are committed and pushed.

## Findings and plan

The plan follows the project rules: the simplest change, one home for each constant, and a test for each finding. Each item names the requirement it protects.

### Priority 1: medium

**H1. Unbounded HTTP request body.** `src/server/main.py`. Uvicorn and Starlette set no body limit, and FastAPI reads the full body before validation. One large `POST /api/v1/tasks` can use up server memory, which breaks the bounded memory goal of SRV-9.
Fix: an ASGI middleware that returns 413 when `Content-Length` or the streamed body exceeds `MAX_REQUEST_BYTES = 16384`. Also pass `limit_concurrency=64` to `uvicorn.run`.
Test: a 17 KiB body returns 413, a valid body still returns 201, and a body without `Content-Length` that goes over the limit returns 413.
Status: withdrawn. The task excludes authentication and production deployment, and any local process can already create tasks and inject samples, so the middleware and `limit_concurrency` cost more code than they protect. The README lists the missing body limit as a limitation.

**H2. No idle timeout or keepalive on the Producer socket.** `src/server/services/receiver.py:92`. A silent or half open Producer, such as a crashed host or a lost network with no FIN, holds the only slot forever. SRV-6 then fails and only a restart recovers.
Fix: wrap each read in `asyncio.timeout(settings.producer_idle_seconds)` with a default of 30, and set `SO_KEEPALIVE` on the accepted socket. Add `PRODUCER_IDLE_SECONDS` to `Settings` and the README table.
Test: with a 0.2 s timeout, a connection that sends nothing is closed, `producer_connected` becomes false, and a second Producer is then accepted.
Status: done.

### Priority 2: low, crash or wrong result

**H3. Very small rate crashes the Producer.** `src/producer/__main__.py:29`. `--rate 1e-300` passes validation, and `time.sleep(1e300)` then raises `OverflowError` with a traceback. Rates just above the overflow sleep for years. Protects PRD-5.
Fix: `MIN_SAMPLE_RATE = 0.1` and reject lower rates in `parse_rate`, with the message updated. Update the README option table. The minimum keeps the gap between samples at 10 s, below the default `PRODUCER_IDLE_SECONDS` of 30 (H2). A lower minimum such as 0.001 would let the server disconnect a valid slow Producer.
Test: boundary values `0.09` rejected and `0.1` accepted.
Status: done.

**H4. Huge limit crashes the Producer.** `src/producer/__main__.py:48`. `itertools.islice` raises `ValueError` for a limit above `sys.maxsize`, after the connection is open. Protects PRD-6.
Fix: reject `limit > sys.maxsize` in `parse_limit`.
Test: `sys.maxsize` accepted, `sys.maxsize + 1` rejected.
Status: withdrawn. Nobody passes a limit that large, and the failure is a traceback, not a wrong result. `parse_limit` still rejects a negative limit, which `islice` also refuses.

**H5. No connect timeout.** `src/producer/__main__.py:104`. An unreachable host blocks until the operating system gives up, about 21 s on Windows and about 2 minutes on Linux. Protects PRD-1.
Fix: `socket.create_connection(address, timeout=CONNECT_TIMEOUT_SECONDS)` with 5 s, then `connection.settimeout(None)` so `sendall` still blocks for backpressure.
Test: a mocked `create_connection` receives the timeout, and the returned socket is set back to blocking.
Status: done.

**H6. One NaN slope freezes min and max.** `src/server/services/algorithms.py:146`. If the first slope is NaN, every later comparison is false, so `min_slope` and `max_slope` stay NaN, reported as `null`, even after finite windows. Reproduced with the window `1e308 1e308` followed by finite windows. Protects ALG-5.
Fix: update `min_slope` and `max_slope` only when the slope is finite. `last_slope` keeps the raw value.
Test: a NaN window followed by windows with slope 5 and slope `-5` gives `min_slope` `-5` and `max_slope` 5.
Status: done.

**H7. Loose `window_size` typing.** `src/server/schemas.py:33,45`. `"6"`, `6.0`, and `true` are accepted, and `true` becomes a window of 1. Protects API-5.
Fix: `Field(ge=..., le=..., strict=True)` on both window sizes.
Test: add `"6"`, `6.0`, and `true` to the 422 parametrization in `tests/integration/test_api.py`.
Status: done.

**H8. Unbounded settings.** `src/server/settings.py:28,30,32`. An empty `TCP_HOST` or `HTTP_HOST` binds every interface, and `MAX_TASKS` has no maximum.
Fix: `min_length=1` on both hosts and `le=256` on `max_tasks`. State the memory cost per task in the README.
Test: settings built from an empty host or `MAX_TASKS=257` raise a validation error.
Status: kept for the empty host only, which `asyncio` binds on every interface. The `MAX_TASKS` maximum was withdrawn because the operator sets that value.

### Priority 3: low, operational

**H9. Log flooding.** `src/producer/readers.py:68,87,90` and `src/server/services/receiver.py:72`. The Producer logs one warning per bad token on every pass, which never ends when `--limit 0`. The server logs one warning per rejected connection.
Fix: count skipped values and log one summary per file pass. Log the first rejected connection, then at most one summary every 10 s with a count.
Test: a file with 1,000 invalid tokens produces one warning per pass.
Status: done.

**H10. API surface advertised.** `src/server/main.py:56,68`. The docs endpoints and the `server` header are always exposed. This matters only on a non loopback bind.
Fix: a `DOCS_ENABLED` setting, default true to keep the README workflow, that sets `docs_url`, `redoc_url`, and `openapi_url` to `None` when false. Pass `server_header=False` to `uvicorn.run`.
Test: with docs disabled, `/docs` returns 404 and `/api/v1/tasks` still works.
Status: withdrawn. The task does not ask for a switch, and the default bind is loopback. The `DOCS_ENABLED` setting and `server_header=False` are gone.

**H11. No dependency floors.** `pyproject.toml:7`. An install that ignores the lock can resolve old releases, for example h11 below 0.16 with a known request smuggling issue.
Fix: floors near the locked versions for `fastapi`, `uvicorn`, and `pydantic-settings`, plus `h11>=0.16`. Refresh `uv.lock`.
Test: `uv sync --locked` passes, and `test_project_targets_python_313` asserts the floors.
Status: done. The floors are asserted in `test_project_sets_dependency_floors`.

**H12. CI credentials and audit scope.** `.github/workflows/ci.yml:23,29`. A persistent self hosted runner keeps the checkout token in `.git/config` during the job. `pip-audit` is resolved unpinned and audits the environment instead of the lock.
Fix: `with: persist-credentials: false` on checkout. Audit the lock with `uv export --frozen --no-dev --no-emit-project | uv run --with pip-audit==2.* pip-audit -r /dev/stdin --no-deps --disable-pip`. Update [ci.md](ci.md).
Test: the pipeline is green and `test_project` checks the workflow settings.
Status: done, with a narrower audit fix. The step is `uv run --with "pip-audit==2.*" pip-audit`, so the tool is pinned but still audits the installed environment instead of the exported lock.

**H13. Finite prefix dropped before a non finite sample.** `src/server/services/decoder.py:34`. Which finite samples reach tasks before the connection closes depends on where the TCP read boundary falls. That departs from STR-1 for invalid input only.
Fix: `NonFiniteSampleError` carries the finite samples decoded before the invalid one. The receiver dispatches them, then closes the connection. Update [wire-protocol.md](wire-protocol.md).
Test: `[1.0, 2.0, nan]` sent in one chunk, per sample, or per byte gives `samples_received` 2 each way.
Status: done.

### Order of work

1. H3, H4, H6, and H7. Each is a small validation change with a boundary test and fixes a crash or a wrong statistic.
2. H1 and H2. These close the two medium findings and add settings, so update the README.
3. H5 and H8.
4. H9, H10, H11, and H12.
5. H13.

After each step, run the CI commands locally: `uv run ruff check .`, `uv run ruff format --check .`, `uv run pytest -q`, and the audit. Then run the `security` agent again on the changed files.

## Residual risk

Accepted in the current design:

| Behavior | Reason |
|----------|--------|
| No authentication | Out of scope. The default bind is localhost |
| Control characters 0 through 31 reach the terminal through the stdout sink | Required by OUT-4. A sink that escapes control codes could be added as a new sink type |
| Synchronous stdout can stall the process | Recorded in [architecture.md](architecture.md). A bounded queue per task is the possible solution |
| Bytes of a sample split by a disconnect are discarded | Unframed protocol. See [wire-protocol.md](wire-protocol.md) |
| Uvicorn header read timeout not verified | Check the uvicorn version in use before binding beyond localhost |
| A local process can keep the only Producer slot by sending one sample more often than every `PRODUCER_IDLE_SECONDS` | Same trust level as no authentication. Named streams or authentication would solve it |
| Uvicorn has no request body size limit and no body read timeout, so a large or slow body can use memory or hold connections | Local denial of service only on the default bind. A reverse proxy with limits would solve it |
| After a burst of rejected Producers, the count since the last warning is not logged if no further rejection arrives | Log volume stays bounded. A periodic flush would report the tail |
