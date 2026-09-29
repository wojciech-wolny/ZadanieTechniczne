"""Integration tests for the TCP receiver and active tasks."""

import math
import socket
import struct

import pytest
from fastapi.testclient import TestClient

from common.protocol import SAMPLE_FORMAT, pack_samples
from server.main import create_app
from server.services import receiver as receiver_module
from tests.support import (
    bound_port,
    connect_rejected_producer,
    send_payload,
    send_payload_in_chunks,
    send_samples,
    wait_for_stream,
    wait_until,
)


def test_second_producer_is_rejected_and_the_first_still_counts(client: TestClient) -> None:
    """Verify SRV-1 and SRV-2: only one producer is accepted and its samples count."""
    port = bound_port(client)
    first = socket.create_connection(("127.0.0.1", port), timeout=5)
    try:
        wait_for_stream(client, 0, True)
        second = socket.create_connection(("127.0.0.1", port), timeout=5)
        second.settimeout(2)
        try:
            data = second.recv(8)
        except (ConnectionResetError, ConnectionAbortedError):
            data = b""
        second.close()
        assert data == b""
        first.sendall(struct.pack(SAMPLE_FORMAT, 4.0))
    finally:
        first.close()

    body = wait_for_stream(client, 1, False)
    assert body["samples_received"] == 1


class ManualMonotonic:
    """Stand in for the time module with a clock moved by the test.

    :attr now: current fake monotonic time
    """

    def __init__(self) -> None:
        self.now = 0.0

    def monotonic(self) -> float:
        """Return the current fake time.

        :return: monotonic time
        """
        return self.now


def read_rejection_messages(caplog: pytest.LogCaptureFixture) -> list[str]:
    """Return the logged second producer rejection messages.

    :param caplog: captured log records
    :return: rejection messages in order
    """
    messages: list[str] = []
    for record in caplog.records:
        message = record.getMessage()
        if "second producer" in message:
            messages.append(message)
    return messages


def test_rejected_producers_are_logged_once_per_interval(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """Verify SRV-1 and H9: rejections log the first one, then one count per 10 seconds."""
    clock = ManualMonotonic()
    monkeypatch.setattr(receiver_module, "time", clock)
    port = bound_port(client)
    first = socket.create_connection(("127.0.0.1", port), timeout=5)
    try:
        wait_for_stream(client, 0, True)
        connect_rejected_producer(port)
        connect_rejected_producer(port)
        connect_rejected_producer(port)
        after_burst = read_rejection_messages(caplog)
        clock.now = 9.9
        connect_rejected_producer(port)
        before_interval = read_rejection_messages(caplog)
        clock.now = 10.0
        connect_rejected_producer(port)
        at_interval = read_rejection_messages(caplog)
    finally:
        first.close()

    assert after_burst == ["rejected 1 second producer connections"]
    assert before_interval == after_burst
    assert at_interval == after_burst + ["rejected 4 second producer connections"]


def test_idle_producer_is_closed_and_a_new_one_is_accepted(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify SRV-6 and H2: a silent producer is closed after the idle timeout."""
    monkeypatch.setenv("TCP_PORT", "0")
    monkeypatch.setenv("PRODUCER_IDLE_SECONDS", "0.2")
    with TestClient(create_app()) as client:
        port = bound_port(client)
        idle = socket.create_connection(("127.0.0.1", port), timeout=5)
        try:
            wait_for_stream(client, 0, True)
            data = idle.recv(8)
        finally:
            idle.close()
        closed = wait_for_stream(client, 0, False)
        send_samples(port, [7.0])
        accepted = wait_for_stream(client, 1, False)

    assert data == b""
    assert closed["producer_connected"] is False
    assert accepted["samples_received"] == 1


def test_reconnect_completes_a_partial_window(client: TestClient) -> None:
    """Verify SRV-6: a later producer can finish a window started earlier."""
    created = client.post(
        "/api/v1/tasks",
        json={"algorithm": {"name": "average", "window_size": 3}, "sink": "null"},
    )
    task_id = created.json()["task_id"]
    port = bound_port(client)

    send_payload(port, pack_samples([1.0, 2.0]) + b"\x01\x02")
    wait_for_stream(client, 2, False)
    send_samples(port, [3.0])
    stream = wait_for_stream(client, 3, False)
    body = client.get(f"/api/v1/tasks/{task_id}").json()

    assert stream["samples_received"] == 3
    assert body["statistics"]["samples_processed"] == 3
    assert body["statistics"]["windows_processed"] == 1
    assert body["statistics"]["last_result"] == 2


def test_non_finite_sample_closes_the_connection(client: TestClient) -> None:
    """Verify SRV-6 and H13: a non finite sample closes the producer after its finite prefix."""
    port = bound_port(client)
    connection = socket.create_connection(("127.0.0.1", port), timeout=5)
    try:
        wait_for_stream(client, 0, True)
        connection.sendall(pack_samples([1.0, math.nan]))
        rejected = wait_until(client, lambda body: body.get("producer_connected") is False)
    finally:
        connection.close()
    assert rejected["samples_received"] == 1

    send_samples(port, [5.0])
    accepted = wait_for_stream(client, 2, False)

    assert accepted["samples_received"] == 2


@pytest.mark.parametrize("chunk_size", [24, 8, 1], ids=["one_chunk", "per_sample", "per_byte"])
def test_finite_prefix_does_not_depend_on_read_size(client: TestClient, chunk_size: int) -> None:
    """Verify STR-1 and H13: samples before a non finite one count the same for any read size."""
    task_id = client.post(
        "/api/v1/tasks",
        json={"algorithm": {"name": "passthrough"}, "sink": "null"},
    ).json()["task_id"]
    payload = pack_samples([1.0, 2.0, math.nan])

    send_payload_in_chunks(bound_port(client), payload, chunk_size)
    stream = wait_for_stream(client, 2, False)
    body = client.get(f"/api/v1/tasks/{task_id}").json()

    assert stream["samples_received"] == 2
    assert body["statistics"]["samples_processed"] == 2


def test_task_created_before_samples_processes_all(client: TestClient) -> None:
    """Verify SRV-7: a task created before the first sample sees the whole batch."""
    task_id = client.post(
        "/api/v1/tasks",
        json={"algorithm": {"name": "passthrough"}, "sink": "null"},
    ).json()["task_id"]

    send_samples(bound_port(client), [1.0, 2.0, 3.0, 4.0])
    wait_for_stream(client, 4, False)
    body = client.get(f"/api/v1/tasks/{task_id}").json()

    assert body["statistics"]["samples_processed"] == 4


def test_task_created_after_samples_sees_only_new_ones(client: TestClient) -> None:
    """Verify SRV-8: a task created after samples arrive skips those samples."""
    port = bound_port(client)
    send_samples(port, [1.0, 2.0, 3.0])
    wait_for_stream(client, 3, False)
    task_id = client.post(
        "/api/v1/tasks",
        json={"algorithm": {"name": "passthrough"}, "sink": "null"},
    ).json()["task_id"]

    send_samples(port, [4.0, 5.0])
    wait_for_stream(client, 5, False)
    body = client.get(f"/api/v1/tasks/{task_id}").json()

    assert body["statistics"]["samples_processed"] == 2


def test_two_tasks_share_one_stream(client: TestClient) -> None:
    """Verify SRV-4: active tasks process the same received samples."""
    passthrough_id = client.post(
        "/api/v1/tasks",
        json={"algorithm": {"name": "passthrough"}, "sink": "null"},
    ).json()["task_id"]
    average_id = client.post(
        "/api/v1/tasks",
        json={"algorithm": {"name": "average", "window_size": 2}, "sink": "null"},
    ).json()["task_id"]

    send_samples(bound_port(client), [1.0, 3.0])
    wait_for_stream(client, 2, False)

    passthrough = client.get(f"/api/v1/tasks/{passthrough_id}").json()
    average = client.get(f"/api/v1/tasks/{average_id}").json()
    assert passthrough["statistics"]["samples_processed"] == 2
    assert average["statistics"]["samples_processed"] == 2
    assert average["statistics"]["last_result"] == 2


def test_window_survives_byte_sized_reads(client: TestClient) -> None:
    """Verify STR-2: a window is complete when its bytes arrive one by one."""
    task_id = client.post(
        "/api/v1/tasks",
        json={"algorithm": {"name": "average", "window_size": 100}, "sink": "null"},
    ).json()["task_id"]
    samples = [float(index) for index in range(100)]
    payload = pack_samples(samples)

    send_payload_in_chunks(bound_port(client), payload, 1)
    wait_for_stream(client, 100, False)
    body = client.get(f"/api/v1/tasks/{task_id}").json()

    assert body["statistics"]["windows_processed"] == 1
    assert body["statistics"]["last_result"] == 49.5
    assert body["statistics"]["samples_processed"] == 100
