from __future__ import annotations

import asyncio
import json
import re
import unittest
from pathlib import Path

import mcp.types as types

from tests.http_harness import open_session, running_server

_ALLOWED_PATH = "/proc/meminfo"
_DYNAMIC_ACCESS_CANDIDATES = (
    "/proc/filesystems",
    "/proc/modules",
    "/sys/devices/system/cpu/possible",
)
_UNSAFE_PATHS = (
    "/proc/../etc/passwd",
    "/proc/self/root/etc/passwd",
    "/proc/meminfo;cat_/etc/passwd",
)


class M7RootsAndSnapshotsTests(unittest.TestCase):
    def run_with_session(self, assertion, *, elicitation_callback=None):  # noqa: ANN001, ANN201
        async def runner() -> None:
            with running_server() as (host, port, _process):
                async with open_session(host=host, port=port, elicitation_callback=elicitation_callback) as (
                    session,
                    initialize_result,
                    _session_id,
                ):
                    await assertion(session, initialize_result)

        asyncio.run(runner())

    def test_server_advertises_m7_tools_templates_and_prior_surfaces(self) -> None:
        async def assertion(session, initialize_result):  # noqa: ANN001
            self.assertEqual(initialize_result.serverInfo.name, "Linux Diagnostics Demo")

            tools = await session.list_tools()
            tool_names = {tool.name for tool in tools.tools}
            self.assertTrue(
                {
                    "get_system_info",
                    "get_process_list",
                    "get_process_by_id",
                    "get_process_by_name",
                    "create_log_snapshot",
                    "kill_process",
                    "troubleshoot_linux_diagnostics",
                    "create_proc_snapshot",
                    "request_proc_access",
                }.issubset(tool_names)
            )

            prompts = await session.list_prompts()
            self.assertTrue(
                {
                    "AnalyzeRecentApplicationErrors",
                    "ExplainHighCpu",
                    "DetectSecurityAnomalies",
                    "DiagnoseSystemHealth",
                    "TroubleshootLinuxComponent",
                }.issubset({prompt.name for prompt in prompts.prompts})
            )

            templates = await session.list_resource_templates()
            template_uris = {template.uriTemplate for template in templates.resourceTemplates}
            self.assertIn("syslog://snapshot/{snapshot_id}", template_uris)
            self.assertIn("syslog://snapshot/{snapshot_id}?limit={limit}&offset={offset}", template_uris)
            self.assertTrue(any(re.fullmatch(r"proc://snapshot/\{[^}]+\}", uri) for uri in template_uris))
            self.assertTrue(
                any(
                    re.fullmatch(r"proc://snapshot/\{[^}]+\}\?limit=\{limit\}&offset=\{offset\}", uri)
                    for uri in template_uris
                )
            )

        self.run_with_session(assertion)

    def test_create_proc_snapshot_reads_allowlisted_path_and_supports_paging(self) -> None:
        async def assertion(session, _initialize_result):  # noqa: ANN001
            snapshot_result = await session.call_tool("create_proc_snapshot", {"path": _ALLOWED_PATH})
            self.assertFalse(
                snapshot_result.isError,
                f"create_proc_snapshot should succeed for {_ALLOWED_PATH}: {_tool_text(snapshot_result)}",
            )

            payload = snapshot_result.structuredContent
            resource_uri = _extract_resource_uri(snapshot_result)
            self.assertTrue(resource_uri.startswith("proc://snapshot/"))
            if isinstance(payload, dict) and "paginated_resource_template" in payload:
                self.assertIn("limit={limit}", str(payload["paginated_resource_template"]))

            resource_result = await session.read_resource(resource_uri)
            rendered = resource_result.contents[0].text
            parsed = json.loads(rendered)
            self.assertIn("pagination", parsed)
            self.assertEqual(parsed.get("path"), _ALLOWED_PATH)
            self.assertGreater(parsed["pagination"].get("total_count", 0), 0)

            page_result = await session.read_resource(f"{resource_uri}?limit=2&offset=0")
            page_text = page_result.contents[0].text
            self.assertIn('"pagination"', page_text)
            self.assertIn(_ALLOWED_PATH, page_text)

        self.run_with_session(assertion)

    def test_create_proc_snapshot_blocks_paths_outside_allowed_roots(self) -> None:
        async def assertion(session, _initialize_result):  # noqa: ANN001
            result = await session.call_tool("create_proc_snapshot", {"path": "/etc/passwd"})
            self.assertTrue(result.isError)
            message = _tool_text(result).lower()
            _fail_if_tool_missing(self, "create_proc_snapshot", message)
            self.assertTrue("allow" in message or "access" in message)

        self.run_with_session(assertion)

    def test_request_proc_access_allows_snapshot_after_approval(self) -> None:
        access_path = _pick_dynamic_access_path()

        async def assertion(session, _initialize_result):  # noqa: ANN001
            blocked = await session.call_tool("create_proc_snapshot", {"path": access_path})
            self.assertTrue(blocked.isError)
            _fail_if_tool_missing(self, "create_proc_snapshot", _tool_text(blocked))

            approved = await session.call_tool(
                "request_proc_access",
                {"path": access_path, "reason": "QA validation for milestone 7 access flow"},
            )
            self.assertFalse(
                approved.isError,
                f"request_proc_access should approve {access_path}: {_tool_text(approved)}",
            )

            snapshot_result = await session.call_tool("create_proc_snapshot", {"path": access_path})
            self.assertFalse(
                snapshot_result.isError,
                f"create_proc_snapshot should succeed after access approval for {access_path}: {_tool_text(snapshot_result)}",
            )
            resource_result = await session.read_resource(_extract_resource_uri(snapshot_result))
            self.assertIn(access_path, resource_result.contents[0].text)

        self.run_with_session(assertion, elicitation_callback=_approval_callback_for(access_path))

    def test_create_proc_snapshot_rejects_obvious_escape_attempts(self) -> None:
        async def assertion(session, _initialize_result):  # noqa: ANN001
            for path in _UNSAFE_PATHS:
                with self.subTest(path=path):
                    result = await session.call_tool("create_proc_snapshot", {"path": path})
                    self.assertTrue(result.isError)
                    message = _tool_text(result).lower()
                    _fail_if_tool_missing(self, "create_proc_snapshot", message)
                    self.assertTrue(
                        any(token in message for token in ("allow", "access", "travers", "symlink", "unsafe", "forbidden"))
                    )

        self.run_with_session(assertion)


def _pick_dynamic_access_path() -> str:
    for candidate in _DYNAMIC_ACCESS_CANDIDATES:
        if Path(candidate).is_file():
            return candidate
    raise unittest.SkipTest("No readable out-of-roots proc/sys file exists on this host for M7 access testing.")


def _approval_callback_for(expected_path: str):
    async def callback(_context, params):  # noqa: ANN001, ANN202
        requested_schema = getattr(params, "requestedSchema", None) or {}
        properties = requested_schema.get("properties") if isinstance(requested_schema, dict) else None
        if not isinstance(properties, dict) or len(properties) != 1:
            raise AssertionError(f"Unsupported elicitation schema: {requested_schema!r}")

        field_name, field_schema = next(iter(properties.items()))
        if not isinstance(field_schema, dict):
            raise AssertionError(f"Unsupported elicitation field schema: {field_schema!r}")

        value = _resolve_elicitation_value(field_name, field_schema, expected_path)
        return types.ElicitResult(action="accept", content={field_name: value})

    return callback


def _resolve_elicitation_value(field_name: str, field_schema: dict[str, object], expected_path: str) -> object:
    one_of = field_schema.get("oneOf")
    if isinstance(one_of, list):
        for option in one_of:
            if isinstance(option, dict) and str(option.get("const")) == expected_path:
                return expected_path
        for option in one_of:
            if isinstance(option, dict) and "const" in option:
                return option["const"]

    enum_values = field_schema.get("enum")
    if isinstance(enum_values, list) and enum_values:
        if expected_path in enum_values:
            return expected_path
        return enum_values[0]

    if field_schema.get("type") == "boolean":
        return True

    description = " ".join(
        str(part)
        for part in (
            field_name,
            field_schema.get("title"),
            field_schema.get("description"),
        )
        if part
    )
    phrase_match = re.search(r"['\"]([^'\"]+)['\"]", description)
    if phrase_match and "confirm" in description.lower():
        return phrase_match.group(1)
    if "path" in description.lower() or "root" in description.lower():
        return expected_path
    if "reason" in description.lower():
        return "QA validation for milestone 7 access flow"
    return "approve"


def _extract_resource_uri(result) -> str:  # noqa: ANN001, ANN201
    payload = result.structuredContent
    if isinstance(payload, dict):
        resource_uri = payload.get("resource_uri")
        if isinstance(resource_uri, str):
            return resource_uri
    for item in result.content:
        if hasattr(item, "text") and isinstance(item.text, str) and item.text.startswith("proc://snapshot/"):
            return item.text
    raise AssertionError(f"Expected proc snapshot URI in tool result, got: {result}")


def _tool_text(result) -> str:  # noqa: ANN001, ANN201
    return "\n".join(item.text for item in result.content if hasattr(item, "text"))


def _fail_if_tool_missing(test_case: unittest.TestCase, tool_name: str, message: str) -> None:
    lowered = message.lower()
    if any(token in lowered for token in ("unknown tool", "method not found", "unknown method", "does not exist")):
        test_case.fail(f"{tool_name} is not implemented or not advertised yet: {message}")
    if tool_name.lower() in lowered and "not found" in lowered:
        test_case.fail(f"{tool_name} is not implemented or not advertised yet: {message}")


if __name__ == "__main__":
    unittest.main()
