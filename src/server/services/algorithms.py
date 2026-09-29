"""Streaming algorithms and their factories."""

import math
from collections.abc import Callable
from typing import Protocol, override

from server.schemas import AlgorithmConfig, AverageConfig, LinearRegressionConfig

type StatisticMap = dict[str, float | int | None]


class Algorithm(Protocol):
    """Turn a stream of samples into a stream of results."""

    def process_sample(self, sample: float) -> float | None:
        """Consume one sample and return a result when one is produced.

        :param sample: incoming sample value
        :return: result or None when the algorithm emits nothing
        """
        ...

    def read_statistics(self) -> StatisticMap:
        """Return algorithm specific statistics.

        :return: statistic names mapped to values
        """
        ...


class PassthroughAlgorithm:
    """Emit each input sample unchanged."""

    def process_sample(self, sample: float) -> float | None:
        """Return the sample as the result.

        :param sample: incoming sample value
        :return: the same sample
        """
        return sample

    def read_statistics(self) -> StatisticMap:
        """Return algorithm statistics.

        :return: empty mapping because passthrough has no extra statistics
        """
        return {}


class WindowAlgorithm:
    """Collect non overlapping windows and emit one result per complete window.

    :attr window_size: number of samples in one window
    :attr windows_processed: number of complete windows so far
    """

    def __init__(self, window_size: int) -> None:
        self.window_size = window_size
        self.windows_processed = 0
        self._window: list[float] = []

    def process_sample(self, sample: float) -> float | None:
        """Add a sample and return a result when the window is complete.

        :param sample: incoming sample value
        :return: window result or None while the window is incomplete
        """
        self._window.append(sample)
        if len(self._window) < self.window_size:
            return None
        result = self.calculate_result(self._window)
        self.windows_processed += 1
        self._window.clear()
        return result

    def calculate_result(self, window: list[float]) -> float:
        """Turn one complete window into a numeric result.

        :param window: samples in the completed window
        :return: numeric result
        """
        raise NotImplementedError

    def read_statistics(self) -> StatisticMap:
        """Return statistics shared by windowed algorithms.

        :return: windows processed so far
        """
        return {"windows_processed": self.windows_processed}


class AverageAlgorithm(WindowAlgorithm):
    """Produce the arithmetic mean of every complete window.

    :attr last_result: mean of the latest complete window
    """

    def __init__(self, window_size: int) -> None:
        super().__init__(window_size)
        self.last_result: float | None = None

    @override
    def calculate_result(self, window: list[float]) -> float:
        """Return the mean of the window.

        :param window: samples in the completed window
        :return: arithmetic mean
        """
        self.last_result = sum(window) / len(window)
        return self.last_result

    @override
    def read_statistics(self) -> StatisticMap:
        """Return window count and the latest mean.

        :return: windows processed and last result
        """
        return {
            "windows_processed": self.windows_processed,
            "last_result": self.last_result,
        }


class LinearRegressionAlgorithm(WindowAlgorithm):
    """Produce the least squares slope of every complete window.

    :attr last_slope: slope of the latest complete window
    :attr min_slope: smallest slope produced so far
    :attr max_slope: largest slope produced so far
    """

    def __init__(self, window_size: int) -> None:
        super().__init__(window_size)
        self.last_slope: float | None = None
        self.min_slope: float | None = None
        self.max_slope: float | None = None

    @override
    def calculate_result(self, window: list[float]) -> float:
        """Return the least squares slope of the window.

        :param window: samples in the completed window
        :return: fitted slope
        """
        slope = calculate_slope(window)
        self.last_slope = slope
        if not math.isfinite(slope):
            return slope
        if self.min_slope is None or slope < self.min_slope:
            self.min_slope = slope
        if self.max_slope is None or slope > self.max_slope:
            self.max_slope = slope
        return slope

    @override
    def read_statistics(self) -> StatisticMap:
        """Return window count and slope statistics.

        :return: windows processed and slope values
        """
        return {
            "windows_processed": self.windows_processed,
            "last_slope": self.last_slope,
            "min_slope": self.min_slope,
            "max_slope": self.max_slope,
        }


def calculate_slope(window: list[float]) -> float:
    """Calculate the least squares slope of samples placed at positions 0..N.

    :param window: sample values used as y coordinates
    :return: slope of the fitted line
    :raises ValueError: when the window has fewer than two samples
    """
    sample_count = len(window)
    if sample_count < 2:
        raise ValueError("window needs at least two samples")

    mean_x = (sample_count - 1) / 2
    mean_y = sum(window) / sample_count
    numerator = 0.0
    denominator = 0.0
    for position, value in enumerate(window):
        numerator += (position - mean_x) * (value - mean_y)
        denominator += (position - mean_x) ** 2
    return numerator / denominator


def build_passthrough(_config: AlgorithmConfig) -> Algorithm:
    """Create a passthrough algorithm.

    :param _config: passthrough configuration
    :return: algorithm instance
    """
    return PassthroughAlgorithm()


def build_average(config: AlgorithmConfig) -> Algorithm:
    """Create an average algorithm.

    :param config: average configuration
    :return: algorithm instance
    :raises TypeError: when the configuration is not an average
    """
    match config:
        case AverageConfig(window_size=window_size):
            return AverageAlgorithm(window_size)
    raise TypeError("average configuration required")


def build_linear_regression(config: AlgorithmConfig) -> Algorithm:
    """Create a linear regression algorithm.

    :param config: linear regression configuration
    :return: algorithm instance
    :raises TypeError: when the configuration is not a linear regression
    """
    match config:
        case LinearRegressionConfig(window_size=window_size):
            return LinearRegressionAlgorithm(window_size)
    raise TypeError("linear regression configuration required")


ALGORITHM_FACTORIES: dict[str, Callable[[AlgorithmConfig], Algorithm]] = {
    "passthrough": build_passthrough,
    "average": build_average,
    "linear_regression": build_linear_regression,
}
