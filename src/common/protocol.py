"""Shared wire format and default endpoints."""

import struct

SAMPLE_FORMAT = "<d"
SAMPLE_SIZE = 8
DEFAULT_TCP_HOST = "127.0.0.1"
DEFAULT_TCP_PORT = 9000
DEFAULT_HTTP_HOST = "127.0.0.1"
DEFAULT_HTTP_PORT = 8000


def pack_samples(samples: list[float]) -> bytes:
    """Encode samples as little endian float64 bytes.

    :param samples: sample values
    :return: wire bytes
    """
    count = len(samples)
    if count == 0:
        return b""
    return struct.pack(f"<{count}d", *samples)
