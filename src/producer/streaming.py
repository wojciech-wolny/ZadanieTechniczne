"""File repetition, sample limits and paced TCP sending."""

import itertools
import socket
import time
from collections.abc import Callable, Iterator
from pathlib import Path

from common.protocol import pack_samples

BATCH_INTERVAL_SECONDS = 0.02


class EmptyInputError(Exception):
    """Raised when a file pass produces no samples."""


def repeat_samples(
    path: Path,
    read_samples: Callable[[Path], Iterator[float]],
) -> Iterator[float]:
    """Yield samples from a file, reopening it after each full pass.

    :param path: input file path
    :param read_samples: reader for one pass over the file
    :return: samples repeated for as long as each pass yields one
    :raises EmptyInputError: when a pass yields no samples
    """
    while True:
        yielded = False
        for sample in read_samples(path):
            yielded = True
            yield sample
        if not yielded:
            raise EmptyInputError(f"no samples in {path}")


def limit_samples(samples: Iterator[float], limit: int) -> Iterator[float]:
    """Stop the sample stream after a finite limit.

    :param samples: source samples
    :param limit: maximum samples, or 0 for no limit
    :return: limited iterator
    """
    if limit == 0:
        yield from samples
        return
    yield from itertools.islice(samples, limit)


def send_samples(
    connection: socket.socket,
    samples: Iterator[float],
    rate: float,
    *,
    clock: Callable[[], float] = time.monotonic,
    wait: Callable[[float], None] = time.sleep,
) -> None:
    """Send samples in paced batches.

    :param connection: connected TCP socket
    :param samples: sample iterator, possibly unbounded
    :param rate: samples per second
    :param clock: monotonic time source
    :param wait: delay used when the schedule is ahead
    """
    batch_size = max(1, round(rate * BATCH_INTERVAL_SECONDS))
    started = clock()
    sent_count = 0
    batch: list[float] = []
    for sample in samples:
        batch.append(sample)
        if len(batch) < batch_size:
            continue
        _send_when_due(connection, batch, rate, started, sent_count, clock, wait)
        sent_count += len(batch)
        batch = []
    if batch:
        _send_when_due(connection, batch, rate, started, sent_count, clock, wait)


def _send_when_due(
    connection: socket.socket,
    batch: list[float],
    rate: float,
    started: float,
    sent_count: int,
    clock: Callable[[], float],
    wait: Callable[[float], None],
) -> None:
    """Send one batch when its deadline has arrived.

    :param connection: connected TCP socket
    :param batch: samples to send together
    :param rate: samples per second
    :param started: schedule origin
    :param sent_count: samples already sent
    :param clock: monotonic time source
    :param wait: delay used when the schedule is ahead
    """
    if sent_count > 0:
        deadline = started + sent_count / rate
        delay = deadline - clock()
        if delay > 0:
            wait(delay)
    connection.sendall(pack_samples(batch))
