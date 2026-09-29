"""Component tests for the processing server entry point."""

import pytest
import uvicorn

from server.main import HTTP_CONCURRENCY_LIMIT, main


def test_main_limits_concurrency_and_hides_server_header(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Verify SRV-9, H1 and H10: uvicorn runs with a connection cap and no server header."""
    calls: list[dict[str, object]] = []

    def run(_app: object, **options: object) -> None:
        calls.append(options)

    monkeypatch.setattr(uvicorn, "run", run)
    monkeypatch.delenv("HTTP_HOST", raising=False)
    monkeypatch.delenv("HTTP_PORT", raising=False)

    main()

    assert calls == [
        {
            "host": "127.0.0.1",
            "port": 8000,
            "limit_concurrency": HTTP_CONCURRENCY_LIMIT,
            "server_header": False,
        }
    ]
    assert HTTP_CONCURRENCY_LIMIT == 64
