"""Component tests for result sinks and the ASCII mapping."""

import io
import math
import sys

import pytest

from server.schemas import AverageConfig, PassthroughConfig, TaskCreate
from server.services.sinks import NullSink, StdoutSink, convert_to_ascii
from server.services.tasks import ProcessingTask


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        (-1, "#"),
        (-0.4, "\x00"),
        (0, "\x00"),
        (10, "\n"),
        (65, "A"),
        (65.4, "A"),
        (65.5, "B"),
        (66, "B"),
        (66.5, "B"),
        (111, "o"),
        (127, "\x7f"),
        (127.5, "#"),
        (128, "#"),
        (137, "#"),
    ],
    ids=[
        "negative",
        "rounded_to_zero",
        "lower_bound",
        "newline",
        "upper_letter",
        "rounded_down",
        "half_up_to_even",
        "letter_b",
        "half_down_to_even",
        "letter_o",
        "upper_bound",
        "half_above_ascii",
        "above_ascii",
        "example_hash",
    ],
)
def test_convert_to_ascii_boundaries(value: float, expected: str) -> None:
    """Verify OUT-4: rounded values map to ASCII or a hash mark."""
    assert convert_to_ascii(value) == expected


@pytest.mark.parametrize(
    "value",
    [math.inf, -math.inf, math.nan],
    ids=["positive_infinity", "negative_infinity", "nan"],
)
def test_convert_to_ascii_non_finite_is_hash(value: float) -> None:
    """Verify OUT-4: a non finite result is outside 0..127 and becomes a hash mark."""
    assert convert_to_ascii(value) == "#"


def test_stdout_task_with_overflowing_average_keeps_running(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify OUT-3 and OUT-4: an average that overflows to infinity prints a hash mark."""
    stream = io.StringIO()
    monkeypatch.setattr(sys, "stdout", stream)
    task = ProcessingTask.create(
        TaskCreate(algorithm=AverageConfig(name="average", window_size=2), sink="stdout")
    )

    task.process_samples([1e308, 1e308])

    assert stream.getvalue() == "#"
    assert task.status == "running"


def test_write_results_null_sink_discards_values() -> None:
    """Verify OUT-2: the null sink accepts results and stores nothing."""
    sink = NullSink()

    assert sink.write_results([65.0, 137.0]) is None
    sink.close()


def test_null_task_does_not_write_standard_output(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify OUT-2: a null task does not write result text."""
    stream = io.StringIO()
    monkeypatch.setattr(sys, "stdout", stream)
    task = ProcessingTask.create(
        TaskCreate(algorithm=PassthroughConfig(name="passthrough"), sink="null")
    )

    task.process_samples([65.0, 66.0])

    assert stream.getvalue() == ""
    assert task.read_statistics()["samples_processed"] == 2


def test_stdout_task_writes_ascii(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify OUT-1 and OUT-3: a stdout task writes ASCII results."""
    stream = io.StringIO()
    monkeypatch.setattr(sys, "stdout", stream)
    task = ProcessingTask.create(
        TaskCreate(algorithm=PassthroughConfig(name="passthrough"), sink="stdout")
    )

    task.process_samples([65.0, 66.0, 10.0, 137.0])

    assert stream.getvalue() == "AB\n#"


def test_close_stdout_sink_leaves_the_stream_open() -> None:
    """Verify OUT-3: closing the stdout sink does not close the caller stream."""
    stream = io.StringIO()
    sink = StdoutSink(stream)

    sink.write_results([65.0])
    sink.close()

    assert stream.getvalue() == "A"
    assert not stream.closed
