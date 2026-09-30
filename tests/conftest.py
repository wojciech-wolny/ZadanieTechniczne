"""Fixtures shared by integration and system tests."""

from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from server.main import create_app


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch) -> Iterator[TestClient]:
    """Start a processing server on a free TCP port."""
    monkeypatch.setenv("TCP_PORT", "0")
    monkeypatch.delenv("MAX_TASKS", raising=False)
    monkeypatch.delenv("PRODUCER_IDLE_SECONDS", raising=False)
    with TestClient(create_app()) as test_client:
        yield test_client
