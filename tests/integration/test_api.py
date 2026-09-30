"""Integration tests for the task REST API."""

import uuid
from datetime import datetime

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from server.main import create_app
from server.services.sinks import SINK_FACTORIES


def test_create_task_returns_created_task(client: TestClient) -> None:
    """Verify API-1, TSK-1 and TSK-3: creating a task returns configuration and state."""
    response = client.post(
        "/api/v1/tasks",
        json={"algorithm": {"name": "average", "window_size": 6}, "sink": "stdout"},
    )

    body = response.json()
    assert response.status_code == status.HTTP_201_CREATED
    uuid.UUID(body["task_id"])
    assert body["algorithm"] == {"name": "average", "window_size": 6}
    assert body["sink"] == "stdout"
    assert body["status"] == "running"
    assert body["error"] is None
    assert body["statistics"] == {
        "samples_processed": 0,
        "windows_processed": 0,
        "last_result": None,
    }
    created_at = datetime.fromisoformat(body["created_at"])
    assert created_at.tzinfo is not None


def test_create_task_defaults_sink_to_null(client: TestClient) -> None:
    """Verify OUT-2 and TSK-4: a passthrough task defaults to a null sink."""
    response = client.post("/api/v1/tasks", json={"algorithm": {"name": "passthrough"}})

    body = response.json()
    assert response.status_code == status.HTTP_201_CREATED
    assert body["sink"] == "null"
    assert body["statistics"] == {"samples_processed": 0}


def test_list_tasks_returns_creation_order(client: TestClient) -> None:
    """Verify API-2: listing tasks follows creation order."""
    first = client.post(
        "/api/v1/tasks",
        json={"algorithm": {"name": "passthrough"}},
    ).json()["task_id"]
    second = client.post(
        "/api/v1/tasks",
        json={"algorithm": {"name": "linear_regression", "window_size": 2}},
    ).json()["task_id"]

    response = client.get("/api/v1/tasks")

    assert response.status_code == status.HTTP_200_OK
    assert [item["task_id"] for item in response.json()] == [first, second]
    assert response.json()[1]["statistics"]["last_slope"] is None


def test_read_task_returns_the_created_task(client: TestClient) -> None:
    """Verify API-3: reading a task returns its configuration and statistics."""
    created = client.post(
        "/api/v1/tasks",
        json={"algorithm": {"name": "passthrough"}, "sink": "null"},
    ).json()

    response = client.get(f"/api/v1/tasks/{created['task_id']}")

    assert response.status_code == status.HTTP_200_OK
    assert response.json()["task_id"] == created["task_id"]
    assert response.json()["status"] == "running"


def test_read_task_unknown_id_returns_not_found(client: TestClient) -> None:
    """Verify API-3: a missing task returns 404."""
    response = client.get("/api/v1/tasks/missing")

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()["detail"] == "Task not found"


def test_delete_task_removes_it(client: TestClient) -> None:
    """Verify API-4: deleting a task removes it from the collection."""
    task_id = client.post(
        "/api/v1/tasks",
        json={"algorithm": {"name": "passthrough"}},
    ).json()["task_id"]

    deleted = client.delete(f"/api/v1/tasks/{task_id}")
    listing = client.get("/api/v1/tasks")
    missing = client.get(f"/api/v1/tasks/{task_id}")

    assert deleted.status_code == status.HTTP_204_NO_CONTENT
    assert deleted.content == b""
    assert listing.json() == []
    assert missing.status_code == status.HTTP_404_NOT_FOUND


def test_delete_task_unknown_id_returns_not_found(client: TestClient) -> None:
    """Verify API-4: deleting a missing task returns 404."""
    response = client.delete("/api/v1/tasks/missing")

    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert response.json()["detail"] == "Task not found"


@pytest.mark.parametrize(
    "payload",
    [
        {"algorithm": {"name": "average", "window_size": 0}},
        {"algorithm": {"name": "average", "window_size": 100001}},
        {"algorithm": {"name": "linear_regression", "window_size": 1}},
        {"algorithm": {"name": "linear_regression", "window_size": 100001}},
        {"algorithm": {"name": "missing"}},
        {"algorithm": {"name": "passthrough"}, "sink": "file"},
        {"algorithm": {"name": "passthrough"}, "sinks": "stdout"},
        {"algorithm": {"name": "average", "window_size": "6"}},
    ],
    ids=[
        "average_below",
        "average_above",
        "regression_below",
        "regression_above",
        "unknown_algorithm",
        "unknown_sink",
        "unknown_field",
        "window_size_text",
    ],
)
def test_create_task_rejects_invalid_configuration(
    client: TestClient,
    payload: dict,
) -> None:
    """Verify API-5, ALG-4 and H7: invalid algorithms, sinks, sizes and field types return 422."""
    response = client.post("/api/v1/tasks", json=payload)

    assert response.status_code == status.HTTP_422_UNPROCESSABLE_CONTENT


@pytest.mark.parametrize(
    "algorithm",
    [
        {"name": "average", "window_size": 1},
        {"name": "average", "window_size": 100000},
        {"name": "linear_regression", "window_size": 2},
        {"name": "linear_regression", "window_size": 100000},
    ],
    ids=["average_min", "average_max", "regression_min", "regression_max"],
)
def test_create_task_accepts_window_boundaries(client: TestClient, algorithm: dict) -> None:
    """Verify API-5: window sizes on the accepted boundary create a task."""
    response = client.post("/api/v1/tasks", json={"algorithm": algorithm, "sink": "null"})

    assert response.status_code == status.HTTP_201_CREATED


def test_create_task_when_full_returns_conflict(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify API-1: a full registry returns 409."""
    monkeypatch.setenv("TCP_PORT", "0")
    monkeypatch.setenv("MAX_TASKS", "1")
    with TestClient(create_app()) as client:
        first = client.post("/api/v1/tasks", json={"algorithm": {"name": "passthrough"}})
        second = client.post("/api/v1/tasks", json={"algorithm": {"name": "passthrough"}})

    assert first.status_code == status.HTTP_201_CREATED
    assert second.status_code == status.HTTP_409_CONFLICT
    assert second.json()["detail"] == "Task limit reached"


def test_shutdown_closes_the_sink_of_a_running_task(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify API-4: stopping the server closes the sinks of tasks that are still stored."""
    closed: list[bool] = []

    class RecordingSink:
        def write_results(self, results: list[float]) -> None:
            return

        def close(self) -> None:
            closed.append(True)

    monkeypatch.setenv("TCP_PORT", "0")
    monkeypatch.setitem(SINK_FACTORIES, "null", RecordingSink)
    with TestClient(create_app()) as client:
        client.post("/api/v1/tasks", json={"algorithm": {"name": "passthrough"}})

    assert closed == [True]


def test_docs_disabled_hides_docs_and_keeps_the_api(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify API-6 and H10: with docs disabled the docs return 404 and the API still works."""
    monkeypatch.setenv("TCP_PORT", "0")
    monkeypatch.setenv("DOCS_ENABLED", "false")
    with TestClient(create_app()) as client:
        docs = client.get("/docs")
        redoc = client.get("/redoc")
        schema = client.get("/openapi.json")
        tasks = client.get("/api/v1/tasks")

    assert docs.status_code == status.HTTP_404_NOT_FOUND
    assert redoc.status_code == status.HTTP_404_NOT_FOUND
    assert schema.status_code == status.HTTP_404_NOT_FOUND
    assert tasks.status_code == status.HTTP_200_OK


def test_read_stream_starts_idle(client: TestClient) -> None:
    """Verify SRV-2 and SRV-5: the stream starts with no producer and no samples."""
    response = client.get("/api/v1/stream")

    assert response.status_code == status.HTTP_200_OK
    assert response.json() == {"producer_connected": False, "samples_received": 0}
