"""One processing task: algorithm, sink and statistics."""

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Literal, Self

from server.schemas import AlgorithmConfig, SinkName, TaskCreate
from server.services.algorithms import (
    ALGORITHM_FACTORIES,
    Algorithm,
    StatisticMap,
)
from server.services.sinks import SINK_FACTORIES, Sink


@dataclass
class BatchOutcome:
    """Results and counters produced from one dispatched batch.

    :attr results: values emitted by the algorithm
    :attr samples_processed: number of consumed input samples
    """

    results: list[float]
    samples_processed: int


class ProcessingTask:
    """Run one algorithm and write its results to one sink.

    :attr task_id: lowercase UUID4 text
    :attr algorithm_config: validated algorithm configuration
    :attr sink_name: selected sink name
    :attr algorithm: algorithm instance
    :attr sink: sink instance
    :attr samples_processed: samples accepted by the algorithm
    :attr created_at: creation time in UTC
    :attr status: running or failed
    :attr error: exception class name after a failure
    """

    def __init__(
        self,
        task_id: str,
        algorithm_config: AlgorithmConfig,
        sink_name: SinkName,
        algorithm: Algorithm,
        sink: Sink,
        created_at: datetime,
    ) -> None:
        self.task_id = task_id
        self.algorithm_config = algorithm_config
        self.sink_name = sink_name
        self.algorithm = algorithm
        self.sink = sink
        self.samples_processed = 0
        self.created_at = created_at
        self.status: Literal["running", "failed"] = "running"
        self.error: str | None = None
        self._sink_closed = False

    @classmethod
    def create(cls, config: TaskCreate) -> Self:
        """Build a running task from a validated request.

        :param config: task configuration
        :return: new running task
        """
        algorithm = ALGORITHM_FACTORIES[config.algorithm.name](config.algorithm)
        sink = SINK_FACTORIES[config.sink]()
        return cls(
            task_id=str(uuid.uuid4()),
            algorithm_config=config.algorithm,
            sink_name=config.sink,
            algorithm=algorithm,
            sink=sink,
            created_at=datetime.now(UTC),
        )

    def process_samples(self, samples: list[float]) -> None:
        """Feed samples to the algorithm and write any results.

        :param samples: finite samples from one dispatch
        :raises Exception: when the algorithm or the sink fails
        """
        outcome = self._process_batch(samples)
        self.samples_processed += outcome.samples_processed
        if outcome.results:
            self.sink.write_results(outcome.results)

    def _process_batch(self, samples: list[float]) -> BatchOutcome:
        """Run the algorithm for one dispatched batch.

        :param samples: finite samples from one dispatch
        :return: emitted results and the number of consumed samples
        """
        results: list[float] = []
        for sample in samples:
            result = self.algorithm.process_sample(sample)
            if result is not None:
                results.append(result)
        return BatchOutcome(results=results, samples_processed=len(samples))

    def read_statistics(self) -> StatisticMap:
        """Return samples processed plus algorithm statistics.

        :return: statistic mapping
        """
        statistics: StatisticMap = {"samples_processed": self.samples_processed}
        for name, value in self.algorithm.read_statistics().items():
            statistics[name] = value
        return statistics

    def record_failure(self, error_name: str) -> None:
        """Mark the task failed and remember the error class name.

        :param error_name: exception class name without a traceback
        """
        self.status = "failed"
        self.error = error_name

    def close_sink(self) -> None:
        """Close the sink once."""
        if self._sink_closed:
            return
        self._sink_closed = True
        self.sink.close()
