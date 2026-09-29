"""Helpers shared by integration and system tests."""

import socket
import time
from collections.abc import Callable

from fastapi.testclient import TestClient

from common.protocol import pack_samples


def bound_port(client: TestClient) -> int:
    """Return the TCP port the receiver bound.

    :param client: running application client
    :return: bound port
    """
    return int(client.app.state.sample_receiver.port)


def send_payload(port: int, payload: bytes) -> None:
    """Send one byte string and close the connection.

    :param port: receiver port
    :param payload: wire bytes
    """
    with socket.create_connection(("127.0.0.1", port), timeout=5) as connection:
        connection.sendall(payload)


def send_samples(port: int, samples: list[float]) -> None:
    """Send finite samples as one little endian float64 payload.

    :param port: receiver port
    :param samples: sample values
    """
    send_payload(port, pack_samples(samples))


def send_payload_in_chunks(port: int, payload: bytes, chunk_size: int) -> None:
    """Send a payload in fixed size pieces on one connection.

    :param port: receiver port
    :param payload: wire bytes
    :param chunk_size: maximum bytes per send
    """
    with socket.create_connection(("127.0.0.1", port), timeout=5) as connection:
        index = 0
        while index < len(payload):
            connection.sendall(payload[index : index + chunk_size])
            index += chunk_size


def connect_rejected_producer(port: int) -> bytes:
    """Connect while another producer holds the slot and read until the server closes.

    :param port: receiver port
    :return: bytes received before the close, expected to be empty
    """
    with socket.create_connection(("127.0.0.1", port), timeout=5) as connection:
        try:
            return connection.recv(8)
        except (ConnectionResetError, ConnectionAbortedError):
            return b""


def wait_until(client: TestClient, ready: Callable[[dict], bool]) -> dict:
    """Poll stream status until the predicate matches.

    :param client: running application client
    :param ready: check against the latest status body
    :return: matching status body
    :raises AssertionError: when the status does not match in time
    """
    deadline = time.monotonic() + 5
    last: dict = {}
    while time.monotonic() < deadline:
        body = client.get("/api/v1/stream").json()
        if isinstance(body, dict):
            last = body
            if ready(body):
                return body
        time.sleep(0.01)
    raise AssertionError(last)


def wait_for_stream(
    client: TestClient,
    samples_received: int,
    producer_connected: bool,
) -> dict:
    """Poll until enough samples have arrived and the connection flag matches.

    :param client: running application client
    :param samples_received: minimum accepted samples
    :param producer_connected: expected connection flag
    :return: matching status body
    """

    def ready(body: dict) -> bool:
        received = body.get("samples_received")
        connected = body.get("producer_connected")
        return (
            isinstance(received, int)
            and received >= samples_received
            and connected is producer_connected
        )

    return wait_until(client, ready)
