"""Shared wire format."""

import struct

SAMPLE_FORMAT = "<d"
SAMPLE_SIZE = 8


def pack_samples(samples: list[float]) -> bytes:
    """Encode samples as little endian float64 bytes.

    :param samples: sample values
    :return: wire bytes
    """
    count = len(samples)
    if count == 0:
        return b""
    return struct.pack(f"<{count}d", *samples)
