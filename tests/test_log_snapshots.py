from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from mcp_linux_diag_server.tools.log_snapshots import (
    LOG_SOURCE_CANDIDATES,
    clear_log_snapshots,
    create_log_snapshot,
    get_log_snapshot_page,
    render_log_snapshot_resource,
)


class LogSnapshotTests(unittest.TestCase):
    def setUp(self) -> None:
        clear_log_snapshots()

    def tearDown(self) -> None:
        clear_log_snapshots()

    def create_log_file(self, *lines: str) -> Path:
        temp_dir = tempfile.TemporaryDirectory()
        self.addCleanup(temp_dir.cleanup)
        log_path = Path(temp_dir.name) / "system.log"
        log_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
        return log_path

    def test_create_snapshot_uses_first_available_log_and_builds_resource_uris(self) -> None:
        log_path = self.create_log_file("ok", "warning", "error")
        with patch.dict(LOG_SOURCE_CANDIDATES, {"system": (log_path,)}, clear=True):
            snapshot = create_log_snapshot()

        self.assertEqual(snapshot.log_name, "system")
        self.assertEqual(snapshot.source_path, str(log_path))
        self.assertEqual(snapshot.line_count, 3)
        self.assertEqual(snapshot.resource_uri, f"syslog://snapshot/{snapshot.snapshot_id}")
        self.assertIn("limit={limit}", snapshot.paginated_resource_template)

    def test_create_snapshot_applies_case_insensitive_filter_and_line_limit(self) -> None:
        log_path = self.create_log_file("info start", "ERROR first", "debug", "error second")
        with patch.dict(LOG_SOURCE_CANDIDATES, {"system": (log_path,)}, clear=True):
            snapshot = create_log_snapshot("system", filter_text="Error", max_lines=1)

        page = get_log_snapshot_page(snapshot.snapshot_id)
        self.assertEqual(page.line_count, 1)
        self.assertEqual(page.lines[0].text, "error second")

    def test_paged_resource_includes_pagination_metadata(self) -> None:
        log_path = self.create_log_file("line 1", "line 2", "line 3")
        with patch.dict(LOG_SOURCE_CANDIDATES, {"system": (log_path,)}, clear=True):
            snapshot = create_log_snapshot("system", max_lines=10)

        page = get_log_snapshot_page(snapshot.snapshot_id, limit=2, offset=1)

        self.assertEqual(page.pagination.total_count, 3)
        self.assertEqual(page.pagination.returned_count, 2)
        self.assertEqual(page.pagination.limit, 2)
        self.assertEqual(page.pagination.offset, 1)
        self.assertFalse(page.pagination.has_more)
        self.assertIsNone(page.pagination.next_offset)

    def test_render_resource_returns_json_text(self) -> None:
        log_path = self.create_log_file("alpha", "beta")
        with patch.dict(LOG_SOURCE_CANDIDATES, {"system": (log_path,)}, clear=True):
            snapshot = create_log_snapshot("system")

        rendered = render_log_snapshot_resource(snapshot.snapshot_id, limit=1, offset=0)

        self.assertIn('"snapshot_id"', rendered)
        self.assertIn('"pagination"', rendered)

    def test_unknown_snapshot_raises_clear_error(self) -> None:
        with self.assertRaisesRegex(ValueError, "No log snapshot found"):
            get_log_snapshot_page("missing")


if __name__ == "__main__":
    unittest.main()
