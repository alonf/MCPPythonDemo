from __future__ import annotations

import asyncio
import unittest

from tests.http_harness import open_session, running_server


class M3ServerSmokeTests(unittest.TestCase):
    def run_with_session(self, assertion):  # noqa: ANN001, ANN201
        async def runner() -> None:
            with running_server() as (host, port, _process):
                async with open_session(host=host, port=port) as (session, initialize_result, _session_id):
                    await assertion(session, initialize_result)

        asyncio.run(runner())

    def test_server_advertises_log_snapshot_tool_and_prompts(self) -> None:
        async def assertion(session, initialize_result):  # noqa: ARG001
            tools = await session.list_tools()
            prompts = await session.list_prompts()
            prompt_names = {prompt.name for prompt in prompts.prompts}
            tool_names = {tool.name for tool in tools.tools}

            self.assertIn("create_log_snapshot", tool_names)
            self.assertEqual(
                prompt_names,
                {
                    "AnalyzeRecentApplicationErrors",
                    "ExplainHighCpu",
                    "DetectSecurityAnomalies",
                    "DiagnoseSystemHealth",
                    "TroubleshootLinuxComponent",
                },
            )

        self.run_with_session(assertion)

    def test_create_log_snapshot_returns_resource_uri_and_readable_resource(self) -> None:
        async def assertion(session, initialize_result):  # noqa: ARG001
            snapshot_result = await session.call_tool("create_log_snapshot", {"filter_text": "error", "max_lines": 25})
            self.assertFalse(snapshot_result.isError)

            payload = snapshot_result.structuredContent
            self.assertEqual(set(payload), {"snapshot_id", "log_name", "source_path", "filter_text", "created_at_utc", "line_count", "resource_uri", "paginated_resource_template"})
            self.assertTrue(payload["resource_uri"].startswith("syslog://snapshot/"))

            resource_result = await session.read_resource(payload["resource_uri"])
            rendered = resource_result.contents[0].text
            self.assertIn('"pagination"', rendered)
            self.assertIn('"snapshot_id"', rendered)

        self.run_with_session(assertion)

    def test_resource_templates_advertise_paged_snapshot_pattern(self) -> None:
        async def assertion(session, initialize_result):  # noqa: ARG001
            templates = await session.list_resource_templates()
            template_uris = {template.uriTemplate for template in templates.resourceTemplates}

            self.assertIn("syslog://snapshot/{snapshot_id}", template_uris)
            self.assertIn("syslog://snapshot/{snapshot_id}?limit={limit}&offset={offset}", template_uris)

        self.run_with_session(assertion)

    def test_get_prompt_returns_plain_text_workflow(self) -> None:
        async def assertion(session, initialize_result):  # noqa: ARG001
            prompt = await session.get_prompt("DiagnoseSystemHealth", {"search_text": "error"})
            self.assertTrue(prompt.messages)
            self.assertIn("get_system_info", prompt.messages[0].content.text)
            self.assertIn("read_resource", prompt.messages[0].content.text)

        self.run_with_session(assertion)


if __name__ == "__main__":
    unittest.main()
