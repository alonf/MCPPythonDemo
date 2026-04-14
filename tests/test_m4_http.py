from __future__ import annotations

import asyncio
import http.client
import json
import unittest

from mcp_linux_diag_server.http_config import API_KEY_QUERY_PARAMETER, DEFAULT_MCP_PATH, SESSION_ID_HEADER
from tests.http_harness import post_jsonrpc, running_server, open_session

API_KEY = "secure-mcp-key"
INITIALIZE_PAYLOAD = {
    "jsonrpc": "2.0",
    "id": "initialize",
    "method": "initialize",
    "params": {
        "protocolVersion": "2025-03-26",
        "capabilities": {},
        "clientInfo": {"name": "m4-http-tests", "version": "0.1"},
    },
}


def post_jsonrpc_query_param(*, host: str, port: int, payload: dict[str, object]) -> tuple[int, dict[str, str], dict[str, object] | None]:
    connection = http.client.HTTPConnection(host, port, timeout=30)
    connection.request(
        "POST",
        f"{DEFAULT_MCP_PATH}?{API_KEY_QUERY_PARAMETER}={API_KEY}",
        body=json.dumps(payload),
        headers={
            "Accept": "application/json, text/event-stream",
            "Content-Type": "application/json",
        },
    )
    response = connection.getresponse()
    body = response.read().decode("utf-8")
    headers = {key.lower(): value for key, value in response.getheaders()}
    connection.close()
    content_type = headers.get("content-type", "").lower()
    if content_type.startswith("text/plain"):
        parsed_body = {"text": body}
    elif content_type.startswith("text/event-stream"):
        data_lines = [line[5:].lstrip() for line in body.splitlines() if line.startswith("data:")]
        parsed_body = json.loads("\n".join(data_lines))
    elif content_type.startswith("application/json"):
        parsed_body = json.loads(body)
    else:
        parsed_body = None
    return response.status, headers, parsed_body


class M4HttpTransportTests(unittest.TestCase):
    def run_with_server(self, assertion):  # noqa: ANN001, ANN201
        with running_server() as (host, port, _process):
            assertion(host, port)

    def run_with_session(self, assertion):  # noqa: ANN001, ANN201
        async def runner() -> None:
            with running_server() as (host, port, _process):
                async with open_session(host=host, port=port) as (session, initialize_result, session_id):
                    await assertion(host, port, session, initialize_result, session_id)

        asyncio.run(runner())

    def test_missing_api_key_is_rejected(self) -> None:
        def assertion(host: str, port: int) -> None:
            status, _, body = post_jsonrpc(
                host=host,
                port=port,
                payload=INITIALIZE_PAYLOAD,
                api_key=None,
            )

            self.assertEqual(status, 401)
            self.assertEqual(body, {"text": "Unauthorized"})

        self.run_with_server(assertion)

    def test_query_param_api_key_can_initialize_session(self) -> None:
        def assertion(host: str, port: int) -> None:
            status, headers, body = post_jsonrpc_query_param(host=host, port=port, payload=INITIALIZE_PAYLOAD)

            self.assertEqual(status, 200)
            self.assertTrue(headers.get(SESSION_ID_HEADER))
            self.assertEqual(body["result"]["serverInfo"]["name"], "Linux Diagnostics Demo")

        self.run_with_server(assertion)

    def test_session_id_is_required_after_initialize(self) -> None:
        def assertion(host: str, port: int) -> None:
            initialize_status, headers, _ = post_jsonrpc(host=host, port=port, payload=INITIALIZE_PAYLOAD)
            self.assertEqual(initialize_status, 200)
            session_id = headers.get(SESSION_ID_HEADER)
            self.assertTrue(session_id)

            missing_status, _, missing_body = post_jsonrpc(
                host=host,
                port=port,
                payload={"jsonrpc": "2.0", "id": "no-session", "method": "tools/list", "params": {}},
            )
            self.assertEqual(missing_status, 400)
            self.assertIn("Missing session ID", missing_body["error"]["message"])

            bad_status, _, bad_body = post_jsonrpc(
                host=host,
                port=port,
                payload={"jsonrpc": "2.0", "id": "bad-session", "method": "tools/list", "params": {}},
                session_id="does-not-exist",
            )
            self.assertEqual(bad_status, 404)
            self.assertIn("Session not found", bad_body["error"]["message"])

            good_status, _, good_body = post_jsonrpc(
                host=host,
                port=port,
                payload={"jsonrpc": "2.0", "id": "good-session", "method": "tools/list", "params": {}},
                session_id=session_id,
            )
            self.assertEqual(good_status, 200)
            tool_names = {tool["name"] for tool in good_body["result"]["tools"]}
            self.assertIn("get_system_info", tool_names)
            self.assertIn("create_log_snapshot", tool_names)
            self.assertIn("kill_process", tool_names)

        self.run_with_server(assertion)

    def test_http_transport_keeps_m1_to_m3_surfaces_reachable(self) -> None:
        async def assertion(host, port, session, initialize_result, session_id) -> None:  # noqa: ANN001
            self.assertEqual(initialize_result.serverInfo.name, "Linux Diagnostics Demo")
            self.assertTrue(session_id)

            tools = await session.list_tools()
            tool_names = {tool.name for tool in tools.tools}
            self.assertTrue(
                {
                    "get_system_info",
                    "get_process_list",
                    "get_process_by_id",
                    "get_process_by_name",
                    "create_log_snapshot",
                    "kill_process",
                }.issubset(tool_names)
            )

            prompts = await session.list_prompts()
            self.assertEqual(
                {prompt.name for prompt in prompts.prompts},
                {
                    "AnalyzeRecentApplicationErrors",
                    "ExplainHighCpu",
                    "DetectSecurityAnomalies",
                    "DiagnoseSystemHealth",
                },
            )

            templates = await session.list_resource_templates()
            template_uris = {template.uriTemplate for template in templates.resourceTemplates}
            self.assertIn("syslog://snapshot/{snapshot_id}", template_uris)
            self.assertIn("syslog://snapshot/{snapshot_id}?limit={limit}&offset={offset}", template_uris)

            system_result = await session.call_tool("get_system_info", {})
            self.assertFalse(system_result.isError)

            process_list_result = await session.call_tool("get_process_list", {})
            self.assertFalse(process_list_result.isError)
            process_list = process_list_result.structuredContent
            if isinstance(process_list, dict) and "result" in process_list:
                process_list = process_list["result"]
            self.assertIsInstance(process_list, list)
            self.assertTrue(process_list)

            process_id = process_list[0]["process_id"]
            process_name = process_list[0]["process_name"]

            process_detail_result = await session.call_tool("get_process_by_id", {"process_id": process_id})
            self.assertFalse(process_detail_result.isError)

            process_page_result = await session.call_tool("get_process_by_name", {"process_name": process_name})
            self.assertFalse(process_page_result.isError)

            snapshot_result = await session.call_tool(
                "create_log_snapshot",
                {"filter_text": "error", "max_lines": 10},
            )
            self.assertFalse(snapshot_result.isError)
            snapshot_payload = snapshot_result.structuredContent
            self.assertIn("resource_uri", snapshot_payload)

            prompt_result = await session.get_prompt("DiagnoseSystemHealth", {"search_text": "error"})
            self.assertTrue(prompt_result.messages)

            resource_result = await session.read_resource(snapshot_payload["resource_uri"])
            self.assertIn('"pagination"', resource_result.contents[0].text)

        self.run_with_session(assertion)


if __name__ == "__main__":
    unittest.main()
