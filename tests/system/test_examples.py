"""System tests that stream example files through the producer."""

import io
import socket
import subprocess
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from producer.__main__ import main
from producer.readers import SAMPLE_READERS
from tests.support import bound_port, wait_for_stream

ROOT = Path(__file__).resolve().parents[2]
EXAMPLES = ROOT / "wytyczne"


def count_samples(path: Path, sample_format: str) -> int:
    """Count samples the producer would send in one pass.

    :param path: input file
    :param sample_format: txt or bin
    :return: sample count
    """
    sample_count = 0
    for _sample in SAMPLE_READERS[sample_format](path):
        sample_count += 1
    return sample_count


@pytest.mark.parametrize(
    ("file_name", "sample_format", "algorithm", "expected"),
    [
        (
            "passthrough.txt",
            "txt",
            {"name": "passthrough"},
            "Passthrough - It works! ",
        ),
        (
            "example_text.txt",
            "txt",
            {"name": "passthrough"},
            "Passthrough works: these samples are printed raw, with no filtering.",
        ),
        (
            "example_text.txt",
            "txt",
            {"name": "average", "window_size": 6},
            "Hello! Nice work :)",
        ),
        (
            "example_text.txt",
            "txt",
            {"name": "linear_regression", "window_size": 4},
            "Congratulation! It is correct decoded data for linear regression",
        ),
        (
            "example_binary.f32",
            "bin",
            {"name": "passthrough"},
            "Passthrough works on binary too: raw float32 samples, no filtering.",
        ),
    ],
    ids=[
        "passthrough_text",
        "example_passthrough",
        "example_average",
        "example_regression",
        "example_binary",
    ],
)
def test_example_file_prints_documented_text(
    client: TestClient,
    monkeypatch: pytest.MonkeyPatch,
    file_name: str,
    sample_format: str,
    algorithm: dict,
    expected: str,
) -> None:
    """Verify DLV-2, DLV-3, DLV-5 and DLV-7: example files decode to the documented text."""
    path = EXAMPLES / file_name
    sample_count = count_samples(path, sample_format)
    stream = io.StringIO()
    monkeypatch.setattr(sys, "stdout", stream)
    created = client.post("/api/v1/tasks", json={"algorithm": algorithm, "sink": "stdout"})
    assert created.status_code == 201

    exit_code = main(
        [
            str(path),
            "--format",
            sample_format,
            "--rate",
            "1000000",
            "--limit",
            str(sample_count),
            "--host",
            "127.0.0.1",
            "--port",
            str(bound_port(client)),
        ]
    )
    wait_for_stream(client, sample_count, False)

    assert exit_code == 0
    assert expected in stream.getvalue()


def test_main_unreachable_server_returns_error(tmp_path: Path) -> None:
    """Verify PRD-1: a failed connection exits with a non zero status."""
    path = tmp_path / "samples.txt"
    path.write_text("1 2\n", encoding="utf-8")
    with socket.socket() as probe:
        probe.bind(("127.0.0.1", 0))
        closed_port = probe.getsockname()[1]

    exit_code = main([str(path), "--rate", "10", "--limit", "1", "--port", str(closed_port)])

    assert exit_code == 1


def test_main_empty_file_returns_error(client: TestClient, tmp_path: Path) -> None:
    """Verify PRD-7: a file pass with no samples stops the producer."""
    path = tmp_path / "empty.txt"
    path.write_text(" \n", encoding="utf-8")

    exit_code = main(
        [
            str(path),
            "--rate",
            "10",
            "--limit",
            "1",
            "--port",
            str(bound_port(client)),
        ]
    )

    assert exit_code == 1


def test_main_missing_file_returns_error(client: TestClient, tmp_path: Path) -> None:
    """Verify PRD-3: a missing input file exits with an error."""
    exit_code = main(
        [
            str(tmp_path / "missing.txt"),
            "--rate",
            "10",
            "--port",
            str(bound_port(client)),
        ]
    )

    assert exit_code == 1


def test_demo_script_prints_example_text() -> None:
    """Verify DLV-8: the demo script prints the documented example text."""
    process = subprocess.Popen(
        [sys.executable, str(ROOT / "scripts" / "demo.py")],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        cwd=ROOT,
    )
    try:
        output, _unused = process.communicate(timeout=90)
    except subprocess.TimeoutExpired:
        process.kill()
        output, _unused = process.communicate()
        raise AssertionError(output)

    assert process.returncode == 0
    assert "Passthrough - It works! " in output
    assert "Passthrough works: these samples are printed raw, with no filtering." in output
    assert "Hello! Nice work :)" in output
    assert "Congratulation! It is correct decoded data for linear regression" in output
    assert "Passthrough works on binary too: raw float32 samples, no filtering." in output
