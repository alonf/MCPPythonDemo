from __future__ import annotations

import asyncio
import subprocess
import unittest

import mcp.types as types

from tests.http_harness import open_session, running_server


class M5HttpElicitationTests(unittest.TestCase):
    def test_kill_process_requires_elicitation_capability(self) -> None:
        async def runner() -> None:
            with running_server() as (host, port, _process):
                async with open_session(host=host, port=port) as (session, _initialize_result, _session_id):
                    result = await session.call_tool("kill_process", {"process_id": 999999})
                    self.assertTrue(result.isError)
                    self.assertIn("Client does not support elicitation", result.content[0].text)

        asyncio.run(runner())

    def test_kill_process_with_pid_terminates_confirmed_subprocess(self) -> None:
        worker = subprocess.Popen(["sleep", "30"])
        self.addCleanup(self._cleanup_process, worker)

        async def confirm_callback(_context, params):  # noqa: ANN001, ANN202
            return types.ElicitResult(
                action="accept",
                content={"confirmation": f"confirm pid {worker.pid}"},
            )

        async def runner() -> None:
            with running_server() as (host, port, _process):
                async with open_session(host=host, port=port, elicitation_callback=confirm_callback) as (
                    session,
                    _initialize_result,
                    _session_id,
                ):
                    result = await session.call_tool("kill_process", {"process_id": worker.pid, "reason": "test"})
                    self.assertFalse(result.isError)
                    payload = result.structuredContent
                    self.assertEqual(payload["status"], "terminated")
                    self.assertEqual(payload["process_id"], worker.pid)
                    self.assertEqual(payload["reason"], "test")
                    await asyncio.to_thread(worker.wait, 5)
                    self.assertIsNotNone(worker.returncode)

        asyncio.run(runner())

    @staticmethod
    def _cleanup_process(process: subprocess.Popen[str]) -> None:
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait(timeout=5)


if __name__ == "__main__":
    unittest.main()
