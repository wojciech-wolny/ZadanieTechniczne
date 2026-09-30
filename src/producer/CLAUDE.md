# Producer context

Use this file when changing anything under `src/producer/`. The repository map is `CLAUDE.md`. The wire constants live in `src/common/CLAUDE.md`.

The Producer is a synchronous TCP client. It does not import FastAPI and it does not load a whole file.

## CLI

Entry point `src/producer/__main__.py`, command `producer`.

| Argument | Rule |
|----------|------|
| `input_file` | Required path, opened read only inside the reader |
| `--format` | `txt` or `bin`, default `txt` |
| `--rate` | Finite samples per second, from 0.1 to 1000000 |
| `--limit` | Integer of 0 or more. `0` repeats the file until the process is stopped |
| `--host` / `--port` | Default `127.0.0.1:9000` |

A failed connection, or a file pass that yields no finite samples, exits with status 1. Connect timeout is 5 seconds.

## Pipeline

`SAMPLE_READERS[format](path)` yields samples. `repeat_samples` reopens the file after each pass. `limit_samples` stops after `limit` yielded samples when `limit > 0`. `send_samples` groups them into about 20 ms batches, writes `pack_samples` bytes, and paces with `time.monotonic` deadlines. The first batch is sent immediately. When the schedule is already late, the next batch is sent immediately.

## File formats

These are input formats. They are different from the TCP format.

| `--format` | On disk | Reader |
|------------|---------|--------|
| `txt` | Whitespace separated numbers, 64 KiB character chunks | `read_text_samples` carries a partial token. A token longer than 1024 characters is skipped. Invalid and non finite tokens are skipped, with one warning per pass |
| `bin` | Little endian float32, 4 bytes, format `<f` | `read_binary_samples` reads multiples of 4 bytes. A short tail is ignored with a warning. Non finite values are skipped |

A complete pass with zero finite samples raises `EmptyInputError`.

## What the server receives

Every yielded finite sample is packed as little endian float64 (`<d`, 8 bytes) by `common.protocol.pack_samples`. There is no header and no delimiter. Keep that call as the only encoder.
