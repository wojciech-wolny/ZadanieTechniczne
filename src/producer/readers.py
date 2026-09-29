"""Chunked text and binary sample readers."""

import logging
import math
import struct
from collections.abc import Callable, Iterator
from pathlib import Path

logger = logging.getLogger(__name__)

TEXT_CHUNK_SIZE = 65536
BINARY_CHUNK_SIZE = 65536
BINARY_SAMPLE_FORMAT = "<f"
BINARY_SAMPLE_SIZE = 4
MAX_TOKEN_LENGTH = 1024


def read_text_samples(path: Path, chunk_size: int = TEXT_CHUNK_SIZE) -> Iterator[float]:
    """Yield finite numbers from a whitespace separated text file with one skip summary per pass.

    :param path: text file path
    :param chunk_size: maximum characters read at once
    :return: iterator of finite samples
    """
    pending = ""
    skipping_long_token = False
    skipped_count = 0
    with path.open("r", encoding="utf-8") as source:
        while chunk := source.read(chunk_size):
            text = pending + chunk
            pending = ""
            tokens = text.split()
            if skipping_long_token:
                has_whitespace = tokens != [text]
                if not text[0].isspace():
                    tokens = tokens[1:]
                skipping_long_token = not has_whitespace
            if tokens and not text[-1].isspace():
                pending = tokens.pop()
            if len(pending) > MAX_TOKEN_LENGTH:
                skipped_count += 1
                pending = ""
                skipping_long_token = True
            for token in tokens:
                value = parse_token(token)
                if value is None:
                    skipped_count += 1
                    continue
                yield value
    if pending:
        value = parse_token(pending)
        if value is None:
            skipped_count += 1
        else:
            yield value
    if skipped_count:
        logger.warning(
            "skipped %s text tokens that are invalid, not finite or longer than %s characters",
            skipped_count,
            MAX_TOKEN_LENGTH,
        )


def read_binary_samples(path: Path, chunk_size: int = BINARY_CHUNK_SIZE) -> Iterator[float]:
    """Yield finite samples from little endian float32 chunks with one skip summary per pass.

    :param path: binary file path
    :param chunk_size: maximum bytes read at once
    :return: iterator of finite samples
    """
    pending = b""
    skipped_count = 0
    with path.open("rb") as source:
        while chunk := source.read(chunk_size):
            data = pending + chunk
            complete_length = (len(data) // BINARY_SAMPLE_SIZE) * BINARY_SAMPLE_SIZE
            pending = data[complete_length:]
            for (value,) in struct.iter_unpack(BINARY_SAMPLE_FORMAT, data[:complete_length]):
                if not math.isfinite(value):
                    skipped_count += 1
                    continue
                yield value
    if skipped_count:
        logger.warning("skipped %s non finite binary samples", skipped_count)
    if pending:
        logger.warning("ignoring %s trailing bytes shorter than one sample", len(pending))


def parse_token(token: str) -> float | None:
    """Parse one text token as a finite float.

    :param token: one whitespace free word
    :return: the sample, or None when the token is too long, invalid or not finite
    """
    if len(token) > MAX_TOKEN_LENGTH:
        return None
    try:
        value = float(token)
    except ValueError:
        return None
    if not math.isfinite(value):
        return None
    return value


SAMPLE_READERS: dict[str, Callable[[Path], Iterator[float]]] = {
    "txt": read_text_samples,
    "bin": read_binary_samples,
}
