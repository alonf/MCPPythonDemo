from __future__ import annotations

import os
import subprocess
import sys
import unittest
from pathlib import Path

from mcp.types import CallToolResult, TextContent, Tool

from mcp_linux_diag_server.client import (
    AssistantTurn,
    ChatConfig,
    ClientConfigurationError,
    ToolCallRequest,
    assistant_turn_to_message,
    build_openai_tools,
    load_local_env_file,
    run_agent_turn,
    serialize_tool_result,
)


class ChatConfigTests(unittest.TestCase):
    def test_from_sources_uses_prefixed_environment(self) -> None:
        config = ChatConfig.from_sources(
            environ={
                "MCP_DEMO_AZURE_OPENAI_ENDPOINT": "https://demo.openai.azure.com/",
                "MCP_DEMO_AZURE_OPENAI_API_KEY": "secret",
            }
        )

        self.assertEqual(config.endpoint, "https://demo.openai.azure.com/")
        self.assertEqual(config.api_key, "secret")
        self.assertEqual(config.deployment, "model-router")

    def test_load_local_env_file_reads_simple_key_values(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        env_file = repo_root / ".env.local.test"
        self.addCleanup(lambda: env_file.unlink(missing_ok=True))
        env_file.write_text(
            "MCP_DEMO_AZURE_OPENAI_ENDPOINT=https://demo.openai.azure.com/\n"
            "MCP_DEMO_AZURE_OPENAI_API_KEY='secret'\n",
            encoding="utf-8",
        )

        values = load_local_env_file(env_file)

        self.assertEqual(values["MCP_DEMO_AZURE_OPENAI_ENDPOINT"], "https://demo.openai.azure.com/")
        self.assertEqual(values["MCP_DEMO_AZURE_OPENAI_API_KEY"], "secret")

    def test_from_sources_uses_local_env_file_when_shell_is_empty(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        env_file = repo_root / ".env.local.test"
        self.addCleanup(lambda: env_file.unlink(missing_ok=True))
        env_file.write_text(
            "MCP_DEMO_AZURE_OPENAI_ENDPOINT=https://demo.openai.azure.com/\n"
            "MCP_DEMO_AZURE_OPENAI_API_KEY=from-file\n"
            "MCP_DEMO_AZURE_OPENAI_DEPLOYMENT=lecture-router\n",
            encoding="utf-8",
        )

        config = ChatConfig.from_sources(environ={}, env_file=str(env_file))

        self.assertEqual(config.endpoint, "https://demo.openai.azure.com/")
        self.assertEqual(config.api_key, "from-file")
        self.assertEqual(config.deployment, "lecture-router")

    def test_from_sources_prefers_environment_over_local_env_file(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        env_file = repo_root / ".env.local.test"
        self.addCleanup(lambda: env_file.unlink(missing_ok=True))
        env_file.write_text(
            "MCP_DEMO_AZURE_OPENAI_ENDPOINT=https://file.openai.azure.com/\n"
            "MCP_DEMO_AZURE_OPENAI_API_KEY=from-file\n",
            encoding="utf-8",
        )

        config = ChatConfig.from_sources(
            environ={
                "MCP_DEMO_AZURE_OPENAI_ENDPOINT": "https://env.openai.azure.com/",
                "MCP_DEMO_AZURE_OPENAI_API_KEY": "from-env",
            },
            env_file=str(env_file),
        )

        self.assertEqual(config.endpoint, "https://env.openai.azure.com/")
        self.assertEqual(config.api_key, "from-env")

    def test_from_sources_allows_default_credential_without_api_key(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        env_file = repo_root / ".env.local.test"
        self.addCleanup(lambda: env_file.unlink(missing_ok=True))
        env_file.write_text(
            "MCP_DEMO_AZURE_OPENAI_ENDPOINT=https://demo.openai.azure.com/\n"
            "MCP_DEMO_AZURE_OPENAI_USE_DEFAULT_CREDENTIAL=true\n",
            encoding="utf-8",
        )

        config = ChatConfig.from_sources(environ={}, env_file=str(env_file))

        self.assertTrue(config.use_default_credential)
        self.assertIsNone(config.api_key)

    def test_from_sources_requires_endpoint_and_key(self) -> None:
        with self.assertRaises(ClientConfigurationError):
            ChatConfig.from_sources(environ={})


class ToolTranslationTests(unittest.TestCase):
    def test_build_openai_tools_preserves_schema(self) -> None:
        tools = build_openai_tools(
            [
                Tool(
                    name="get_system_info",
                    description="Get a Linux snapshot.",
                    inputSchema={"type": "object", "properties": {}, "additionalProperties": False},
                )
            ]
        )

        self.assertEqual(tools[0]["function"]["name"], "get_system_info")
        self.assertFalse(tools[0]["function"]["parameters"]["additionalProperties"])

    def test_assistant_turn_to_message_keeps_tool_payload(self) -> None:
        message = assistant_turn_to_message(
            AssistantTurn(
                content="",
                tool_calls=[ToolCallRequest(id="call-1", name="get_system_info", arguments={})],
            )
        )

        self.assertEqual(message["role"], "assistant")
        self.assertEqual(message["tool_calls"][0]["function"]["name"], "get_system_info")

    def test_serialize_tool_result_prefers_structured_content(self) -> None:
        result = CallToolResult(
            content=[TextContent(type="text", text="ignored")],
            structuredContent={"machine_name": "demo-host"},
            isError=False,
        )

        self.assertIn("demo-host", serialize_tool_result(result))


class FakeSession:
    def __init__(self) -> None:
        self.calls: list[tuple[str, dict[str, object]]] = []

    async def call_tool(self, name: str, arguments: dict[str, object]) -> CallToolResult:
        self.calls.append((name, arguments))
        return CallToolResult(
            content=[TextContent(type="text", text="tool fallback")],
            structuredContent={"machine_name": "demo-host", "uptime_seconds": 12.5},
            isError=False,
        )


class FakeModel:
    def __init__(self) -> None:
        self.turns = [
            AssistantTurn(
                content="",
                tool_calls=[ToolCallRequest(id="call-1", name="get_system_info", arguments={})],
            ),
            AssistantTurn(content="The host is demo-host and uptime is 12.5 seconds.", tool_calls=[]),
        ]

    def complete(self, messages, tools):  # noqa: ANN001, ANN201
        return self.turns.pop(0)


class AgentLoopTests(unittest.IsolatedAsyncioTestCase):
    async def test_run_agent_turn_executes_tool_and_returns_final_text(self) -> None:
        session = FakeSession()
        model = FakeModel()
        messages = [{"role": "system", "content": "Be helpful."}, {"role": "user", "content": "Check the system."}]

        answer = await run_agent_turn(
            session=session,
            model=model,
            messages=messages,
            tools=[],
        )

        self.assertEqual(answer, "The host is demo-host and uptime is 12.5 seconds.")
        self.assertEqual(session.calls, [("get_system_info", {})])
        self.assertEqual(messages[-1]["content"], "The host is demo-host and uptime is 12.5 seconds.")

    async def test_cli_reports_missing_configuration_cleanly(self) -> None:
        repo_root = Path(__file__).resolve().parents[1]
        env = {
            key: value
            for key, value in os.environ.items()
            if not key.startswith("AZURE_OPENAI_") and not key.startswith("MCP_DEMO_AZURE_OPENAI_")
        }

        result = subprocess.run(
            [sys.executable, "-m", "mcp_linux_diag_server.client", "--no-local-env", "--prompt", "Summarize this machine."],
            cwd=repo_root,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

        self.assertEqual(result.returncode, 2)
        self.assertIn("Missing Azure OpenAI settings", result.stderr)


if __name__ == "__main__":
    unittest.main()
