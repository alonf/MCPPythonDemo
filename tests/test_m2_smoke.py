from __future__ import annotations

import asyncio
import subprocess
import sys
import unittest

from tests.http_harness import open_session, running_server


class M2ServerSmokeTests(unittest.TestCase):
    def run_with_session(self, assertion):  # noqa: ANN001, ANN201
        async def runner() -> None:
            with running_server() as (host, port, _process):
                async with open_session(host=host, port=port) as (session, initialize_result, _session_id):
                    await assertion(session, initialize_result)

        asyncio.run(runner())

    def start_sleep_process(self) -> subprocess.Popen[str]:
        proc = subprocess.Popen([sys.executable, "-c", "import time; time.sleep(30)"], text=True)
        self.addCleanup(self.stop_process, proc)
        return proc

    @staticmethod
    def stop_process(proc: subprocess.Popen[str]) -> None:
        if proc.poll() is not None:
            return
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait(timeout=5)

    def test_list_tools_includes_process_inspection_tools(self) -> None:
        async def assertion(session, initialize_result):  # noqa: ARG001
            tools = await session.list_tools()
            tool_names = {tool.name for tool in tools.tools}
            self.assertTrue({"get_process_list", "get_process_by_id", "get_process_by_name"}.issubset(tool_names))

        self.run_with_session(assertion)

    def test_get_process_list_includes_spawned_subprocess(self) -> None:
        proc = self.start_sleep_process()

        async def assertion(session, initialize_result):  # noqa: ARG001
            result = await session.call_tool("get_process_list", {})
            self.assertFalse(result.isError)
            payload = result.structuredContent
            if isinstance(payload, dict) and "result" in payload:
                payload = payload["result"]
            self.assertIsInstance(payload, list)
            self.assertIn(proc.pid, {item["process_id"] for item in payload})

        self.run_with_session(assertion)

    def test_get_process_by_id_returns_detail_for_live_process(self) -> None:
        proc = self.start_sleep_process()

        async def assertion(session, initialize_result):  # noqa: ARG001
            result = await session.call_tool("get_process_by_id", {"process_id": proc.pid})
            self.assertFalse(result.isError)
            payload = result.structuredContent
            self.assertEqual(payload["process_id"], proc.pid)
            self.assertTrue(payload["process_name"])
            self.assertGreaterEqual(payload["total_cpu_time_seconds"], 0.0)
            self.assertEqual(
                set(payload["memory"]),
                {"virtual_memory_bytes", "resident_set_bytes", "shared_memory_bytes"},
            )

        self.run_with_session(assertion)

    def test_get_process_by_name_supports_live_lookup_and_paging(self) -> None:
        proc = self.start_sleep_process()

        async def assertion(session, initialize_result):  # noqa: ARG001
            detail_result = await session.call_tool("get_process_by_id", {"process_id": proc.pid})
            self.assertFalse(detail_result.isError)
            process_name = detail_result.structuredContent["process_name"]

            full_result = await session.call_tool(
                "get_process_by_name",
                {"process_name": process_name, "page_number": 1, "page_size": 200},
            )
            self.assertFalse(full_result.isError)
            full_payload = full_result.structuredContent
            self.assertGreaterEqual(full_payload["total_count"], 1)
            self.assertIn(proc.pid, {item["process_id"] for item in full_payload["processes"]})

            paged_result = await session.call_tool(
                "get_process_by_name",
                {"process_name": process_name, "page_number": 1, "page_size": 1},
            )
            self.assertFalse(paged_result.isError)
            paged_payload = paged_result.structuredContent
            self.assertEqual(paged_payload["page_number"], 1)
            self.assertEqual(paged_payload["page_size"], 1)
            self.assertLessEqual(len(paged_payload["processes"]), 1)
            self.assertEqual(set(paged_payload), {"processes", "page_number", "page_size", "total_count", "has_more"})

        self.run_with_session(assertion)

    def test_get_process_by_name_returns_empty_result_for_unknown_name(self) -> None:
        async def assertion(session, initialize_result):  # noqa: ARG001
            result = await session.call_tool(
                "get_process_by_name",
                {"process_name": "definitely-no-such-process-name", "page_number": 1, "page_size": 5},
            )
            self.assertFalse(result.isError)
            payload = result.structuredContent
            self.assertEqual(payload["total_count"], 0)
            self.assertEqual(payload["processes"], [])
            self.assertFalse(payload["has_more"])

        self.run_with_session(assertion)

    def test_get_process_by_id_returns_error_for_missing_pid(self) -> None:
        async def assertion(session, initialize_result):  # noqa: ARG001
            result = await session.call_tool("get_process_by_id", {"process_id": 99999999})
            self.assertTrue(result.isError)
            self.assertTrue(result.content)
            self.assertIn("No process found", result.content[0].text)

        self.run_with_session(assertion)


if __name__ == "__main__":
    unittest.main()
