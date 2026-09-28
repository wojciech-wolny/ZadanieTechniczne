# TCP wire protocol

## Format

A raw, unframed byte stream of samples. Every sample is an **IEEE 754 float64, little endian** (`struct` format `<d`, 8 bytes). No header, no length prefix, no delimiters. Closing the connection ends the stream.

```
| sample 0 (8 bytes) | sample 1 (8 bytes) | sample 2 (8 bytes) | ...
```

## Why this format

| Option | Verdict |
|--------|---------|
| Text, whitespace separated | Readable, but variable length tokens need a tokenizer on the server and are larger |
| float32 LE | Matches the binary input, but loses precision of text input such as `15.36939640848985` |
| **float64 LE** | Fixed size, trivial reassembly, preserves float32 exactly and avoids an additional float32 downcast for text input |
| Framed messages (length prefix, JSON) | Unneeded: there is one message type and no metadata |

## Reassembly rule

TCP delivers bytes, not samples. The server keeps a remainder of at most 7 bytes:

```
data = remainder + chunk
complete = len(data) // 8 * 8
samples = struct.iter_unpack("<d", data[:complete])
remainder = data[complete:]
```

This makes results independent of packet and read sizes (STR-1, STR-2). On disconnect a non empty remainder is discarded and logged as a truncated sample. A decoded NaN or infinity is a protocol error: the server logs it and closes that connection before dispatching the containing batch.

## Connection rules

1. Default endpoint `127.0.0.1:9000`, configurable on both sides.
2. The server accepts one Producer at a time. A second connection is closed immediately and logged (SRV-1).
3. After the Producer disconnects, the server keeps running. Complete samples already dispatched, task statistics and partial algorithm windows remain. The next Producer therefore continues the same logical stream and may complete an earlier window (SRV-6). See [decisions.md](decisions.md), decision 6.
4. The Producer does not reconnect automatically; it exits with a non zero code when the connection fails or drops.
