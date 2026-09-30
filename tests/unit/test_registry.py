"""Component tests for task creation, statistics and dispatch."""

import io
import sys

import pytest

from server.schemas import (
    AlgorithmConfig,
    AverageConfig,
    LinearRegressionConfig,
    PassthroughConfig,
    TaskCreate,
)
from server.services.algorithms import ALGORITHM_FACTORIES, Algorithm
from server.services.registry import TaskLimitError, TaskRegistry
from server.services.sinks import SINK_FACTORIES
from server.services.tasks import ProcessingTask


class FailingAlgorithm:
    """Raise when a sample arrives."""

    def process_sample(self, sample: float) -> float | None:
        """Reject the sample.

        :param sample: incoming sample value
        :return: never
        :raises ValueError: always
        """
        raise ValueError(sample)

    def read_statistics(self) -> dict[str, float | int | None]:
        """Return no extra statistics.

        :return: empty mapping
        """
        return {}


class ClosingSink:
    """Record that close was called."""

    def __init__(self) -> None:
        self.closed = False

    def write_results(self, results: list[float]) -> None:
        """Ignore results.

        :param results: numeric results to drop
        """
        return

    def close(self) -> None:
        """Remember that the sink was closed."""
        self.closed = True


def passthrough_task() -> TaskCreate:
    """Build a passthrough task that discards results.

    :return: task request
    """
    return TaskCreate(algorithm=PassthroughConfig(name="passthrough"), sink="null")


def test_dispatch_delivers_samples_to_every_running_task() -> None:
    """Verify SRV-3 and SRV-4: every running task receives the same samples."""
    registry = TaskRegistry()
    first = registry.create_task(passthrough_task())
    second = registry.create_task(
        TaskCreate(algorithm=AverageConfig(name="average", window_size=2), sink="null")
    )

    registry.dispatch([1.0, 3.0])

    assert first.read_statistics()["samples_processed"] == 2
    assert second.read_statistics()["samples_processed"] == 2
    assert second.read_statistics()["last_result"] == 2


def test_dispatch_includes_a_task_created_before_samples() -> None:
    """Verify SRV-7: a task created first processes every later sample."""
    registry = TaskRegistry()
    task = registry.create_task(passthrough_task())

    registry.dispatch([1.0, 2.0, 3.0])

    assert task.read_statistics()["samples_processed"] == 3


def test_dispatch_skips_tasks_created_after_the_batch() -> None:
    """Verify SRV-8: a new task sees only samples dispatched after it exists."""
    registry = TaskRegistry()
    registry.dispatch([1.0, 2.0])
    task = registry.create_task(passthrough_task())

    registry.dispatch([9.0])

    assert task.read_statistics()["samples_processed"] == 1


def test_process_samples_counts_every_sample() -> None:
    """Verify TSK-2: samples are counted even when the sink discards results."""
    task = ProcessingTask.create(passthrough_task())

    task.process_samples([1.0, 2.0, 3.0])

    assert task.read_statistics()["samples_processed"] == 3


def test_task_statistics_depend_on_the_algorithm() -> None:
    """Verify TSK-4: average and linear regression expose different statistics."""
    average = ProcessingTask.create(
        TaskCreate(algorithm=AverageConfig(name="average", window_size=2), sink="null")
    )
    regression = ProcessingTask.create(
        TaskCreate(
            algorithm=LinearRegressionConfig(name="linear_regression", window_size=2),
            sink="null",
        )
    )

    average.process_samples([1.0, 3.0])
    regression.process_samples([0.0, 2.0])

    assert set(average.read_statistics()) == {
        "samples_processed",
        "windows_processed",
        "last_result",
    }
    assert average.read_statistics()["last_result"] == 2
    assert set(regression.read_statistics()) == {
        "samples_processed",
        "windows_processed",
        "last_slope",
        "min_slope",
        "max_slope",
    }
    assert regression.read_statistics()["last_slope"] == 2


def test_create_task_at_limit_raises() -> None:
    """Verify API-1: the registry rejects a task past its limit."""
    registry = TaskRegistry(max_tasks=1)
    registry.create_task(passthrough_task())

    with pytest.raises(TaskLimitError):
        registry.create_task(passthrough_task())


def test_list_tasks_follows_creation_order() -> None:
    """Verify API-2: tasks are listed from oldest to newest."""
    registry = TaskRegistry()
    first = registry.create_task(passthrough_task())
    second = registry.create_task(
        TaskCreate(algorithm=AverageConfig(name="average", window_size=2), sink="null")
    )

    listed = registry.list_tasks()

    assert [task.task_id for task in listed] == [first.task_id, second.task_id]


def test_remove_task_stops_further_samples() -> None:
    """Verify API-4: a removed task receives no later samples."""
    registry = TaskRegistry()
    task = registry.create_task(passthrough_task())

    removed = registry.remove_task(task.task_id)
    registry.dispatch([1.0])

    assert removed is task
    assert registry.find_task(task.task_id) is None
    assert task.read_statistics()["samples_processed"] == 0


def test_remove_task_unknown_id_returns_none() -> None:
    """Verify API-4: removing a missing task does nothing."""
    registry = TaskRegistry()

    assert registry.remove_task("missing") is None


def test_remove_task_closes_the_sink(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify API-4: removing a task closes its sink."""
    sink = ClosingSink()
    monkeypatch.setitem(SINK_FACTORIES, "null", lambda: sink)
    registry = TaskRegistry()
    task = registry.create_task(passthrough_task())

    registry.remove_task(task.task_id)

    assert sink.closed is True


def test_close_all_closes_every_sink_even_when_one_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify API-4: closing the registry closes each task sink and survives a failing close."""
    failing_sink = ClosingSink()
    healthy_sink = ClosingSink()

    def fail_on_close() -> None:
        raise OSError

    failing_sink.close = fail_on_close
    sinks = iter([failing_sink, healthy_sink])
    monkeypatch.setitem(SINK_FACTORIES, "null", lambda: next(sinks))
    registry = TaskRegistry()
    registry.create_task(passthrough_task())
    registry.create_task(passthrough_task())

    registry.close_all()

    assert healthy_sink.closed is True


def test_dispatch_marks_failing_task_and_continues(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify API-3: one failing task stays queryable and the other still runs."""
    stream = io.StringIO()
    monkeypatch.setattr(sys, "stdout", stream)

    def build_failing(_config: AlgorithmConfig) -> Algorithm:
        return FailingAlgorithm()

    registry = TaskRegistry()
    healthy = registry.create_task(
        TaskCreate(algorithm=PassthroughConfig(name="passthrough"), sink="stdout")
    )
    monkeypatch.setitem(ALGORITHM_FACTORIES, "passthrough", build_failing)
    failing = registry.create_task(
        TaskCreate(algorithm=PassthroughConfig(name="passthrough"), sink="null")
    )

    registry.dispatch([65.0])
    registry.dispatch([66.0])

    assert failing.status == "failed"
    assert failing.error == "ValueError"
    assert registry.find_task(failing.task_id) is failing
    assert failing.read_statistics()["samples_processed"] == 0
    assert healthy.status == "running"
    assert healthy.read_statistics()["samples_processed"] == 2
    assert stream.getvalue() == "AB"
