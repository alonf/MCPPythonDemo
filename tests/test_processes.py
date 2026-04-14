from __future__ import annotations

import asyncio
import sys
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from mcp_linux_diag_server.tools import processes


class ProcessToolUnitTests(unittest.TestCase):
    def test_list_processes_sorts_results_and_skips_missing_names(self) -> None:
        with (
            patch.object(processes, "_iter_process_ids", return_value=[22, 11, 33]),
            patch.object(processes, "_read_process_name", side_effect=["bash", "python3", None]),
        ):
            result = processes.list_processes()

        self.assertEqual([item.process_name for item in result], ["bash", "python3"])
        self.assertEqual([item.process_id for item in result], [22, 11])

    def test_get_process_by_id_raises_clear_error_for_missing_process(self) -> None:
        with patch.object(processes, "_read_process_detail", return_value=None):
            with self.assertRaisesRegex(ValueError, "No process found"):
                processes.get_process_by_id(999999)

    def test_get_processes_by_name_uses_default_pagination_and_normalized_query(self) -> None:
        detail = lambda pid: processes.ProcessDetailResult(  # noqa: E731
            process_id=pid,
            process_name="python",
            parent_process_id=1,
            state="S",
            thread_count=1,
            user_name="demo",
            command_line=["python"],
            executable_path=None,
            current_working_directory=None,
            start_time_utc=None,
            uptime_seconds=0.0,
            total_cpu_time_seconds=0.0,
            open_file_descriptor_count=None,
            memory=processes.ProcessMemorySnapshot(
                virtual_memory_bytes=0,
                resident_set_bytes=0,
                shared_memory_bytes=0,
            ),
        )
        matcher = Mock(side_effect=[True, True, True, True, True, True])

        with (
            patch.object(processes, "_iter_process_ids", return_value=[10, 11, 12, 13, 14, 15]),
            patch.object(processes, "_process_matches_name", matcher),
            patch.object(processes, "_read_process_detail", side_effect=[detail(pid) for pid in [10, 11, 12, 13, 14, 15]]),
        ):
            result = processes.get_processes_by_name("python.exe", page_number=0, page_size=0)

        self.assertEqual(result.page_number, 1)
        self.assertEqual(result.page_size, 5)
        self.assertEqual(result.total_count, 6)
        self.assertTrue(result.has_more)
        self.assertEqual([item.process_id for item in result.processes], [10, 11, 12, 13, 14])
        self.assertTrue(all(call.args[1] == "python" for call in matcher.call_args_list))

    def test_read_process_detail_keeps_partial_payload_when_optional_reads_fail(self) -> None:
        process_dir = REPO_ROOT / "src"

        with (
            patch.object(processes.Path, "is_dir", return_value=True),
            patch.object(
                processes,
                "_read_status_fields",
                return_value={"Name": "python3", "PPid": "1", "State": "S", "Threads": "4", "Uid": "1000"},
            ),
            patch.object(processes, "_read_stat_snapshot", return_value=None),
            patch.object(processes, "_read_link", return_value=None),
            patch.object(processes, "_read_command_line", return_value=[]),
            patch.object(processes, "_lookup_user_name", return_value="demo"),
            patch.object(processes, "_format_process_start_time", return_value=None),
            patch.object(processes, "_read_process_uptime_seconds", return_value=0.0),
            patch.object(processes, "_read_total_cpu_time_seconds", return_value=0.0),
            patch.object(processes, "_count_open_file_descriptors", return_value=None),
            patch.object(
                processes,
                "_read_process_memory",
                return_value=processes.ProcessMemorySnapshot(
                    virtual_memory_bytes=0,
                    resident_set_bytes=0,
                    shared_memory_bytes=0,
                ),
            ),
        ):
            result = processes._read_process_detail(77)

        self.assertIsNotNone(result)
        self.assertEqual(result.process_id, 77)
        self.assertEqual(result.process_name, "python3")
        self.assertIsNone(result.current_working_directory)
        self.assertIsNone(result.executable_path)
        self.assertEqual(result.command_line, [])
        self.assertEqual(result.memory.virtual_memory_bytes, 0)

    def test_sample_top_cpu_processes_ranks_by_cpu_then_memory(self) -> None:
        initial = {
            10: processes._ProcessRuntimeSnapshot(10, "python", 200, 100),
            11: processes._ProcessRuntimeSnapshot(11, "worker", 500, 200),
            12: processes._ProcessRuntimeSnapshot(12, "idle", 100, 300),
        }
        later = {
            10: processes._ProcessRuntimeSnapshot(10, "python", 200, 125),
            11: processes._ProcessRuntimeSnapshot(11, "worker", 500, 230),
            12: processes._ProcessRuntimeSnapshot(12, "idle", 100, 300),
        }

        async def run_test() -> None:
            with (
                patch.object(processes, "_capture_runtime_snapshot", side_effect=[initial, later]),
                patch.object(processes.asyncio, "sleep", new=AsyncMock()),
                patch.object(processes.os, "cpu_count", return_value=2),
            ):
                result = await processes.sample_top_cpu_processes(take=2)

            self.assertEqual([item.process_id for item in result], [11, 10])
            self.assertGreater(result[0].cpu_percent, result[1].cpu_percent)

        asyncio.run(run_test())


class _FakeServerSession:
    def __init__(self, *, supports_elicitation: bool = True, elicitation_responses: list[object] | None = None) -> None:
        self.supports_elicitation = supports_elicitation
        self.elicitation_responses = list(elicitation_responses or [])
        self.elicitation_requests: list[tuple[str, dict[str, object], object]] = []

    def check_client_capability(self, _capability) -> bool:  # noqa: ANN001
        return self.supports_elicitation

    async def elicit_form(self, message: str, requested_schema: dict[str, object], related_request_id=None):  # noqa: ANN001, ANN201
        self.elicitation_requests.append((message, requested_schema, related_request_id))
        return self.elicitation_responses.pop(0)


class ProcessKillWorkflowTests(unittest.IsolatedAsyncioTestCase):
    async def test_kill_process_requires_elicitation_capability(self) -> None:
        ctx = SimpleNamespace(request_context=SimpleNamespace(session=_FakeServerSession(supports_elicitation=False)))

        with self.assertRaisesRegex(RuntimeError, "Client does not support elicitation"):
            await processes.kill_process(process_id=123, ctx=ctx)

    async def test_kill_process_without_pid_elicits_selection_and_confirmation(self) -> None:
        session = _FakeServerSession(
            elicitation_responses=[
                SimpleNamespace(action="accept", content={"process": "321"}),
                SimpleNamespace(action="accept", content={"confirmation": "confirm pid 321"}),
            ]
        )
        ctx = SimpleNamespace(request_context=SimpleNamespace(session=session), request_id="req-1")
        candidate = processes.ProcessCpuUsage(process_id=321, process_name="burner", working_set_bytes=4096, cpu_percent=88.5)

        with (
            patch.object(processes, "sample_top_cpu_processes", new=AsyncMock(return_value=[candidate])),
            patch.object(processes, "_terminate_process", new=AsyncMock()),
        ):
            result = await processes.kill_process(reason="test", ctx=ctx)

        self.assertEqual(result.status, "terminated")
        self.assertEqual(result.process_id, 321)
        selection_message, selection_schema, _ = session.elicitation_requests[0]
        confirmation_message, confirmation_schema, _ = session.elicitation_requests[1]
        self.assertIn("top CPU consumers", selection_message)
        self.assertEqual(selection_schema["properties"]["process"]["oneOf"][0]["const"], "321")
        self.assertIn("CPU 88.5%", selection_schema["properties"]["process"]["oneOf"][0]["title"])
        self.assertIn("cannot be undone", confirmation_message)
        self.assertIn("CONFIRM PID 321", confirmation_schema["properties"]["confirmation"]["description"])


if __name__ == "__main__":
    unittest.main()
