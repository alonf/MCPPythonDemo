"""Interactive lecture chat client for the Milestone 1 MCP server."""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Protocol

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from mcp.types import CallToolResult, TextContent, Tool

DEFAULT_DEPLOYMENT = "model-router"
DEFAULT_API_VERSION = "2024-10-21"
DEFAULT_ENV_FILE_NAME = ".env.local"
DEFAULT_SYSTEM_PROMPT = (
    "You are a helpful Linux diagnostics assistant. "
    "You can call MCP tools that inspect the current Linux or WSL machine. "
    "When the user asks about the system, use get_system_info before answering. "
    "When the user asks about processes, list them first and then use get_process_by_id "
    "or get_process_by_name for detail. "
    "Keep answers concise, practical, and grounded in tool results."
)
AZURE_OPENAI_SCOPE = "https://cognitiveservices.azure.com/.default"


class ClientConfigurationError(RuntimeError):
    """Raised when the lecture chat client cannot start safely."""


@dataclass(slots=True)
class ChatConfig:
    """Runtime settings for the lecture chat client."""

    endpoint: str
    api_key: str | None = None
    deployment: str = DEFAULT_DEPLOYMENT
    api_version: str = DEFAULT_API_VERSION
    system_prompt: str = DEFAULT_SYSTEM_PROMPT
    use_default_credential: bool = False

    @classmethod
    def from_sources(
        cls,
        *,
        endpoint: str | None = None,
        api_key: str | None = None,
        deployment: str | None = None,
        api_version: str | None = None,
        system_prompt: str | None = None,
        environ: Mapping[str, str] | None = None,
        env_file: str | None = None,
        use_local_env: bool = True,
    ) -> ChatConfig:
        """Build configuration from CLI overrides plus environment variables."""
        env = os.environ if environ is None else environ
        resolved_env_file = None
        if env_file is not None or environ is None:
            resolved_env_file = resolve_env_file(env_file=env_file, environ=env, use_local_env=use_local_env)
        file_values = load_local_env_file(resolved_env_file)
        resolved_endpoint = (
            endpoint
            or env.get("MCP_DEMO_AZURE_OPENAI_ENDPOINT")
            or env.get("AZURE_OPENAI_ENDPOINT")
            or file_values.get("MCP_DEMO_AZURE_OPENAI_ENDPOINT")
            or file_values.get("AZURE_OPENAI_ENDPOINT")
        )
        resolved_api_key = (
            api_key
            or env.get("MCP_DEMO_AZURE_OPENAI_API_KEY")
            or env.get("AZURE_OPENAI_API_KEY")
            or file_values.get("MCP_DEMO_AZURE_OPENAI_API_KEY")
            or file_values.get("AZURE_OPENAI_API_KEY")
        )
        resolved_deployment = (
            deployment
            or env.get("MCP_DEMO_AZURE_OPENAI_DEPLOYMENT")
            or env.get("AZURE_OPENAI_DEPLOYMENT")
            or file_values.get("MCP_DEMO_AZURE_OPENAI_DEPLOYMENT")
            or file_values.get("AZURE_OPENAI_DEPLOYMENT")
            or DEFAULT_DEPLOYMENT
        )
        resolved_api_version = (
            api_version
            or env.get("MCP_DEMO_AZURE_OPENAI_API_VERSION")
            or env.get("OPENAI_API_VERSION")
            or file_values.get("MCP_DEMO_AZURE_OPENAI_API_VERSION")
            or file_values.get("OPENAI_API_VERSION")
            or DEFAULT_API_VERSION
        )
        resolved_system_prompt = (
            system_prompt
            or env.get("MCP_DEMO_SYSTEM_PROMPT")
            or file_values.get("MCP_DEMO_SYSTEM_PROMPT")
            or DEFAULT_SYSTEM_PROMPT
        )
        resolved_use_default_credential = _parse_bool(
            env.get("MCP_DEMO_AZURE_OPENAI_USE_DEFAULT_CREDENTIAL")
            or file_values.get("MCP_DEMO_AZURE_OPENAI_USE_DEFAULT_CREDENTIAL")
        )

        missing: list[str] = []
        if not resolved_endpoint:
            missing.append("MCP_DEMO_AZURE_OPENAI_ENDPOINT")
        if not resolved_api_key and not resolved_use_default_credential:
            missing.append("MCP_DEMO_AZURE_OPENAI_API_KEY")

        if missing:
            joined = ", ".join(missing)
            raise ClientConfigurationError(
                f"Missing Azure OpenAI settings: {joined}. "
                "Set them in your environment, place them in .env.local, "
                "or pass the matching CLI flags."
            )

        return cls(
            endpoint=resolved_endpoint,
            api_key=resolved_api_key,
            deployment=resolved_deployment,
            api_version=resolved_api_version,
            system_prompt=resolved_system_prompt,
            use_default_credential=resolved_use_default_credential,
        )


def _parse_bool(value: str | None) -> bool:
    return (value or "").strip().lower() in {"1", "true", "yes", "on"}


def load_local_env_file(path: str | Path | None) -> dict[str, str]:
    """Read simple KEY=VALUE pairs from a local env file."""
    if path is None:
        return {}

    env_path = Path(path)
    if not env_path.exists():
        return {}

    loaded: dict[str, str] = {}
    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        resolved = value.strip()
        if len(resolved) >= 2 and resolved[0] == resolved[-1] and resolved[0] in {"'", '"'}:
            resolved = resolved[1:-1]
        loaded[key.strip()] = resolved

    return loaded


def resolve_env_file(
    *,
    env_file: str | None = None,
    environ: Mapping[str, str] | None = None,
    use_local_env: bool = True,
) -> Path | None:
    """Resolve which local env file, if any, should be loaded."""
    if not use_local_env:
        return None

    env = os.environ if environ is None else environ
    candidate = env_file or env.get("MCP_DEMO_ENV_FILE")
    if candidate:
        return Path(candidate)

    return Path.cwd() / DEFAULT_ENV_FILE_NAME

@dataclass(slots=True)
class ToolCallRequest:
    """Simple tool call payload used by the agent loop."""

    id: str
    name: str
    arguments: dict[str, Any]


@dataclass(slots=True)
class AssistantTurn:
    """Minimal assistant turn model for tool-calling loops."""

    content: str
    tool_calls: list[ToolCallRequest]


class ChatModel(Protocol):
    """Small protocol for testable chat-completion backends."""

    def complete(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> AssistantTurn:
        """Return the next assistant turn."""


class AzureOpenAIChatModel:
    """Azure OpenAI-backed chat model with tool-calling support."""

    def __init__(self, config: ChatConfig) -> None:
        try:
            from openai import AzureOpenAI
        except ImportError as exc:  # pragma: no cover - import path only matters when configured
            raise ClientConfigurationError(
                "The lecture chat client requires the OpenAI dependency. "
                "Install it with: python3 -m pip install --user --break-system-packages -e '.[llm]'"
            ) from exc

        client_kwargs: dict[str, Any] = {
            "azure_endpoint": config.endpoint,
            "api_version": config.api_version,
        }
        if config.use_default_credential:
            try:
                from azure.identity import DefaultAzureCredential, get_bearer_token_provider
            except ImportError as exc:  # pragma: no cover - import path only matters when configured
                raise ClientConfigurationError(
                    "DefaultAzureCredential support requires azure-identity. "
                    "Install it with: python3 -m pip install --user --break-system-packages -e '.[llm]'"
                ) from exc

            credential = DefaultAzureCredential()
            client_kwargs["azure_ad_token_provider"] = get_bearer_token_provider(credential, AZURE_OPENAI_SCOPE)
        else:
            client_kwargs["api_key"] = config.api_key

        self._client = AzureOpenAI(**client_kwargs)
        self._deployment = config.deployment

    def complete(self, messages: list[dict[str, Any]], tools: list[dict[str, Any]]) -> AssistantTurn:
        response = self._client.chat.completions.create(
            model=self._deployment,
            messages=messages,
            tools=tools,
        )
        message = response.choices[0].message
        tool_calls: list[ToolCallRequest] = []

        for tool_call in message.tool_calls or []:
            raw_arguments = tool_call.function.arguments or "{}"
            try:
                arguments = json.loads(raw_arguments)
            except json.JSONDecodeError as exc:
                raise RuntimeError(
                    f"Model returned invalid JSON for tool '{tool_call.function.name}': {raw_arguments}"
                ) from exc

            tool_calls.append(
                ToolCallRequest(
                    id=tool_call.id,
                    name=tool_call.function.name,
                    arguments=arguments,
                )
            )

        return AssistantTurn(
            content=message.content or "",
            tool_calls=tool_calls,
        )


def build_openai_tools(mcp_tools: list[Tool]) -> list[dict[str, Any]]:
    """Translate advertised MCP tools to Azure OpenAI function definitions."""
    return [
        {
            "type": "function",
            "function": {
                "name": tool.name,
                "description": tool.description or tool.title or tool.name,
                "parameters": tool.inputSchema or {"type": "object", "properties": {}},
            },
        }
        for tool in mcp_tools
    ]


def assistant_turn_to_message(turn: AssistantTurn) -> dict[str, Any]:
    """Convert a simplified assistant turn back to an OpenAI chat message."""
    message: dict[str, Any] = {"role": "assistant", "content": turn.content}
    if turn.tool_calls:
        message["tool_calls"] = [
            {
                "id": tool_call.id,
                "type": "function",
                "function": {
                    "name": tool_call.name,
                    "arguments": json.dumps(tool_call.arguments),
                },
            }
            for tool_call in turn.tool_calls
        ]
    return message


def serialize_tool_result(result: CallToolResult) -> str:
    """Prefer structured content so the model gets JSON instead of free-form text."""
    if result.structuredContent is not None:
        return json.dumps(result.structuredContent, indent=2, sort_keys=True)

    text_fragments = [item.text for item in result.content if isinstance(item, TextContent)]
    if text_fragments:
        return "\n".join(text_fragments)

    return json.dumps(result.model_dump(mode="json"), indent=2, sort_keys=True)


async def run_agent_turn(
    *,
    session: ClientSession,
    model: ChatModel,
    messages: list[dict[str, Any]],
    tools: list[dict[str, Any]],
    max_steps: int = 6,
    emit_trace: bool = True,
) -> str:
    """Run one user turn, allowing the model to call MCP tools until it answers."""
    for _ in range(max_steps):
        assistant_turn = await asyncio.to_thread(model.complete, messages, tools)
        messages.append(assistant_turn_to_message(assistant_turn))

        if not assistant_turn.tool_calls:
            return assistant_turn.content or "(No text returned.)"

        for tool_call in assistant_turn.tool_calls:
            if emit_trace:
                print(f"[tool] {tool_call.name}({json.dumps(tool_call.arguments, sort_keys=True)})")
            result = await session.call_tool(tool_call.name, tool_call.arguments)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": serialize_tool_result(result),
                }
            )

    raise RuntimeError("The model did not finish within the tool-call limit.")


async def run_single_prompt(
    *,
    config: ChatConfig,
    prompt: str,
    server_module: str = "mcp_linux_diag_server",
    emit_trace: bool = False,
) -> dict[str, Any]:
    """Run one prompt and return a structured result for scripts or tests."""
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", server_module],
    )
    model = AzureOpenAIChatModel(config)

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tool_list = await session.list_tools()
            mcp_tools = tool_list.tools
            messages: list[dict[str, Any]] = [
                {"role": "system", "content": config.system_prompt},
                {"role": "user", "content": prompt},
            ]
            answer = await run_agent_turn(
                session=session,
                model=model,
                messages=messages,
                tools=build_openai_tools(mcp_tools),
                emit_trace=emit_trace,
            )
            return {
                "question": prompt,
                "answer": answer,
                "tools": [tool.name for tool in mcp_tools],
            }


async def run_chat(
    *,
    config: ChatConfig,
    initial_prompt: str | None = None,
    server_module: str = "mcp_linux_diag_server",
    as_json: bool = False,
) -> None:
    """Start the MCP server, connect to it, and run the chat loop."""
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", server_module],
    )
    model = AzureOpenAIChatModel(config)

    async with stdio_client(server_params) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()
            tool_list = await session.list_tools()
            mcp_tools = tool_list.tools
            tool_names = ", ".join(tool.name for tool in mcp_tools) or "(none)"
            print(f"Connected to MCP server. Tools: {tool_names}")

            messages: list[dict[str, Any]] = [{"role": "system", "content": config.system_prompt}]
            openai_tools = build_openai_tools(mcp_tools)

            pending_prompt = initial_prompt
            while True:
                if pending_prompt is None:
                    try:
                        user_input = input("User: ").strip()
                    except EOFError:
                        print()
                        return
                else:
                    user_input = pending_prompt.strip()
                    print(f"User: {user_input}")

                if not user_input:
                    if pending_prompt is None:
                        continue
                    return

                if user_input.lower() in {"exit", "quit"}:
                    return

                messages.append({"role": "user", "content": user_input})
                answer = await run_agent_turn(
                    session=session,
                    model=model,
                    messages=messages,
                    tools=openai_tools,
                    emit_trace=True,
                )

                if as_json:
                    print(
                        json.dumps(
                            {
                                "question": user_input,
                                "answer": answer,
                            },
                            indent=2,
                            sort_keys=True,
                        )
                    )
                else:
                    print(f"Assistant: {answer}")

                if pending_prompt is not None:
                    return
                pending_prompt = None


def build_parser() -> argparse.ArgumentParser:
    """Create the CLI parser for the lecture chat client."""
    parser = argparse.ArgumentParser(description="Run the Milestone 1 Azure OpenAI chat client.")
    parser.add_argument("question", nargs="?", help="Optional single prompt to run instead of interactive mode.")
    parser.add_argument("--prompt", help="Alias for the positional question argument.")
    parser.add_argument("--json", action="store_true", help="Emit single-prompt output as JSON.")
    parser.add_argument(
        "--env-file",
        help=f"Optional local env file to load before defaults. Defaults to ./{DEFAULT_ENV_FILE_NAME} when present.",
    )
    parser.add_argument(
        "--no-local-env",
        action="store_true",
        help="Disable automatic loading of a local env file.",
    )
    parser.add_argument("--endpoint", help="Azure OpenAI endpoint. Defaults to MCP_DEMO_AZURE_OPENAI_ENDPOINT.")
    parser.add_argument("--api-key", help="Azure OpenAI API key. Defaults to MCP_DEMO_AZURE_OPENAI_API_KEY.")
    parser.add_argument(
        "--deployment",
        help=f"Azure OpenAI deployment name. Defaults to MCP_DEMO_AZURE_OPENAI_DEPLOYMENT or {DEFAULT_DEPLOYMENT}.",
    )
    parser.add_argument(
        "--api-version",
        help=f"Azure OpenAI API version. Defaults to MCP_DEMO_AZURE_OPENAI_API_VERSION or {DEFAULT_API_VERSION}.",
    )
    parser.add_argument(
        "--system-prompt",
        help="Optional override for the agent system prompt.",
    )
    parser.add_argument(
        "--server-module",
        default="mcp_linux_diag_server",
        help="Python module to launch for the MCP server.",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint."""
    parser = build_parser()
    args = parser.parse_args(argv)

    try:
        config = ChatConfig.from_sources(
            endpoint=args.endpoint,
            api_key=args.api_key,
            deployment=args.deployment,
            api_version=args.api_version,
            system_prompt=args.system_prompt,
            env_file=args.env_file,
            use_local_env=not args.no_local_env,
        )
    except ClientConfigurationError as exc:
        print(str(exc), file=sys.stderr)
        return 2

    prompt = args.prompt or args.question

    print("Linux Diagnostics MCP Chat Client")
    print("Type 'exit' to quit.")
    try:
        asyncio.run(
            run_chat(
                config=config,
                initial_prompt=prompt,
                server_module=args.server_module,
                as_json=args.json,
            )
        )
    except Exception as exc:  # pragma: no cover - CLI guardrail
        print(f"Diagnostics chat client failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
