"""Reassemble little endian float64 samples from TCP chunks."""

import logging
import math
import struct

from common.protocol import SAMPLE_FORMAT, SAMPLE_SIZE

logger = logging.getLogger(__name__)


class NonFiniteSampleError(Exception):
    """Raised when a decoded sample is not a finite number.

    :attr samples: finite samples decoded before the invalid one
    """

    def __init__(self, samples: list[float]) -> None:
        super().__init__("sample is not finite")
        self.samples = samples


class SampleDecoder:
    """Decode an unframed little endian float64 byte stream."""

    def __init__(self) -> None:
        self._remainder = b""

    def decode(self, chunk: bytes) -> list[float]:
        """Decode complete samples from a chunk and keep a short remainder.

        :param chunk: next bytes read from the socket
        :return: finite samples contained in this chunk
        :raises NonFiniteSampleError: when a sample is NaN or infinity
        """
        data = self._remainder + chunk
        complete_length = (len(data) // SAMPLE_SIZE) * SAMPLE_SIZE
        self._remainder = data[complete_length:]
        samples: list[float] = []
        for (value,) in struct.iter_unpack(SAMPLE_FORMAT, data[:complete_length]):
            if not math.isfinite(value):
                self._remainder = b""
                raise NonFiniteSampleError(samples)
            samples.append(value)
        return samples

    def discard_remainder(self) -> None:
        """Drop a partial sample left after a disconnect."""
        if self._remainder:
            logger.warning("discarding truncated sample of %s bytes", len(self._remainder))
        self._remainder = b""
