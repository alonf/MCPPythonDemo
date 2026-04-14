from __future__ import annotations

import json
import unittest
from pathlib import Path

from mcp_linux_diag_server.tools.proc_snapshots import (
    ProcRootsService,
    clear_proc_snapshots,
    create_proc_snapshot,
    get_proc_snapshot_page,
    render_proc_snapshot_resource,
    reset_proc_roots,
    validate_proc_snapshot_path,
)


class ProcSnapshotTests(unittest.TestCase):
    def setUp(self) -> None:
        clear_proc_snapshots()
        reset_proc_roots()

    def tearDown(self) -> None:
        clear_proc_snapshots()
        reset_proc_roots()

    def test_create_proc_snapshot_builds_resource_uris_for_allowed_file(self) -> None:
        snapshot = create_proc_snapshot("/proc/meminfo")

        self.assertEqual(snapshot.path, "/proc/meminfo")
        self.assertTrue(snapshot.resource_uri.startswith("proc://snapshot/"))
        self.assertIn("limit={limit}", snapshot.paginated_resource_template)
        self.assertGreater(snapshot.entry_count, 0)

    def test_proc_snapshot_page_includes_pagination_metadata(self) -> None:
        snapshot = create_proc_snapshot("/proc/meminfo")

        page = get_proc_snapshot_page(snapshot.snapshot_id, limit=2, offset=0)

        self.assertEqual(page.path, "/proc/meminfo")
        self.assertEqual(page.pagination.limit, 2)
        self.assertEqual(page.pagination.offset, 0)
        self.assertEqual(page.pagination.returned_count, len(page.entries))
        self.assertGreater(page.pagination.total_count, 0)

    def test_render_proc_snapshot_resource_returns_json_text(self) -> None:
        snapshot = create_proc_snapshot("/proc/meminfo")

        rendered = render_proc_snapshot_resource(snapshot.snapshot_id, limit=1, offset=0)

        parsed = json.loads(rendered)
        self.assertEqual(parsed["path"], "/proc/meminfo")
        self.assertIn("pagination", parsed)

    def test_validate_proc_snapshot_path_rejects_supported_but_blocked_path(self) -> None:
        blocked_candidate = next(
            (candidate for candidate in ("/proc/filesystems", "/proc/modules") if Path(candidate).is_file()),
            None,
        )
        if blocked_candidate is None:
            self.skipTest("No blocked proc candidate exists on this host.")

        with self.assertRaisesRegex(ValueError, "request_proc_access"):
            validate_proc_snapshot_path(blocked_candidate)

    def test_validate_proc_snapshot_path_rejects_forbidden_path_even_without_allowlist_check(self) -> None:
        with self.assertRaisesRegex(ValueError, "forbidden"):
            validate_proc_snapshot_path("/proc/kcore", require_allowed_root=False)

    def test_adding_forbidden_root_is_rejected(self) -> None:
        with self.assertRaisesRegex(ValueError, "forbidden"):
            ProcRootsService.instance().add_allowed_root("/proc/kcore")

    def test_adding_root_unblocks_supported_path(self) -> None:
        candidate = next(
            (value for value in ("/proc/filesystems", "/proc/modules") if Path(value).is_file()),
            None,
        )
        if candidate is None:
            self.skipTest("No blocked proc candidate exists on this host.")

        ProcRootsService.instance().add_allowed_root(candidate)
        validated = validate_proc_snapshot_path(candidate)

        self.assertEqual(validated["normalized_path"], candidate)
        self.assertEqual(validated["matched_allowed_root"], candidate)


if __name__ == "__main__":
    unittest.main()
