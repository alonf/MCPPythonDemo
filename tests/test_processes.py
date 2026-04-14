from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

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


if __name__ == "__main__":
    unittest.main()
