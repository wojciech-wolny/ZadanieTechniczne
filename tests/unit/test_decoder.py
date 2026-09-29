"""Component tests for TCP sample reassembly."""

import math
import random
import struct

import pytest

from common.protocol import SAMPLE_FORMAT, SAMPLE_SIZE, pack_samples
from server.services.decoder import NonFiniteSampleError, SampleDecoder


def decode_chunks(chunks: list[bytes]) -> list[float]:
    """Decode a sequence of chunks with one decoder.

    :param chunks: successive reads
    :return: finite samples
    """
    decoder = SampleDecoder()
    samples: list[float] = []
    for chunk in chunks:
        samples.extend(decoder.decode(chunk))
    return samples


def random_chunks(payload: bytes) -> list[bytes]:
    """Split a payload into pieces of one to seven bytes.

    :param payload: complete wire bytes
    :return: chunks that concatenate to the payload
    """
    generator = random.Random(1)
    chunks: list[bytes] = []
    index = 0
    while index < len(payload):
        size = generator.randint(1, SAMPLE_SIZE - 1)
        chunks.append(payload[index : index + size])
        index += size
    return chunks


def test_decode_splits_match_the_whole_payload() -> None:
    """Verify STR-1 and SRV-9: read size does not change the decoded samples."""
    samples = [1.0, -2.5, 3.25, 4.0]
    payload = pack_samples(samples)
    byte_chunks = [payload[index : index + 1] for index in range(len(payload))]
    fixed_chunks = [payload[:3], payload[3:8], payload[8:15], payload[15:]]

    assert decode_chunks([payload]) == samples
    assert decode_chunks(byte_chunks) == samples
    assert decode_chunks(fixed_chunks) == samples
    assert decode_chunks(random_chunks(payload)) == samples


def test_decode_non_finite_sample_rejects_the_batch() -> None:
    """Verify STR-1: a non finite sample is rejected and the next chunk stays aligned."""
    decoder = SampleDecoder()
    payload = pack_samples([1.0, math.nan])

    with pytest.raises(NonFiniteSampleError) as error:
        decoder.decode(payload)

    assert error.value.samples == [1.0]
    assert decoder.decode(struct.pack(SAMPLE_FORMAT, 2.0)) == [2.0]


def test_discard_remainder_drops_a_partial_sample() -> None:
    """Verify STR-2: a short tail is ignored and the next chunk starts clean."""
    decoder = SampleDecoder()
    decoder.decode(b"\x01\x02\x03")

    decoder.discard_remainder()

    assert decoder.decode(struct.pack(SAMPLE_FORMAT, 5.0)) == [5.0]
