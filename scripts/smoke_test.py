from __future__ import annotations

import asyncio
import json
import os
import subprocess
import sys
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(REPO_ROOT / "src"))


async def run_server_smoke() -> dict[str, object]:
    env = dict(os.environ)
    env["PYTHONPATH"] = (
        f"{REPO_ROOT / 'src'}:{env['PYTHONPATH']}"
        if env.get("PYTHONPATH")
        else str(REPO_ROOT / "src")
    )
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "mcp_linux_diag_server"],
        cwd=REPO_ROOT,
        env=env,
    )

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            tools = await session.list_tools()
            tool_names = [tool.name for tool in tools.tools]
            expected_tools = {
                "get_system_info",
                "get_process_list",
                "get_process_by_id",
                "get_process_by_name",
                "create_log_snapshot",
            }
            if not expected_tools.issubset(tool_names):
                missing_tools = sorted(expected_tools - set(tool_names))
                raise RuntimeError(f"Expected tools were not advertised by the server: {missing_tools}")

            prompts = await session.list_prompts()
            prompt_names = {prompt.name for prompt in prompts.prompts}
            expected_prompts = {
                "AnalyzeRecentApplicationErrors",
                "ExplainHighCpu",
                "DetectSecurityAnomalies",
                "DiagnoseSystemHealth",
            }
            if prompt_names != expected_prompts:
                raise RuntimeError(f"Expected prompts were not advertised by the server: {sorted(expected_prompts - prompt_names)}")

            resource_templates = await session.list_resource_templates()
            template_uris = {template.uriTemplate for template in resource_templates.resourceTemplates}
            expected_templates = {
                "syslog://snapshot/{snapshot_id}",
                "syslog://snapshot/{snapshot_id}?limit={limit}&offset={offset}",
            }
            if not expected_templates.issubset(template_uris):
                raise RuntimeError(f"Expected resource templates were not advertised by the server: {sorted(expected_templates - template_uris)}")

            system_result = await session.call_tool("get_system_info", {})
            if system_result.isError:
                raise RuntimeError(f"Tool call failed: {system_result.content}")

            process_list_result = await session.call_tool("get_process_list", {})
            if process_list_result.isError:
                raise RuntimeError(f"Process list tool failed: {process_list_result.content}")

            process_list = process_list_result.structuredContent
            if isinstance(process_list, dict) and "result" in process_list:
                process_list = process_list["result"]
            if not isinstance(process_list, list) or not process_list:
                raise RuntimeError("Expected get_process_list to return at least one process")

            process_detail = None
            process_page = None
            for process_entry in process_list[:10]:
                process_id = process_entry["process_id"]
                process_name = process_entry["process_name"]

                process_detail_result = await session.call_tool("get_process_by_id", {"process_id": process_id})
                if process_detail_result.isError:
                    continue

                process_page_result = await session.call_tool("get_process_by_name", {"process_name": process_name})
                if process_page_result.isError:
                    continue

                process_detail = process_detail_result.structuredContent
                process_page = process_page_result.structuredContent
                break

            if process_detail is None or process_page is None:
                raise RuntimeError("Unable to complete live process detail smoke calls")

            snapshot_result = await session.call_tool("create_log_snapshot", {"filter_text": "error", "max_lines": 25})
            if snapshot_result.isError:
                raise RuntimeError(f"Log snapshot tool failed: {snapshot_result.content}")

            snapshot_payload = snapshot_result.structuredContent
            if not isinstance(snapshot_payload, dict) or "resource_uri" not in snapshot_payload:
                raise RuntimeError("Expected create_log_snapshot to return a resource URI")

            prompt_result = await session.get_prompt("DiagnoseSystemHealth", {"search_text": "error"})
            if not prompt_result.messages:
                raise RuntimeError("Expected DiagnoseSystemHealth prompt to return at least one message")

            resource_result = await session.read_resource(snapshot_payload["resource_uri"])
            rendered_snapshot = resource_result.contents[0].text
            if '"pagination"' not in rendered_snapshot:
                raise RuntimeError("Expected log snapshot resource to include pagination metadata")

            return {
                "tools": tool_names,
                "prompts": sorted(prompt_names),
                "resource_templates": sorted(template_uris),
                "system_info": system_result.structuredContent,
                "process_sample": process_detail,
                "process_page": process_page,
                "log_snapshot": snapshot_payload,
            }


def run_agent_smoke() -> dict[str, object]:
    env = {
        key: value
        for key, value in os.environ.items()
        if not key.startswith("AZURE_OPENAI_") and not key.startswith("MCP_DEMO_AZURE_OPENAI_")
    }
    env["PYTHONPATH"] = (
        f"{REPO_ROOT / 'src'}:{env['PYTHONPATH']}"
        if env.get("PYTHONPATH")
        else str(REPO_ROOT / "src")
    )

    result = subprocess.run(
        [sys.executable, "-m", "mcp_linux_diag_server.client", "--no-local-env", "--prompt", "Summarize this machine."],
        cwd=REPO_ROOT,
        env=env,
        capture_output=True,
        text=True,
        check=False,
    )

    if result.returncode != 2:
        raise RuntimeError(
            "Expected the agent smoke to fail fast without Azure configuration, "
            f"but exit code was {result.returncode}."
        )
    if "Missing Azure OpenAI settings" not in result.stderr:
        raise RuntimeError(f"Unexpected agent failure output: {result.stderr.strip()}")

    return {
        "exit_code": result.returncode,
        "stderr": result.stderr.strip(),
    }


def main() -> None:
    server_payload = asyncio.run(run_server_smoke())
    print(json.dumps({"server": server_payload}, indent=2, sort_keys=True))
    agent_payload = run_agent_smoke()
    print(json.dumps({"agent": agent_payload}, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
