# Shared protocol context

Use this file when changing `src/common/`. Both processes import this package. It is the only home for the TCP sample layout and the default bind addresses.

| Name | Value | Used by |
|------|-------|---------|
| `SAMPLE_FORMAT` | `"<d"` | Producer `pack_samples`, server `SampleDecoder` |
| `SAMPLE_SIZE` | `8` | Decoder remainder math |
| `DEFAULT_TCP_HOST` / `DEFAULT_TCP_PORT` | `127.0.0.1` / `9000` | Producer CLI and server `Settings` |
| `DEFAULT_HTTP_HOST` / `DEFAULT_HTTP_PORT` | `127.0.0.1` / `8000` | Server `Settings` |

`pack_samples([])` returns `b""`. A non empty list is `struct.pack(f"<{count}d", *samples)`.

Binary input files are float32 (`<f`, 4 bytes). That constant stays in `src/producer/readers.py` as `BINARY_SAMPLE_FORMAT`. Do not reuse `SAMPLE_FORMAT` for file reads.

Changing `SAMPLE_FORMAT` or `SAMPLE_SIZE` requires the same change on both sides and an update of `docs/wire-protocol.md`.
