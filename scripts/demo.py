"""Start the processing server and decode the example files."""

import json
import os
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path

from producer.readers import SAMPLE_READERS

ROOT = Path(__file__).resolve().parents[1]
EXAMPLES = ROOT / "wytyczne"
LOCALHOST = "127.0.0.1"
API_PREFIX = "/api/v1"
SERVER_START_SECONDS = 15.0
SAMPLE_WAIT_SECONDS = 30.0
STOP_TIMEOUT_SECONDS = 5.0
PRODUCER_RATE = "200000"
type AlgorithmBody = dict[str, str | int]
type JsonObject = dict[str, object]


@dataclass
class DemoCase:
    """One example file and the task that decodes it.

    :attr path: input file
    :attr sample_format: txt or bin
    :attr algorithm: algorithm JSON body
    :attr label: heading printed before the decoded text
    """

    path: Path
    sample_format: str
    algorithm: AlgorithmBody
    label: str


@dataclass
class RunningServer:
    """Local server started for one demo run.

    :attr http_port: HTTP port
    :attr tcp_port: TCP port
    :attr environment: environment passed to the server and the producer
    :attr process: server process
    """

    http_port: int
    tcp_port: int
    environment: dict[str, str]
    process: subprocess.Popen[bytes]


def demo_cases() -> list[DemoCase]:
    """Return the example files and the tasks that decode them.

    :return: demo cases in display order
    """
    return [
        DemoCase(
            EXAMPLES / "passthrough.txt",
            "txt",
            {"name": "passthrough"},
            "passthrough.txt / passthrough",
        ),
        DemoCase(
            EXAMPLES / "example_text.txt",
            "txt",
            {"name": "passthrough"},
            "example_text.txt / passthrough",
        ),
        DemoCase(
            EXAMPLES / "example_text.txt",
            "txt",
            {"name": "average", "window_size": 6},
            "example_text.txt / average window 6",
        ),
        DemoCase(
            EXAMPLES / "example_text.txt",
            "txt",
            {"name": "linear_regression", "window_size": 4},
            "example_text.txt / linear regression window 4",
        ),
        DemoCase(
            EXAMPLES / "example_binary.f32",
            "bin",
            {"name": "passthrough"},
            "example_binary.f32 / passthrough",
        ),
    ]


def find_two_ports() -> tuple[int, int]:
    """Reserve two different local TCP ports.

    :return: HTTP port and TCP port
    """
    with socket.socket() as http_socket, socket.socket() as tcp_socket:
        http_socket.bind((LOCALHOST, 0))
        tcp_socket.bind((LOCALHOST, 0))
        http_port = int(http_socket.getsockname()[1])
        tcp_port = int(tcp_socket.getsockname()[1])
    return http_port, tcp_port


def server_environment(http_port: int, tcp_port: int) -> dict[str, str]:
    """Build the environment that pins both processes to the reserved ports.

    :param http_port: HTTP port
    :param tcp_port: TCP port
    :return: environment for the server and the producer
    """
    environment = os.environ.copy()
    environment["HTTP_HOST"] = LOCALHOST
    environment["HTTP_PORT"] = str(http_port)
    environment["TCP_HOST"] = LOCALHOST
    environment["TCP_PORT"] = str(tcp_port)
    environment["PYTHONUNBUFFERED"] = "1"
    return environment


def start_server() -> RunningServer:
    """Start the processing server on two free local ports.

    :return: ports, environment, and the server process
    """
    http_port, tcp_port = find_two_ports()
    environment = server_environment(http_port, tcp_port)
    process = subprocess.Popen(
        [sys.executable, "-m", "server.main"],
        env=environment,
        cwd=ROOT,
    )
    return RunningServer(http_port, tcp_port, environment, process)


def stop_server(process: subprocess.Popen[bytes]) -> None:
    """Stop the server process.

    :param process: server process
    """
    process.terminate()
    try:
        process.wait(timeout=STOP_TIMEOUT_SECONDS)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=STOP_TIMEOUT_SECONDS)


def request_json(url: str, method: str = "GET", payload: JsonObject | None = None) -> JsonObject:
    """Send one JSON request and return an object body.

    :param url: request URL
    :param method: HTTP method
    :param payload: optional JSON body
    :return: parsed JSON object, or an empty object when the body is empty
    :raises RuntimeError: when the body is not a JSON object
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


def api_base(http_port: int) -> str:
    """Return the versioned API prefix for one local server.

    :param http_port: HTTP port
    :return: API prefix including the host
    """
    return f"http://{LOCALHOST}:{http_port}{API_PREFIX}"


def read_stream(base: str) -> tuple[int, bool]:
    """Read how many samples arrived and whether a producer is connected.

    :param base: API prefix including the host
    :return: samples received and the connection flag
    :raises RuntimeError: when the status fields have the wrong type
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


def wait_for_server(url: str) -> None:
    """Block until the stream endpoint answers.

    :param url: stream status URL
    :raises RuntimeError: when the server does not start
    """
    deadline = time.monotonic() + SERVER_START_SECONDS
    while time.monotonic() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=0.5):
                return
        except (urllib.error.URLError, TimeoutError, OSError):
            time.sleep(0.05)
    raise RuntimeError("processing server did not start")


def wait_for_samples(base: str, target: int) -> None:
    """Wait until the server has accepted the samples and the producer is gone.

    :param base: API prefix including the host
    :param target: samples received threshold
    :raises RuntimeError: when the samples do not arrive in time
    """
    deadline = time.monotonic() + SAMPLE_WAIT_SECONDS
    while time.monotonic() < deadline:
        samples, connected = read_stream(base)
        if samples >= target and not connected:
            return
        time.sleep(0.02)
    raise RuntimeError("producer output was not fully received")


def send_file(server: RunningServer, case: DemoCase, sample_count: int) -> None:
    """Send one file pass to the demo server.

    :param server: running demo server
    :param case: example file and format
    :param sample_count: samples to send
    """
    subprocess.run(
        [
            sys.executable,
            "-m",
            "producer",
            str(case.path),
            "--format",
            case.sample_format,
            "--rate",
            PRODUCER_RATE,
            "--limit",
            str(sample_count),
            "--host",
            LOCALHOST,
            "--port",
            str(server.tcp_port),
        ],
        check=True,
        cwd=ROOT,
        env=server.environment,
    )


def run_case(server: RunningServer, case: DemoCase) -> None:
    """Create one task, stream one file pass, and remove the task.

    :param server: running demo server
    :param case: example file and task
    :raises RuntimeError: when the created task has no id
    """
    base = api_base(server.http_port)
    received, _connected = read_stream(base)
    created = request_json(
        f"{base}/tasks",
        method="POST",
        payload={"algorithm": case.algorithm, "sink": "stdout"},
    )
    task_id = created.get("task_id")
    if not isinstance(task_id, str):
        raise RuntimeError("task id missing")
    print(f"\n{case.label}", flush=True)
    sample_count = count_samples(case.path, case.sample_format)
    send_file(server, case, sample_count)
    wait_for_samples(base, received + sample_count)
    request_json(f"{base}/tasks/{task_id}", method="DELETE")
    print(flush=True)


def run_cases(server: RunningServer) -> None:
    """Run every example configuration against one server.

    :param server: running demo server
    """
    wait_for_server(f"{api_base(server.http_port)}/stream")
    for case in demo_cases():
        run_case(server, case)


def main() -> int:
    """Run every example configuration.

    :return: process exit code
    """
    server = start_server()
    try:
        run_cases(server)
    except (OSError, urllib.error.URLError, subprocess.CalledProcessError, RuntimeError) as error:
        print(error, file=sys.stderr)
        return 1
    finally:
        stop_server(server.process)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
