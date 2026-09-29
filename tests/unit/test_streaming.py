"""Component tests for repetition, limits and paced sending."""

import itertools
from pathlib import Path

import pytest

from common.protocol import pack_samples
from producer.readers import read_binary_samples, read_text_samples
from producer.streaming import EmptyInputError, limit_samples, repeat_samples, send_samples


class RecordingSocket:
    """Record payloads passed to sendall."""

    def __init__(self) -> None:
        self.payloads: list[bytes] = []

    def sendall(self, payload: bytes) -> None:
        """Store one outgoing payload.

        :param payload: bytes the producer would write
        """
        self.payloads.append(payload)


class ManualClock:
    """Move time only when the pacer waits."""

    def __init__(self) -> None:
        self.now = 0.0
        self.delays: list[float] = []

    def read(self) -> float:
        """Return the current fake time.

        :return: monotonic time
        """
        return self.now

    def wait(self, delay: float) -> None:
        """Record a delay and advance the clock.

        :param delay: seconds the pacer wants to sleep
        """
        self.delays.append(delay)
        self.now += delay


def test_limit_zero_keeps_repeating_the_file(tmp_path: Path) -> None:
    """Verify PRD-6: a limit of zero does not stop the repeated file."""
    path = tmp_path / "samples.txt"
    path.write_text("1 2", encoding="utf-8")
    stream = limit_samples(repeat_samples(path, read_text_samples), 0)

    values = list(itertools.islice(stream, 5))

    assert values == [1.0, 2.0, 1.0, 2.0, 1.0]


@pytest.mark.parametrize(
    ("limit", "expected"),
    [(1, [1.0]), (2, [1.0, 2.0]), (3, [1.0, 2.0, 1.0])],
    ids=["one_sample", "file_length", "above_file_length"],
)
def test_limit_stops_after_the_requested_count(
    tmp_path: Path,
    limit: int,
    expected: list[float],
) -> None:
    """Verify PRD-7 and PRD-8: the file repeats until the limit is reached."""
    path = tmp_path / "samples.txt"
    path.write_text("1 2", encoding="utf-8")

    values = list(limit_samples(repeat_samples(path, read_text_samples), limit))

    assert values == expected


@pytest.mark.parametrize(
    "contents",
    ["", " \n\t", "abc nan"],
    ids=["empty", "whitespace", "invalid"],
)
def test_repeat_text_without_samples_raises(tmp_path: Path, contents: str) -> None:
    """Verify PRD-7: a text pass with no samples is an error."""
    path = tmp_path / "empty.txt"
    path.write_text(contents, encoding="utf-8")

    with pytest.raises(EmptyInputError):
        list(repeat_samples(path, read_text_samples))


def test_repeat_short_binary_raises(tmp_path: Path) -> None:
    """Verify PRD-7: a binary file shorter than one sample is an error."""
    path = tmp_path / "short.bin"
    path.write_bytes(b"\x01\x02")

    with pytest.raises(EmptyInputError):
        list(repeat_samples(path, read_binary_samples))


def test_send_samples_writes_little_endian_float64() -> None:
    """Verify PRD-2 and PRD-10: samples are written as little endian float64 bytes."""
    connection = RecordingSocket()

    send_samples(
        connection,
        iter([1.5, -2.0]),
        1_000_000,
        clock=lambda: 0.0,
        wait=lambda delay: None,
    )

    assert connection.payloads == [pack_samples([1.5, -2.0])]


def test_send_samples_waits_until_the_deadline() -> None:
    """Verify PRD-5: later batches follow the sample rate."""
    clock = ManualClock()
    connection = RecordingSocket()

    send_samples(
        connection,
        iter([1.0, 2.0, 3.0]),
        50,
        clock=clock.read,
        wait=clock.wait,
    )

    assert clock.delays == pytest.approx([0.02, 0.02])
    assert len(connection.payloads) == 3


def test_send_samples_skips_wait_when_behind_schedule() -> None:
    """Verify PRD-5: a late batch is sent without adding delay."""
    ticks = iter([0.0, 5.0])
    connection = RecordingSocket()
    delays: list[float] = []

    send_samples(
        connection,
        iter([1.0, 2.0]),
        50,
        clock=lambda: next(ticks),
        wait=delays.append,
    )

    assert delays == []
    assert len(connection.payloads) == 2
