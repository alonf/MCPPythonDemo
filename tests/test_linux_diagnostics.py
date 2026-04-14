from __future__ import annotations

import asyncio
import unittest

import mcp.types as types

from mcp_linux_diag_server.tools.m6_diagnostics import LinuxDiagnosticQuery, validate_linux_diagnostic_query
from tests.http_harness import open_session, running_server


class LinuxDiagnosticsValidationTests(unittest.TestCase):
    def test_validate_linux_diagnostic_query_strips_code_fences(self) -> None:
        query = validate_linux_diagnostic_query(
            "```proc\n/proc/meminfo | grep Dirty\n```"
        )

        self.assertEqual(query, LinuxDiagnosticQuery(path="/proc/meminfo", field="Dirty"))

    def test_validate_linux_diagnostic_query_rejects_unallowlisted_path(self) -> None:
        with self.assertRaisesRegex(ValueError, "allowlisted"):
            validate_linux_diagnostic_query("/etc/passwd")

    def test_validate_linux_diagnostic_query_rejects_shell_chaining(self) -> None:
        with self.assertRaisesRegex(ValueError, "forbidden shell"):
            validate_linux_diagnostic_query("/proc/meminfo; cat /etc/passwd")


class _SamplingSequence:
    def __init__(self, *responses: str) -> None:
        self._responses = list(responses)
        self.requests: list[types.CreateMessageRequestParams] = []

    async def __call__(self, _context, params):  # noqa: ANN001, ANN202
        self.requests.append(params)
        if not self._responses:
            raise AssertionError("No canned sampling response remained for the test.")
        return types.CreateMessageResult(
            role="assistant",
            content=types.TextContent(type="text", text=self._responses.pop(0)),
            model="test-model",
            stopReason="endTurn",
        )


class M6HttpSamplingTests(unittest.TestCase):
    def test_troubleshoot_linux_diagnostics_requires_sampling_capability(self) -> None:
        async def runner() -> None:
            with running_server() as (host, port, _process):
                async with open_session(host=host, port=port) as (session, _initialize_result, _session_id):
                    result = await session.call_tool(
                        "troubleshoot_linux_diagnostics",
                        {"user_request": "Show me dirty memory pages."},
                    )
                    self.assertTrue(result.isError)
                    self.assertIn("Client does not support sampling", result.content[0].text)

        asyncio.run(runner())

    def test_troubleshoot_linux_diagnostics_retries_invalid_query_then_succeeds(self) -> None:
        sampler = _SamplingSequence(
            "/etc/passwd",
            "/proc/meminfo | grep Dirty",
            "Dirty memory is currently modest, so the machine is not showing immediate writeback pressure.",
        )

        async def runner() -> None:
            with running_server() as (host, port, _process):
                async with open_session(host=host, port=port, sampling_callback=sampler) as (
                    session,
                    _initialize_result,
                    _session_id,
                ):
                    result = await session.call_tool(
                        "troubleshoot_linux_diagnostics",
                        {"user_request": "Show me dirty memory pages."},
                    )
                    self.assertFalse(result.isError)
                    summary_text = "\n".join(item.text for item in result.content if hasattr(item, "text"))
                    self.assertIn("Dirty memory", summary_text)
                    self.assertEqual(len(sampler.requests), 3)
                    retry_prompt = sampler.requests[1].messages[0].content.text
                    self.assertIn("Previous validation errors", retry_prompt)

        asyncio.run(runner())


if __name__ == "__main__":
    unittest.main()
