"""Component tests for the streaming algorithms."""

import math

import pytest

from server.services.algorithms import (
    Algorithm,
    AverageAlgorithm,
    LinearRegressionAlgorithm,
    PassthroughAlgorithm,
)


def collect_results(algorithm: Algorithm, samples: list[float]) -> list[float]:
    """Return every result the algorithm emits for the samples.

    :param algorithm: algorithm under test
    :param samples: input samples
    :return: emitted results
    """
    results: list[float] = []
    for sample in samples:
        result = algorithm.process_sample(sample)
        if result is not None:
            results.append(result)
    return results


def test_process_sample_passthrough_returns_each_sample() -> None:
    """Verify ALG-1: each input sample is emitted unchanged."""
    algorithm = PassthroughAlgorithm()

    assert collect_results(algorithm, [1, 2, 3, 4]) == [1, 2, 3, 4]


def test_process_sample_average_matches_the_example() -> None:
    """Verify ALG-2: non overlapping windows emit their mean."""
    algorithm = AverageAlgorithm(window_size=3)

    assert collect_results(algorithm, [1, 2, 3, 4, 5, 6, 7]) == [2, 5]


def test_process_sample_average_window_of_one_emits_the_sample() -> None:
    """Verify ALG-2: a window of one sample emits that sample."""
    algorithm = AverageAlgorithm(window_size=1)

    assert algorithm.process_sample(4.0) == 4.0


def test_read_statistics_average_before_a_window_has_no_result() -> None:
    """Verify ALG-3: last result stays empty until a window completes."""
    algorithm = AverageAlgorithm(window_size=3)

    statistics = algorithm.read_statistics()

    assert statistics["windows_processed"] == 0
    assert statistics["last_result"] is None


def test_read_statistics_average_reports_last_result() -> None:
    """Verify ALG-3: the average exposes windows and the latest result."""
    algorithm = AverageAlgorithm(window_size=3)
    collect_results(algorithm, [1, 2, 3, 4, 5, 6, 7])

    statistics = algorithm.read_statistics()

    assert statistics["windows_processed"] == 2
    assert statistics["last_result"] == 5


def test_process_sample_linear_regression_matches_the_example() -> None:
    """Verify ALG-4: each window emits the least squares slope."""
    algorithm = LinearRegressionAlgorithm(window_size=4)

    assert collect_results(algorithm, [1, 3, 5, 7, 10, 9, 8, 7]) == [2, -1]


def test_process_sample_constant_window_has_zero_slope() -> None:
    """Verify ALG-4: a flat window has slope zero."""
    algorithm = LinearRegressionAlgorithm(window_size=4)

    assert collect_results(algorithm, [5, 5, 5, 5]) == [0]


def test_process_sample_regression_window_of_two_emits_the_slope() -> None:
    """Verify ALG-4: the smallest window emits the slope of two points."""
    algorithm = LinearRegressionAlgorithm(window_size=2)

    assert collect_results(algorithm, [0, 1]) == [1]


def test_read_statistics_regression_before_a_window_has_no_slope() -> None:
    """Verify ALG-5: slope statistics stay empty until a window completes."""
    algorithm = LinearRegressionAlgorithm(window_size=4)
    algorithm.process_sample(1)

    statistics = algorithm.read_statistics()

    assert statistics["windows_processed"] == 0
    assert statistics["last_slope"] is None
    assert statistics["min_slope"] is None
    assert statistics["max_slope"] is None


def test_read_statistics_linear_regression_tracks_slopes() -> None:
    """Verify ALG-5: slope statistics follow the completed windows."""
    algorithm = LinearRegressionAlgorithm(window_size=4)
    collect_results(algorithm, [1, 3, 5, 7, 10, 9, 8, 7])

    statistics = algorithm.read_statistics()

    assert statistics["windows_processed"] == 2
    assert statistics["last_slope"] == -1
    assert statistics["min_slope"] == -1
    assert statistics["max_slope"] == 2


@pytest.mark.parametrize(
    ("sample_count", "expected"),
    [(2, []), (3, [2.0]), (4, [2.0])],
    ids=["below_window", "exact_window", "above_window"],
)
def test_process_sample_average_window_boundaries(
    sample_count: int,
    expected: list[float],
) -> None:
    """Verify ALG-6 and STR-3: only a complete window produces a result."""
    algorithm = AverageAlgorithm(window_size=3)
    samples = [float(value) for value in [1, 2, 3, 4][:sample_count]]

    assert collect_results(algorithm, samples) == expected


def test_read_statistics_regression_nan_slope_does_not_freeze_extremes() -> None:
    """Verify ALG-5 and H6: finite slopes after a NaN window still set min and max."""
    algorithm = LinearRegressionAlgorithm(window_size=2)
    collect_results(algorithm, [1e308, 1e308, 0, 5, 5, 0])

    statistics = algorithm.read_statistics()

    assert statistics["windows_processed"] == 3
    assert statistics["min_slope"] == -5
    assert statistics["max_slope"] == 5
    assert statistics["last_slope"] == -5


def test_read_statistics_regression_nan_slope_is_kept_as_last_slope() -> None:
    """Verify ALG-5 and H6: a NaN slope is reported as last slope but not as min or max."""
    algorithm = LinearRegressionAlgorithm(window_size=2)
    collect_results(algorithm, [1e308, 1e308])

    statistics = algorithm.read_statistics()

    assert math.isnan(statistics["last_slope"])
    assert statistics["min_slope"] is None
    assert statistics["max_slope"] is None


def test_process_sample_regression_incomplete_window_emits_nothing() -> None:
    """Verify ALG-6: an unfinished regression window produces no slope."""
    algorithm = LinearRegressionAlgorithm(window_size=4)

    assert collect_results(algorithm, [1, 3, 5]) == []
    assert algorithm.read_statistics()["windows_processed"] == 0
