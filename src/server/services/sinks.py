"""Result sinks and the ASCII mapping."""

import math
import sys
from collections.abc import Callable
from typing import Protocol, TextIO


class Sink(Protocol):
    """Consume results produced by a task."""

    def write_results(self, results: list[float]) -> None:
        """Write a batch of results.

        :param results: numeric results to write
        """
        ...

    def close(self) -> None:
        """Release resources held by the sink."""
        ...


class NullSink:
    """Discard every result."""

    def write_results(self, results: list[float]) -> None:
        """Ignore a batch of results.

        :param results: numeric results to drop
        """
        return

    def close(self) -> None:
        """Release nothing because the sink stores no resources."""
        return


class StdoutSink:
    """Write results as ASCII characters to a text stream."""

    def __init__(self, stream: TextIO | None = None) -> None:
        self.stream = sys.stdout if stream is None else stream

    def write_results(self, results: list[float]) -> None:
        """Map a batch to ASCII and write it once.

        :param results: numeric results to encode
        """
        characters: list[str] = []
        for value in results:
            characters.append(convert_to_ascii(value))
        self.stream.write("".join(characters))
        self.stream.flush()

    def close(self) -> None:
        """Flush the stream without closing it."""
        self.stream.flush()


def convert_to_ascii(value: float) -> str:
    """Map a rounded value to a character from 0 to 127 or a hash mark.

    :param value: numeric result
    :return: one character
    """
    if not math.isfinite(value):
        return "#"
    rounded = round(value)
    if rounded < 0 or rounded > 127:
        return "#"
    return chr(rounded)


def build_null_sink() -> Sink:
    """Create a sink that discards results.

    :return: null sink
    """
    return NullSink()


def build_stdout_sink() -> Sink:
    """Create a sink that writes ASCII to standard output.

    :return: stdout sink
    """
    return StdoutSink()


SINK_FACTORIES: dict[str, Callable[[], Sink]] = {
    "null": build_null_sink,
    "stdout": build_stdout_sink,
}
