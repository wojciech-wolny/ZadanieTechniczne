"""Chunked text and binary sample readers."""

import logging
import math
import struct
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

from producer.constants import (
    BINARY_CHUNK_SIZE,
    BINARY_SAMPLE_FORMAT,
    BINARY_SAMPLE_SIZE,
    MAX_TOKEN_LENGTH,
    TEXT_CHUNK_SIZE,
)

logger = logging.getLogger(__name__)


@dataclass
class TextReadState:
    """Carry text reader state between chunks.

    :attr pending: unfinished token from the previous chunk
    :attr skipping_long_token: whether an overlong token continues
    :attr skipped_count: number of skipped tokens in this pass
    """

    pending: str = ""
    skipping_long_token: bool = False
    skipped_count: int = 0


def read_text_samples(path: Path, chunk_size: int = TEXT_CHUNK_SIZE) -> Iterator[float]:
    """Yield finite numbers from a whitespace separated text file with one skip summary per pass.

    :param path: text file path
    :param chunk_size: maximum characters read at once
    :return: iterator of finite samples
    """
    state = TextReadState()
    with path.open("r", encoding="utf-8-sig") as source:
        while chunk := source.read(chunk_size):
            tokens, state = next_text_tokens(state, chunk)
            for token in tokens:
                value = parse_token(token)
                if value is None:
                    state.skipped_count += 1
                    continue
                yield value
    if state.pending:
        value = parse_token(state.pending)
        if value is None:
            state.skipped_count += 1
        else:
            yield value
    if state.skipped_count:
        logger.warning(
            "skipped %s text tokens that are invalid, not finite or longer than %s characters",
            state.skipped_count,
            MAX_TOKEN_LENGTH,
        )


def next_text_tokens(state: TextReadState, chunk: str) -> tuple[list[str], TextReadState]:
    """Take finished tokens from one read and carry the unfinished tail forward.

    :param state: unfinished token and skip state from the previous chunk
    :param chunk: characters just read
    :return: finished tokens and state for the next chunk
    """
    text = state.pending + chunk
    tokens = text.split()
    tokens, skipping_long_token = discard_continued_long_token(
        text,
        tokens,
        state.skipping_long_token,
    )
    tokens, pending = hold_back_unfinished_token(text, tokens)
    pending, skipping_long_token, skipped_long = skip_pending_over_limit(
        pending,
        skipping_long_token,
    )
    return tokens, TextReadState(
        pending=pending,
        skipping_long_token=skipping_long_token,
        skipped_count=state.skipped_count + skipped_long,
    )


def discard_continued_long_token(
    text: str,
    tokens: list[str],
    skipping_long_token: bool,
) -> tuple[list[str], bool]:
    """Drop the continuation of an overlong token until whitespace appears.

    :param text: pending token joined with the new chunk
    :param tokens: whitespace split of that text
    :param skipping_long_token: whether the previous chunk ended inside an overlong token
    :return: tokens after the overlong token, and whether that token still continues
    """
    if not skipping_long_token:
        return tokens, False
    token_continues = tokens == [text]
    if not text[0].isspace():
        tokens = tokens[1:]
    return tokens, token_continues


def hold_back_unfinished_token(text: str, tokens: list[str]) -> tuple[list[str], str]:
    """Hold back the last token when the chunk does not end on whitespace.

    :param text: pending token joined with the new chunk
    :param tokens: tokens that are complete or still open
    :return: finished tokens and the unfinished tail
    """
    if tokens and not text[-1].isspace():
        return tokens[:-1], tokens[-1]
    return tokens, ""


def skip_pending_over_limit(
    pending: str,
    skipping_long_token: bool,
) -> tuple[str, bool, int]:
    """Drop a carried token once it passes the length limit.

    :param pending: unfinished token
    :param skipping_long_token: whether an overlong token already continues
    :return: pending token, whether an overlong token continues, new skips
    """
    if len(pending) > MAX_TOKEN_LENGTH:
        return "", True, 1
    return pending, skipping_long_token, 0


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
