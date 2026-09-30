# Shared protocol context

Use this file when changing `src/common/`. Both processes import this package. It is the only home for the TCP sample layout. Hosts and ports are operator settings in `.env`. `.env.example` is the template and is not loaded. `load_env_file` reads `.env` with `python-dotenv` and copies values into the process environment when the shell has not set them.

| Name | Value | Used by |
|------|-------|---------|
| `SAMPLE_FORMAT` | `"<d"` | Producer `pack_samples`, server `SampleDecoder` |
| `SAMPLE_SIZE` | `8` | Decoder remainder math |
| `ENV_FILE` | `.env` | `load_env_file`; a shell variable stays |

`pack_samples([])` returns `b""`. A non empty list is `struct.pack(f"<{count}d", *samples)`.

Binary input files are float32 (`<f`, 4 bytes). That constant stays in `src/producer/constants.py` as `BINARY_SAMPLE_FORMAT`. Do not reuse `SAMPLE_FORMAT` for file reads.

Changing `SAMPLE_FORMAT` or `SAMPLE_SIZE` requires the same change on both sides and an update of `docs/wire-protocol.md`.
