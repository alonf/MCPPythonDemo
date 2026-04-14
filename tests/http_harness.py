from __future__ import annotations

import contextlib
import http.client
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client

from mcp_linux_diag_server.http_config import API_KEY_HEADER, DEFAULT_MCP_PATH, DEMO_API_KEY, SESSION_ID_HEADER, build_mcp_url

REPO_ROOT = Path(__file__).resolve().parents[1]


def find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def build_env() -> dict[str, str]:
    env = dict(os.environ)
    src_path = str(REPO_ROOT / "src")
    env["PYTHONPATH"] = f"{src_path}:{env['PYTHONPATH']}" if env.get("PYTHONPATH") else src_path
    return env


def wait_for_server(host: str, port: int, process: subprocess.Popen[str], *, timeout_seconds: float = 10.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error: OSError | None = None
    while time.monotonic() < deadline:
        if process.poll() is not None:
            output = process.stdout.read() if process.stdout else ""
            raise RuntimeError(f"Server exited early with code {process.returncode}.\n{output}".strip())
        try:
            with socket.create_connection((host, port), timeout=0.2):
                return
        except OSError as exc:
            last_error = exc
            time.sleep(0.1)
    raise RuntimeError(f"Timed out waiting for server on {host}:{port}: {last_error}")


@contextlib.contextmanager
def running_server(*, host: str = "127.0.0.1", port: int | None = None):  # noqa: ANN201
    selected_port = find_free_port() if port is None else port
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "mcp_linux_diag_server",
            "--host",
            host,
            "--port",
            str(selected_port),
        ],
        cwd=REPO_ROOT,
        env=build_env(),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    try:
        wait_for_server(host, selected_port, process)
        yield host, selected_port, process
    finally:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)
        if process.stdout:
            process.stdout.close()


@contextlib.asynccontextmanager
async def open_session(*, host: str, port: int, sampling_callback=None, elicitation_callback=None):  # noqa: ANN201, ANN001
    async with httpx.AsyncClient(headers={API_KEY_HEADER: DEMO_API_KEY}) as http_client:
        async with streamable_http_client(build_mcp_url(host=host, port=port), http_client=http_client) as (read, write, get_session_id):
            async with ClientSession(
                read,
                write,
                sampling_callback=sampling_callback,
                elicitation_callback=elicitation_callback,
            ) as session:
                initialize_result = await session.initialize()
                session_id = get_session_id()
                if not session_id:
                    raise RuntimeError("Expected streamable HTTP initialization to return an mcp-session-id header")
                yield session, initialize_result, session_id


def parse_response(content_type: str, body: str) -> dict[str, Any] | None:
    if not body.strip():
        return None
    if content_type.startswith("text/plain"):
        return {"text": body}
    if content_type.startswith("application/json"):
        return json.loads(body)
    if content_type.startswith("text/event-stream"):
        data_lines = [line[5:].lstrip() for line in body.splitlines() if line.startswith("data:")]
        if not data_lines:
            raise RuntimeError(f"Expected SSE data payload, got: {body!r}")
        return json.loads("\n".join(data_lines))
    raise RuntimeError(f"Unexpected content type: {content_type}")


def post_jsonrpc(*, host: str, port: int, payload: dict[str, Any], session_id: str | None = None, api_key: str | None = DEMO_API_KEY) -> tuple[int, dict[str, str], dict[str, Any] | None]:
    connection = http.client.HTTPConnection(host, port, timeout=30)
    headers = {
        "Accept": "application/json, text/event-stream",
        "Content-Type": "application/json",
    }
    if api_key is not None:
        headers[API_KEY_HEADER] = api_key
    if session_id is not None:
        headers[SESSION_ID_HEADER] = session_id

    connection.request("POST", DEFAULT_MCP_PATH, body=json.dumps(payload), headers=headers)
    response = connection.getresponse()
    body = response.read().decode("utf-8")
    response_headers = {key.lower(): value for key, value in response.getheaders()}
    connection.close()
    return response.status, response_headers, parse_response(response_headers.get("content-type", "").lower(), body)
