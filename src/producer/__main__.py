"""Command line entry point for the sample producer."""

import argparse
import math
import socket
import sys
from pathlib import Path

from common.protocol import DEFAULT_TCP_HOST, DEFAULT_TCP_PORT
from producer.readers import SAMPLE_READERS
from producer.streaming import EmptyInputError, limit_samples, repeat_samples, send_samples

MIN_SAMPLE_RATE = 0.1
MAX_SAMPLE_RATE = 1_000_000
CONNECT_TIMEOUT_SECONDS = 5.0
RATE_ERROR = f"rate must be a finite number from {MIN_SAMPLE_RATE} to {MAX_SAMPLE_RATE}"
LIMIT_ERROR = f"limit must be an integer from 0 to {sys.maxsize}"


def parse_rate(value: str) -> float:
    """Parse a finite sample rate from one tenth to one million.

    :param value: command text
    :return: samples per second
    :raises argparse.ArgumentTypeError: when the value is outside the accepted range
    """
    try:
        rate = float(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(RATE_ERROR) from error
    if not math.isfinite(rate) or rate < MIN_SAMPLE_RATE or rate > MAX_SAMPLE_RATE:
        raise argparse.ArgumentTypeError(RATE_ERROR)
    return rate


def parse_limit(value: str) -> int:
    """Parse a sample limit from zero to the largest supported size.

    :param value: command text
    :return: sample limit
    :raises argparse.ArgumentTypeError: when the value is outside the range or not an integer
    """
    try:
        limit = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(LIMIT_ERROR) from error
    if limit < 0 or limit > sys.maxsize:
        raise argparse.ArgumentTypeError(LIMIT_ERROR)
    return limit


def parse_port(value: str) -> int:
    """Parse a TCP port from 0 to 65535.

    :param value: command text
    :return: port number
    :raises argparse.ArgumentTypeError: when the value is outside the port range
    """
    try:
        port = int(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("port must be from 0 to 65535") from error
    if port < 0 or port > 65535:
        raise argparse.ArgumentTypeError("port must be from 0 to 65535")
    return port


def build_parser() -> argparse.ArgumentParser:
    """Build the producer command line parser.

    :return: configured argument parser
    """
    parser = argparse.ArgumentParser(prog="producer")
    parser.add_argument("input_file", help="path to the input file")
    parser.add_argument(
        "--format",
        dest="sample_format",
        choices=("txt", "bin"),
        default="txt",
        help="input format, txt or bin",
    )
    parser.add_argument("--rate", type=parse_rate, required=True, help="samples per second")
    parser.add_argument(
        "--limit",
        type=parse_limit,
        default=0,
        help="samples to send, 0 means unlimited",
    )
    parser.add_argument("--host", default=DEFAULT_TCP_HOST, help="server host")
    parser.add_argument("--port", type=parse_port, default=DEFAULT_TCP_PORT, help="server port")
    return parser


def main(argv: list[str] | None = None) -> int:
    """Send samples from a file to the processing server.

    :param argv: command arguments without the program name
    :return: process exit code
    """
    arguments = build_parser().parse_args(argv)
    reader = SAMPLE_READERS[arguments.sample_format]
    path = Path(arguments.input_file)
    try:
        with socket.create_connection(
            (arguments.host, arguments.port),
            timeout=CONNECT_TIMEOUT_SECONDS,
        ) as connection:
            connection.settimeout(None)
            stream = limit_samples(repeat_samples(path, reader), arguments.limit)
            send_samples(connection, stream, arguments.rate)
    except KeyboardInterrupt:
        return 0
    except (OSError, UnicodeError, EmptyInputError) as error:
        print(f"producer failed: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
