from __future__ import annotations

import sys
import unittest
from pathlib import Path
from unittest.mock import Mock, patch

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))

from mcp_linux_diag_server.tools import system_info


class SystemInfoFallbackTests(unittest.TestCase):
    def test_missing_uptime_file_falls_back_to_zero(self) -> None:
        failing_path = Mock()
        failing_path.read_text.side_effect = OSError("missing")

        with patch.object(system_info, "_PROC_UPTIME", failing_path):
            self.assertEqual(system_info._read_uptime_seconds(), 0.0)

    def test_missing_loadavg_file_returns_zeroed_snapshot(self) -> None:
        failing_path = Mock()
        failing_path.read_text.side_effect = OSError("missing")

        with patch.object(system_info, "_PROC_LOADAVG", failing_path):
            load = system_info._read_load_average()

        self.assertEqual(load.one_minute, 0.0)
        self.assertEqual(load.five_minutes, 0.0)
        self.assertEqual(load.fifteen_minutes, 0.0)

    def test_missing_meminfo_file_returns_zeroes(self) -> None:
        failing_path = Mock()
        failing_path.read_text.side_effect = OSError("missing")

        with patch.object(system_info, "_PROC_MEMINFO", failing_path):
            total, available = system_info._read_memory_bytes()

        self.assertEqual((total, available), (0, 0))

    def test_collect_system_info_keeps_payload_non_negative_when_meminfo_missing(self) -> None:
        failing_meminfo = Mock()
        failing_meminfo.read_text.side_effect = OSError("missing")

        with patch.object(system_info, "_PROC_MEMINFO", failing_meminfo):
            result = system_info.collect_system_info()

        self.assertEqual(result.memory.total_bytes, 0)
        self.assertEqual(result.memory.available_bytes, 0)
        self.assertEqual(result.memory.used_bytes, 0)


if __name__ == "__main__":
    unittest.main()
