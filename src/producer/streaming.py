"""File repetition, sample limits and paced TCP sending."""

import itertools
import socket
import time
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from pathlib import Path

from common.protocol import pack_samples

BATCH_INTERVAL_SECONDS = 0.02
type Clock = Callable[[], float]
type Wait = Callable[[float], None]


class EmptyInputError(Exception):
    """Raised when a file pass produces no samples."""


@dataclass
class SendSchedule:
    """Track batch deadlines while sending samples.

    :attr rate: samples per second
    :attr started: monotonic start time of the first batch
    :attr sent_count: samples already written
    """

    rate: float
    started: float
    sent_count: int = 0


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
    clock: Clock = time.monotonic,
    wait: Wait = time.sleep,
) -> None:
    """Send samples in paced batches.

    :param connection: connected TCP socket
    :param samples: sample iterator, possibly unbounded
    :param rate: samples per second
    :param clock: monotonic time source
    :param wait: delay used when the schedule is ahead
    """
    batch_size = max(1, round(rate * BATCH_INTERVAL_SECONDS))
    schedule = SendSchedule(rate=rate, started=clock())
    batch: list[float] = []
    for sample in samples:
        batch.append(sample)
        if len(batch) < batch_size:
            continue
        _send_when_due(connection, batch, schedule, clock, wait)
        batch = []
    if batch:
        _send_when_due(connection, batch, schedule, clock, wait)


def _send_when_due(
    connection: socket.socket,
    batch: list[float],
    schedule: SendSchedule,
    clock: Clock,
    wait: Wait,
) -> None:
    """Send one batch when its deadline has arrived.

    :param connection: connected TCP socket
    :param batch: samples to send together
    :param schedule: pacing state shared between batches
    :param clock: monotonic time source
    :param wait: delay used when the schedule is ahead
    """
    if schedule.sent_count > 0:
        deadline = schedule.started + schedule.sent_count / schedule.rate
        delay = deadline - clock()
        if delay > 0:
            wait(delay)
    connection.sendall(pack_samples(batch))
    schedule.sent_count += len(batch)
