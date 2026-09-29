"""Start the processing server and decode the example files."""

import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

from producer.readers import SAMPLE_READERS

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "wytyczne"
type AlgorithmBody = dict[str, str | int]


def find_two_ports() -> tuple[int, int]:
    """Reserve two different local TCP ports.

    :return: HTTP port and TCP port
    """
    with socket.socket() as http_socket, socket.socket() as tcp_socket:
        http_socket.bind(("127.0.0.1", 0))
        tcp_socket.bind(("127.0.0.1", 0))
        http_port = int(http_socket.getsockname()[1])
        tcp_port = int(tcp_socket.getsockname()[1])
    return http_port, tcp_port


def request_json(url: str, method: str = "GET", payload: dict | None = None) -> dict:
    """Send one JSON request and return an object body.

    :param url: request URL
    :param method: HTTP method
    :param payload: optional JSON body
    :return: parsed JSON object, or an empty object when the body is empty
    """
    data = None
    headers: dict[str, str] = {}
    if payload is not None:
        data = json.dumps(payload).encode()
        headers["Content-Type"] = "application/json"
    request = urllib.request.Request(url, data=data, headers=headers, method=method)
    with urllib.request.urlopen(request, timeout=5) as response:
        body = response.read()
    if not body:
        return {}
    parsed = json.loads(body)
    if not isinstance(parsed, dict):
        raise RuntimeError("expected a JSON object")
    return parsed


def read_stream(base: str) -> tuple[int, bool]:
    """Read how many samples arrived and whether a producer is connected.

    :param base: API prefix including the host
    :return: samples received and the connection flag
    """
    body = request_json(f"{base}/stream")
    samples = body.get("samples_received")
    connected = body.get("producer_connected")
    if not isinstance(samples, int) or not isinstance(connected, bool):
        raise RuntimeError("unexpected stream status")
    return samples, connected


def count_samples(path: Path, sample_format: str) -> int:
    """Count samples in one file pass.

    :param path: input file
    :param sample_format: txt or bin
    :return: number of samples the producer sends
    """
    sample_count = 0
    for _sample in SAMPLE_READERS[sample_format](path):
        sample_count += 1
    return sample_count


def wait_for_samples(base: str, target: int) -> None:
    """Wait until the server has accepted the samples and the producer is gone.

    :param base: API prefix including the host
    :param target: samples received threshold
    :raises RuntimeError: when the samples do not arrive in time
    """
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        samples, connected = read_stream(base)
        if samples >= target and not connected:
            return
        time.sleep(0.02)
    raise RuntimeError("producer output was not fully received")


def delete_task(url: str) -> None:
    """Delete one task.

    :param url: task URL
    """
    request = urllib.request.Request(url, method="DELETE")
    with urllib.request.urlopen(request, timeout=5):
        return


def run_case(
    http_port: int,
    tcp_port: int,
    path: Path,
    sample_format: str,
    algorithm: AlgorithmBody,
    label: str,
) -> None:
    """Create one task, stream one file pass and remove the task.

    :param http_port: server HTTP port
    :param tcp_port: server TCP port
    :param path: input file
    :param sample_format: txt or bin
    :param algorithm: algorithm JSON body
    :param label: heading printed before the decoded text
    """
    base = f"http://127.0.0.1:{http_port}/api/v1"
    received, _connected = read_stream(base)
    created = request_json(
        f"{base}/tasks",
        method="POST",
        payload={"algorithm": algorithm, "sink": "stdout"},
    )
    task_id = created.get("task_id")
    if not isinstance(task_id, str):
        raise RuntimeError("task id missing")
    print(f"\n{label}", flush=True)
    sample_count = count_samples(path, sample_format)
    subprocess.run(
        [
            sys.executable,
            "-m",
            "producer",
            str(path),
            "--format",
            sample_format,
            "--rate",
            "200000",
            "--limit",
            str(sample_count),
            "--port",
            str(tcp_port),
        ],
        check=True,
    )
    wait_for_samples(base, received + sample_count)
    delete_task(f"{base}/tasks/{task_id}")
    print(flush=True)


def wait_for_server(url: str) -> None:
    """Block until the stream endpoint answers.

    :param url: stream status URL
    :raises RuntimeError: when the server does not start
    """
    deadline = time.monotonic() + 15
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=0.5):
                return
        except (urllib.error.URLError, TimeoutError, OSError):
            time.sleep(0.05)
    raise RuntimeError("processing server did not start")


def main() -> int:
    """Run every example configuration.

    :return: process exit code
    """
    http_port, tcp_port = find_two_ports()
    environment = os.environ.copy()
    environment["HTTP_HOST"] = "127.0.0.1"
    environment["HTTP_PORT"] = str(http_port)
    environment["TCP_HOST"] = "127.0.0.1"
    environment["TCP_PORT"] = str(tcp_port)
    environment["PYTHONUNBUFFERED"] = "1"
    process = subprocess.Popen(
        [sys.executable, "-m", "server.main"],
        env=environment,
        cwd=ROOT,
    )
    try:
        wait_for_server(f"http://127.0.0.1:{http_port}/api/v1/stream")
        cases: list[tuple[Path, str, AlgorithmBody, str]] = [
            (
                EXAMPLES / "passthrough.txt",
                "txt",
                {"name": "passthrough"},
                "passthrough.txt / passthrough",
            ),
            (
                EXAMPLES / "example_text.txt",
                "txt",
                {"name": "passthrough"},
                "example_text.txt / passthrough",
            ),
            (
                EXAMPLES / "example_text.txt",
                "txt",
                {"name": "average", "window_size": 6},
                "example_text.txt / average window 6",
            ),
            (
                EXAMPLES / "example_text.txt",
                "txt",
                {"name": "linear_regression", "window_size": 4},
                "example_text.txt / linear regression window 4",
            ),
            (
                EXAMPLES / "example_binary.f32",
                "bin",
                {"name": "passthrough"},
                "example_binary.f32 / passthrough",
            ),
        ]
        for path, sample_format, algorithm, label in cases:
            run_case(http_port, tcp_port, path, sample_format, algorithm, label)
    except (OSError, urllib.error.URLError, subprocess.CalledProcessError, RuntimeError) as error:
        print(error, file=sys.stderr)
        return 1
    finally:
        process.terminate()
        try:
            process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=5)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
