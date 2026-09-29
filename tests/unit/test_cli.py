"""Component tests for the producer command line."""

import argparse
import socket
import sys
from pathlib import Path

import pytest

from common.protocol import pack_samples
from producer.__main__ import (
    CONNECT_TIMEOUT_SECONDS,
    build_parser,
    main,
    parse_limit,
    parse_port,
    parse_rate,
)


def test_parse_args_accepts_the_producer_parameters() -> None:
    """Verify PRD-3, PRD-4, PRD-5 and PRD-6: the CLI accepts file, format, rate and limit."""
    arguments = build_parser().parse_args(
        [
            "data.bin",
            "--format",
            "bin",
            "--rate",
            "2.5",
            "--limit",
            "10",
            "--host",
            "localhost",
            "--port",
            "9001",
        ]
    )

    assert arguments.input_file == "data.bin"
    assert arguments.sample_format == "bin"
    assert arguments.rate == 2.5
    assert arguments.limit == 10
    assert arguments.host == "localhost"
    assert arguments.port == 9001


def test_parse_args_uses_documented_defaults() -> None:
    """Verify PRD-4 and PRD-6: text format and an unlimited stream are the defaults."""
    arguments = build_parser().parse_args(["samples.txt", "--rate", "10"])

    assert arguments.sample_format == "txt"
    assert arguments.limit == 0
    assert arguments.host == "127.0.0.1"
    assert arguments.port == 9000


def test_parse_args_requires_a_rate() -> None:
    """Verify PRD-5: the sample rate is required."""
    with pytest.raises(SystemExit):
        build_parser().parse_args(["samples.txt"])


@pytest.mark.parametrize(
    "value",
    ["0", "-1", "inf", "nan", "1000000.1", "abc"],
    ids=["zero", "negative", "infinity", "nan", "above_max", "text"],
)
def test_parse_rate_rejects_values_outside_the_range(value: str) -> None:
    """Verify PRD-5: the rate must be finite, positive and at most one million."""
    with pytest.raises(argparse.ArgumentTypeError):
        parse_rate(value)


@pytest.mark.parametrize(
    ("value", "expected"),
    [("0.1", 0.1), ("1000000", 1_000_000), ("1e6", 1_000_000)],
    ids=["small", "maximum", "scientific"],
)
def test_parse_rate_accepts_boundary_values(value: str, expected: float) -> None:
    """Verify PRD-5: rates from one tenth through one million are accepted."""
    assert parse_rate(value) == expected


@pytest.mark.parametrize("value", ["-1", "1.5", "abc"], ids=["negative", "fraction", "text"])
def test_parse_limit_rejects_invalid_values(value: str) -> None:
    """Verify PRD-6: the limit must be an integer of zero or more."""
    with pytest.raises(argparse.ArgumentTypeError):
        parse_limit(value)


def test_parse_limit_accepts_zero() -> None:
    """Verify PRD-6: zero is the unlimited limit."""
    assert parse_limit("0") == 0


class RecordingConnection:
    """Record the socket calls made by the producer."""

    def __init__(self) -> None:
        self.timeouts: list[float | None] = []
        self.payloads: list[bytes] = []

    def __enter__(self) -> "RecordingConnection":
        """Enter the connection context.

        :return: this connection
        """
        return self

    def __exit__(self, *_details: object) -> None:
        """Leave the connection context without closing anything.

        :param _details: exception details, unused
        """

    def settimeout(self, timeout: float | None) -> None:
        """Store one timeout change.

        :param timeout: new socket timeout
        """
        self.timeouts.append(timeout)

    def sendall(self, payload: bytes) -> None:
        """Store one outgoing payload.

        :param payload: bytes the producer would write
        """
        self.payloads.append(payload)


def test_main_connects_with_timeout_then_sends_blocking(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Verify PRD-1 and H5: the connect has a timeout and sending is blocking again."""
    path = tmp_path / "samples.txt"
    path.write_text("1 2", encoding="utf-8")
    connection = RecordingConnection()
    connect_timeouts: list[float] = []

    def create_connection(_address: tuple[str, int], timeout: float) -> RecordingConnection:
        connect_timeouts.append(timeout)
        return connection

    monkeypatch.setattr(socket, "create_connection", create_connection)

    exit_code = main([str(path), "--rate", "1000000", "--limit", "2"])

    assert exit_code == 0
    assert connect_timeouts == [CONNECT_TIMEOUT_SECONDS]
    assert CONNECT_TIMEOUT_SECONDS == 5
    assert connection.timeouts == [None]
    assert connection.payloads == [pack_samples([1.0, 2.0])]


def test_parse_rate_rejects_value_below_minimum() -> None:
    """Verify PRD-5 and H3: a rate just below one tenth is rejected."""
    with pytest.raises(argparse.ArgumentTypeError):
        parse_rate("0.09")


def test_parse_rate_rejects_tiny_positive_value() -> None:
    """Verify PRD-5 and H3: a rate that would overflow the sleep is rejected."""
    with pytest.raises(argparse.ArgumentTypeError):
        parse_rate("1e-300")


def test_parse_limit_accepts_largest_size() -> None:
    """Verify PRD-6 and H4: the largest supported limit is accepted."""
    assert parse_limit(str(sys.maxsize)) == sys.maxsize


def test_parse_limit_rejects_value_above_largest_size() -> None:
    """Verify PRD-6 and H4: a limit above the largest supported size is rejected."""
    with pytest.raises(argparse.ArgumentTypeError):
        parse_limit(str(sys.maxsize + 1))


@pytest.mark.parametrize("value", ["-1", "65536", "abc"], ids=["below", "above", "text"])
def test_parse_port_rejects_values_outside_the_range(value: str) -> None:
    """Verify PRD-10: the port must be from 0 through 65535."""
    with pytest.raises(argparse.ArgumentTypeError):
        parse_port(value)


@pytest.mark.parametrize(("value", "expected"), [("0", 0), ("65535", 65535)], ids=["low", "high"])
def test_parse_port_accepts_boundary_values(value: str, expected: int) -> None:
    """Verify PRD-10: the lowest and highest TCP ports are accepted."""
    assert parse_port(value) == expected
