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
            if "get_system_info" not in tool_names:
                raise RuntimeError("get_system_info tool was not advertised by the server")

            result = await session.call_tool("get_system_info", {})
            if result.isError:
                raise RuntimeError(f"Tool call failed: {result.content}")

            return {
                "tools": tool_names,
                "system_info": result.structuredContent,
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
