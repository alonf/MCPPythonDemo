from __future__ import annotations

import asyncio
import http.client
import json
import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
SRC_ROOT = REPO_ROOT / "src"
if str(SRC_ROOT) not in sys.path:
    sys.path.insert(0, str(SRC_ROOT))

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
from mcp.shared.version import LATEST_PROTOCOL_VERSION

from mcp_linux_diag_server.http_config import API_KEY_HEADER, DEFAULT_HTTP_HOST, DEFAULT_MCP_PATH, DEMO_API_KEY, SESSION_ID_HEADER, build_mcp_url


def _build_env() -> dict[str, str]:
    env = dict(os.environ)
    src_path = str(REPO_ROOT / "src")
    env["PYTHONPATH"] = f"{src_path}:{env['PYTHONPATH']}" if env.get("PYTHONPATH") else src_path
    return env


def _wait_for_server(host: str, port: int, process: subprocess.Popen[str], *, timeout_seconds: float = 10.0) -> None:
    deadline = time.monotonic() + timeout_seconds
    last_error: OSError | None = None
    while time.monotonic() < deadline:
        if process.poll() is not None:
            output = process.stdout.read() if process.stdout else ""
            raise RuntimeError(f"Local MCP server exited early with code {process.returncode}.\n{output}".strip())
        try:
            with socket.create_connection((host, port), timeout=0.2):
                return
        except OSError as exc:
            last_error = exc
            time.sleep(0.1)
    raise RuntimeError(f"Timed out waiting for local MCP HTTP server on {host}:{port}: {last_error}")


def _find_free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind((DEFAULT_HTTP_HOST, 0))
        return int(sock.getsockname()[1])


def _start_server(port: int) -> subprocess.Popen[str]:
    process = subprocess.Popen(
        [
            sys.executable,
            "-m",
            "mcp_linux_diag_server",
            "--host",
            DEFAULT_HTTP_HOST,
            "--port",
            str(port),
        ],
        cwd=REPO_ROOT,
        env=_build_env(),
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )
    _wait_for_server(DEFAULT_HTTP_HOST, port, process)
    return process


def _stop_server(process: subprocess.Popen[str]) -> None:
    if process.poll() is not None:
        if process.stdout:
            process.stdout.close()
        return
    process.terminate()
    try:
        process.wait(timeout=5)
    except subprocess.TimeoutExpired:
        process.kill()
        process.wait(timeout=5)
    if process.stdout:
        process.stdout.close()


def _parse_response_body(content_type: str, body: str) -> dict[str, Any] | None:
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
    raise RuntimeError(f"Unexpected response content type: {content_type}")


def _post_jsonrpc(
    payload: dict[str, Any],
    *,
    port: int,
    session_id: str | None = None,
    api_key: str | None = DEMO_API_KEY,
) -> tuple[int, dict[str, str], dict[str, Any] | None]:
    connection = http.client.HTTPConnection(DEFAULT_HTTP_HOST, port, timeout=30)
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
    return response.status, response_headers, _parse_response_body(response_headers.get("content-type", "").lower(), body)


def _run_raw_http_checks(*, port: int) -> dict[str, Any]:
    unauthorized_status, _headers, _payload = _post_jsonrpc(
        {"jsonrpc": "2.0", "id": "unauthorized", "method": "tools/list"},
        port=port,
        api_key=None,
    )
    if unauthorized_status != 401:
        raise RuntimeError(f"Expected 401 without API key, got {unauthorized_status}")

    initialize_status, initialize_headers, initialize_payload = _post_jsonrpc(
        {
            "jsonrpc": "2.0",
            "id": "init-1",
            "method": "initialize",
            "params": {
                "protocolVersion": LATEST_PROTOCOL_VERSION,
                "capabilities": {},
                "clientInfo": {"name": "smoke-test", "version": "0.1.0"},
            },
        },
        port=port,
    )
    if initialize_status != 200:
        raise RuntimeError(f"Initialize failed with status {initialize_status}: {initialize_payload}")

    session_id = initialize_headers.get(SESSION_ID_HEADER)
    if not session_id:
        raise RuntimeError("Initialize response did not include an mcp-session-id header")
    if initialize_payload is None or initialize_payload.get("result", {}).get("serverInfo", {}).get("name") != "Linux Diagnostics Demo":
        raise RuntimeError(f"Unexpected initialize payload: {initialize_payload}")

    initialized_status, _initialized_headers, initialized_payload = _post_jsonrpc(
        {"jsonrpc": "2.0", "method": "notifications/initialized"},
        port=port,
        session_id=session_id,
    )
    if initialized_status not in {200, 202, 204}:
        raise RuntimeError(f"Initialized notification failed with status {initialized_status}: {initialized_payload}")

    tools_status, _tools_headers, tools_payload = _post_jsonrpc(
        {"jsonrpc": "2.0", "id": "tools-1", "method": "tools/list"},
        port=port,
        session_id=session_id,
    )
    if tools_status != 200:
        raise RuntimeError(f"tools/list failed with status {tools_status}: {tools_payload}")
    tool_names = [tool["name"] for tool in tools_payload["result"]["tools"]]

    system_status, _system_headers, system_payload = _post_jsonrpc(
        {
            "jsonrpc": "2.0",
            "id": "tool-1",
            "method": "tools/call",
            "params": {"name": "get_system_info", "arguments": {}},
        },
        port=port,
        session_id=session_id,
    )
    if system_status != 200:
        raise RuntimeError(f"tools/call failed with status {system_status}: {system_payload}")

    return {
        "unauthorized_status": unauthorized_status,
        "session_id": session_id,
        "tools": tool_names,
        "system_info_call": system_payload,
    }


async def _run_sdk_http_checks(*, port: int) -> dict[str, Any]:
    async with httpx.AsyncClient(headers={API_KEY_HEADER: DEMO_API_KEY}) as http_client:
        async with streamable_http_client(build_mcp_url(host=DEFAULT_HTTP_HOST, port=port), http_client=http_client) as (read, write, get_session_id):
            async with ClientSession(read, write) as session:
                await session.initialize()
                session_id = get_session_id()
                if not session_id:
                    raise RuntimeError("SDK HTTP session did not retain an mcp-session-id")

                tools = await session.list_tools()
                tool_names = [tool.name for tool in tools.tools]
                expected_tools = {
                    "get_system_info",
                    "get_process_list",
                    "get_process_by_id",
                    "get_process_by_name",
                    "create_log_snapshot",
                    "kill_process",
                }
                if not expected_tools.issubset(tool_names):
                    missing_tools = sorted(expected_tools - set(tool_names))
                    raise RuntimeError(f"Expected tools were not advertised by the server: {missing_tools}")

                prompts = await session.list_prompts()
                prompt_names = {prompt.name for prompt in prompts.prompts}
                expected_prompts = {
                    "AnalyzeRecentApplicationErrors",
                    "ExplainHighCpu",
                    "DetectSecurityAnomalies",
                    "DiagnoseSystemHealth",
                }
                if prompt_names != expected_prompts:
                    raise RuntimeError(f"Expected prompts were not advertised by the server: {sorted(expected_prompts - prompt_names)}")

                resource_templates = await session.list_resource_templates()
                template_uris = {template.uriTemplate for template in resource_templates.resourceTemplates}
                expected_templates = {
                    "syslog://snapshot/{snapshot_id}",
                    "syslog://snapshot/{snapshot_id}?limit={limit}&offset={offset}",
                }
                if not expected_templates.issubset(template_uris):
                    raise RuntimeError(
                        f"Expected resource templates were not advertised by the server: {sorted(expected_templates - template_uris)}"
                    )

                system_result = await session.call_tool("get_system_info", {})
                if system_result.isError:
                    raise RuntimeError(f"Tool call failed: {system_result.content}")

                process_list_result = await session.call_tool("get_process_list", {})
                if process_list_result.isError:
                    raise RuntimeError(f"Process list tool failed: {process_list_result.content}")

                process_list = process_list_result.structuredContent
                if isinstance(process_list, dict) and "result" in process_list:
                    process_list = process_list["result"]
                if not isinstance(process_list, list) or not process_list:
                    raise RuntimeError("Expected get_process_list to return at least one process")

                process_detail = None
                process_page = None
                for process_entry in process_list[:10]:
                    process_id = process_entry["process_id"]
                    process_name = process_entry["process_name"]

                    process_detail_result = await session.call_tool("get_process_by_id", {"process_id": process_id})
                    if process_detail_result.isError:
                        continue

                    process_page_result = await session.call_tool("get_process_by_name", {"process_name": process_name})
                    if process_page_result.isError:
                        continue

                    process_detail = process_detail_result.structuredContent
                    process_page = process_page_result.structuredContent
                    break

                if process_detail is None or process_page is None:
                    raise RuntimeError("Unable to complete live process detail smoke calls")

                snapshot_result = await session.call_tool("create_log_snapshot", {"filter_text": "error", "max_lines": 25})
                if snapshot_result.isError:
                    raise RuntimeError(f"Log snapshot tool failed: {snapshot_result.content}")

                snapshot_payload = snapshot_result.structuredContent
                if not isinstance(snapshot_payload, dict) or "resource_uri" not in snapshot_payload:
                    raise RuntimeError("Expected create_log_snapshot to return a resource URI")

                prompt_result = await session.get_prompt("DiagnoseSystemHealth", {"search_text": "error"})
                if not prompt_result.messages:
                    raise RuntimeError("Expected DiagnoseSystemHealth prompt to return at least one message")

                resource_result = await session.read_resource(snapshot_payload["resource_uri"])
                rendered_snapshot = resource_result.contents[0].text
                if '"pagination"' not in rendered_snapshot:
                    raise RuntimeError("Expected log snapshot resource to include pagination metadata")

                kill_result = await session.call_tool("kill_process", {"process_id": 999999})
                if not kill_result.isError:
                    raise RuntimeError("Expected kill_process to fail safely without elicitation support")
                kill_text = "\n".join(item.text for item in kill_result.content if hasattr(item, "text"))
                if "Client does not support elicitation" not in kill_text:
                    raise RuntimeError(f"Unexpected kill_process safety error: {kill_text}")

                return {
                    "session_id": session_id,
                    "tools": tool_names,
                    "prompts": sorted(prompt_names),
                    "resource_templates": sorted(template_uris),
                    "system_info": system_result.structuredContent,
                    "process_sample": process_detail,
                    "process_page": process_page,
                    "log_snapshot": snapshot_payload,
                    "kill_process_error": kill_text,
                }


def run_server_smoke() -> dict[str, object]:
    port = _find_free_port()
    process = _start_server(port)
    try:
        return {
            "base_url": build_mcp_url(host=DEFAULT_HTTP_HOST, port=port),
            "http": _run_raw_http_checks(port=port),
            "sdk": asyncio.run(_run_sdk_http_checks(port=port)),
        }
    finally:
        _stop_server(process)


def run_agent_smoke() -> dict[str, object]:
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("AZURE_OPENAI_") and not key.startswith("MCP_DEMO_AZURE_OPENAI_")
    }
    env["PYTHONPATH"] = (
        f"{REPO_ROOT / 'src'}:{env['PYTHONPATH']}"
        if env.get("PYTHONPATH")
        else str(REPO_ROOT / "src")
    )

    result = subprocess.run(
        [sys.executable, "-m", "mcp_linux_diag_server.client", "--no-local-env", "--prompt", "Summarize this machine."],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 2:
        raise RuntimeError(
            "Expected the agent smoke to fail fast without Azure configuration, "
            f"but exit code was {result.returncode}."
        )
    if "Missing Azure OpenAI settings" not in result.stderr:
        raise RuntimeError(f"Unexpected agent failure output: {result.stderr.strip()}")

    return {
        "exit_code": result.returncode,
        "stderr": result.stderr.strip(),
    }


def main() -> None:
    server_payload = run_server_smoke()
    print(json.dumps({"server": server_payload}, indent=2, sort_keys=True))
    agent_payload = run_agent_smoke()
    print(json.dumps({"agent": agent_payload}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
