from __future__ import annotations

import asyncio
import unittest

from tests.http_harness import open_session, running_server


class M1ServerSmokeTests(unittest.TestCase):
    def run_with_session(self, assertion):  # noqa: ANN001, ANN201
        async def runner() -> None:
            with running_server() as (host, port, _process):
                async with open_session(host=host, port=port) as (session, initialize_result, _session_id):
                    await assertion(session, initialize_result)

        asyncio.run(runner())

    def test_initialize_advertises_tools_capability(self) -> None:
        async def assertion(session, initialize_result):  # noqa: ARG001
            self.assertTrue(initialize_result.capabilities.tools)
            self.assertEqual(initialize_result.serverInfo.name, "Linux Diagnostics Demo")

        self.run_with_session(assertion)

    def test_list_tools_includes_get_system_info(self) -> None:
        async def assertion(session, initialize_result):  # noqa: ARG001
            tools = await session.list_tools()
            self.assertIn("get_system_info", [tool.name for tool in tools.tools])

        self.run_with_session(assertion)

    def test_get_system_info_returns_expected_schema(self) -> None:
        async def assertion(session, initialize_result):  # noqa: ARG001
            result = await session.call_tool("get_system_info", {})
            self.assertFalse(result.isError)

            payload = result.structuredContent
            self.assertIsInstance(payload, dict)
            expected_keys = {
                "machine_name",
                "user_name",
                "os_description",
                "kernel_release",
                "architecture",
                "processor_count",
                "python_runtime",
                "current_directory",
                "uptime_seconds",
                "uptime_human",
                "load_average",
                "memory",
                "wsl_detected",
            }
            self.assertTrue(expected_keys.issubset(payload.keys()))
            self.assertGreaterEqual(payload["processor_count"], 1)
            self.assertGreaterEqual(payload["uptime_seconds"], 0.0)
            self.assertEqual(set(payload["load_average"]), {"one_minute", "five_minutes", "fifteen_minutes"})
            self.assertEqual(set(payload["memory"]), {"total_bytes", "available_bytes", "used_bytes"})

        self.run_with_session(assertion)

    def test_get_system_info_ignores_extra_arguments(self) -> None:
        async def assertion(session, initialize_result):  # noqa: ARG001
            result = await session.call_tool("get_system_info", {"ignored": True})
            self.assertFalse(result.isError)
            self.assertIsInstance(result.structuredContent, dict)

        self.run_with_session(assertion)

    def test_invalid_tool_returns_error_message(self) -> None:
        async def assertion(session, initialize_result):  # noqa: ARG001
            result = await session.call_tool("tool_does_not_exist", {})
            self.assertTrue(result.isError)
            self.assertTrue(result.content)
            self.assertIn("Unknown tool", result.content[0].text)

        self.run_with_session(assertion)


if __name__ == "__main__":
    unittest.main()
