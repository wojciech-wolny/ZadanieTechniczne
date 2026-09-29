# Proposal: packet based wire protocol

Status: **proposed**, not yet accepted. Alternative to the raw sample stream in [wire-protocol.md](wire-protocol.md).

## Problem

The raw stream is the simplest correct format, but the server cannot tell:

1. a clean end of stream from a Producer crash or network failure (SRV-6),
2. a corrupted or foreign client from a valid one (anything is "some floats"),
3. which protocol version the client speaks, once the format evolves.

## Proposal

Samples travel in packets. Each packet is a fixed 8 byte header followed by a payload.

```
| magic 2B | version 1B | type 1B | count 4B | payload: count x float64 |
```

| Field | Struct | Value |
|-------|--------|-------|
| magic | `2s` | `b"SP"` |
| version | `B` | `1` |
| type | `B` | `1` DATA, `2` END |
| count | `I` | number of samples in the payload; `0` for END |
| payload | `count * d` | samples, float64 |

Header struct `<2sBBI`, sample struct `<d`, everything little endian. Both live in `src/common/protocol.py`.

### Packet types

| Type | Sent when | Server reaction |
|------|-----------|-----------------|
| DATA | every pacing batch (about 20 ms of samples) | decode payload, dispatch to tasks |
| END | Producer reached its limit or the user stopped it | log clean end, close connection |

A connection closed without END is logged as an aborted stream. The partial packet is discarded.

### Limits

1. `count` at most `8192` (64 KiB payload). Larger values are a protocol error, which bounds server memory per read.
2. Wrong magic, unknown version or unknown type is a protocol error: the server logs it and closes the connection. No resynchronisation attempt (KISS).

### Reassembly

Same principle as today, with a header step:

```
buffer += chunk
while len(buffer) >= HEADER_SIZE:
    header = parse_header(buffer)          raises ProtocolError
    packet_size = HEADER_SIZE + header.count * SAMPLE_SIZE
    if len(buffer) < packet_size:
        break
    handle_packet(header, buffer[HEADER_SIZE:packet_size])
    del buffer[:packet_size]
```

The buffer never exceeds one maximum packet plus one read. Results stay independent of TCP chunk sizes (STR-1, STR-2), and tests keep splitting the byte stream at every position.

## Comparison

| Aspect | Raw stream | Packets |
|--------|------------|---------|
| Code size | smallest | about 40 more lines plus tests |
| Clean end vs crash | not distinguishable | END packet |
| Invalid client detection | none | magic and version |
| Format evolution | breaking change | new version or packet type |
| Memory bound | 7 byte remainder | one packet, max 64 KiB |
| Overhead | 0 | 8 bytes per batch, below 1 % |
| Fits the pacer | yes | naturally: one batch is one packet |

## Deliberately left out (YAGNI)

| Feature | Why not now | Add when |
|---------|-------------|----------|
| Sequence numbers | TCP already guarantees order and no gaps inside one connection | resuming after reconnect or passing through a broker |
| Checksum | TCP checksums every segment | transport without integrity checks |
| HELLO packet with metadata (rate, format, stream name) | nothing on the server uses it | several producers or named streams |
| Heartbeat | an idle Producer is not an error | detecting silent half open connections |

## Impact on the plan

1. Stage 3: `SampleDecoder` becomes `PacketDecoder` returning samples and an end flag; `ProtocolError` closes the connection.
2. Stage 5: the Producer wraps each pacing batch with `encode_data_packet(samples)` and sends `encode_end_packet()` before closing.
3. `GET /stream` gains `last_disconnect: "clean" | "aborted" | null`.
4. New tests: header split across reads, packet split at every byte, oversized count, wrong magic, END handling, missing END.

## Recommendation

Adopt it. It costs little, maps directly to "properly handle client disconnections" (SRV-6), rejects garbage input, and gives a versioned format that can grow with the microservice path. If accepted, `wire-protocol.md` is replaced by this document and `decisions.md` decision 2 is updated.
