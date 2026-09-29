"""Component tests for the server settings."""

import pytest
from pydantic import ValidationError

from server.settings import MAX_TASKS_LIMIT, Settings


@pytest.mark.parametrize(
    ("name", "value"),
    [("TCP_HOST", ""), ("HTTP_HOST", ""), ("MAX_TASKS", "0"), ("MAX_TASKS", "257")],
    ids=["empty_tcp_host", "empty_http_host", "tasks_below", "tasks_above"],
)
def test_settings_reject_values_outside_bounds(
    monkeypatch: pytest.MonkeyPatch,
    name: str,
    value: str,
) -> None:
    """Verify SRV-9 and H8: empty hosts and task limits outside 1 to 256 are rejected."""
    monkeypatch.setenv(name, value)

    with pytest.raises(ValidationError):
        Settings()


@pytest.mark.parametrize("value", ["1", "256"], ids=["tasks_min", "tasks_max"])
def test_settings_accept_task_limit_boundaries(
    monkeypatch: pytest.MonkeyPatch,
    value: str,
) -> None:
    """Verify SRV-9 and H8: task limits of 1 and 256 are accepted."""
    monkeypatch.setenv("MAX_TASKS", value)

    settings = Settings()

    assert settings.max_tasks == int(value)
    assert MAX_TASKS_LIMIT == 256


@pytest.mark.parametrize(
    "value",
    ["0", "-1", "3600.1", "inf", "nan"],
    ids=["zero", "negative", "above_max", "infinity", "nan"],
)
def test_settings_reject_idle_timeout_outside_range(
    monkeypatch: pytest.MonkeyPatch,
    value: str,
) -> None:
    """Verify SRV-6 and H2: the producer idle timeout is finite, above zero and at most 3600."""
    monkeypatch.setenv("PRODUCER_IDLE_SECONDS", value)

    with pytest.raises(ValidationError):
        Settings()


def test_settings_default_idle_timeout_is_30_seconds(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify SRV-6 and H2: the producer idle timeout defaults to 30 seconds."""
    monkeypatch.delenv("PRODUCER_IDLE_SECONDS", raising=False)

    settings = Settings()

    assert settings.producer_idle_seconds == 30
