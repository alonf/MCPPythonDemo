"""Interactive lecture chat client for the Milestone 6 MCP server."""

from __future__ import annotations

import argparse
import asyncio
from contextlib import asynccontextmanager
import json
import os
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Protocol

import httpx
from mcp import ClientSession
from mcp.client.streamable_http import streamable_http_client
import mcp.types as types
from mcp.types import CallToolResult, CreateMessageRequestParams, ElicitRequestParams, TextContent, Tool

from mcp_linux_diag_server.http_config import API_KEY_HEADER, DEFAULT_HTTP_HOST, DEFAULT_HTTP_PORT, DEMO_API_KEY, build_mcp_url

DEFAULT_DEPLOYMENT = "model-router"
DEFAULT_API_VERSION = "2024-10-21"
DEFAULT_ENV_FILE_NAME = ".env.local"
DEFAULT_SYSTEM_PROMPT = (
    "You are a helpful Linux diagnostics assistant. "
    "You can call MCP tools that inspect the current Linux or WSL machine. "
    "When the user asks about the system, use get_system_info before answering. "
    "When the user asks about processes, list them first and then use get_process_by_id "
    "or get_process_by_name for detail. "
    "When the user asks for deeper kernel, memory, CPU, or /proc-/sys-oriented troubleshooting, "
    "prefer troubleshoot_linux_diagnostics over a broad health summary. "
    "If the user wants to terminate a process, use kill_process and let the server drive "
    "the confirmation workflow. Never invent a PID when the user wants to choose interactively. "
    "When you need a guided workflow, call list_prompts and then get_prompt. "
    "When a tool returns a resource URI, call read_resource to inspect it, and use "
    "list_resource_templates to learn the pagination pattern. "
    "Keep answers concise, practical, and grounded in tool results."
)
AZURE_OPENAI_SCOPE = "https://cognitiveservices.azure.com/.default"
REPO_ROOT = Path(__file__).resolve().parents[2]


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

    async def sample(self, _context, params: CreateMessageRequestParams) -> types.CreateMessageResult | types.ErrorData:  # noqa: ANN001
        return await asyncio.to_thread(self._sample_sync, params)

    def _sample_sync(self, params: CreateMessageRequestParams) -> types.CreateMessageResult | types.ErrorData:
        """Handle MCP sampling/createMessage requests with Azure OpenAI."""
        if params.tools:
            return types.ErrorData(
                code=types.INVALID_REQUEST,
                message="Sampling tool calls are not supported by this lecture client.",
            )

        response = self._client.chat.completions.create(
            model=self._deployment,
            messages=build_sampling_messages(params),
            max_tokens=params.maxTokens,
            temperature=params.temperature,
            stop=params.stopSequences,
        )
        choice = response.choices[0]
        content = _coerce_openai_message_text(choice.message.content)
        return types.CreateMessageResult(
            role="assistant",
            content=types.TextContent(type="text", text=content),
            model=response.model or self._deployment,
            stopReason=map_sampling_stop_reason(choice.finish_reason),
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


def build_sampling_messages(params: CreateMessageRequestParams) -> list[dict[str, Any]]:
    """Convert MCP sampling requests into Azure OpenAI chat messages."""
    messages: list[dict[str, Any]] = []
    if params.systemPrompt:
        messages.append({"role": "system", "content": params.systemPrompt})
    for message in params.messages:
        messages.append({"role": message.role, "content": _serialize_sampling_message_content(message.content)})
    return messages


def map_sampling_stop_reason(finish_reason: str | None) -> str | None:
    """Translate Azure/OpenAI finish reasons to MCP sampling stop reasons."""
    if finish_reason == "length":
        return "maxTokens"
    if finish_reason == "tool_calls":
        return "toolUse"
    if finish_reason == "stop":
        return "endTurn"
    return "endTurn" if finish_reason else None


def _serialize_sampling_message_content(content: Any) -> str:
    blocks = content if isinstance(content, list) else [content]
    rendered: list[str] = []
    for block in blocks:
        if isinstance(block, TextContent):
            rendered.append(block.text)
        elif hasattr(block, "model_dump"):
            rendered.append(json.dumps(block.model_dump(mode="json"), indent=2, sort_keys=True))
        else:
            rendered.append(str(block))
    return "\n".join(part for part in rendered if part).strip()


def _coerce_openai_message_text(content: Any) -> str:
    if isinstance(content, str):
        return content
    if isinstance(content, list):
        parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(str(item.get("text", "")))
            else:
                parts.append(str(item))
        return "\n".join(part for part in parts if part).strip()
    return "" if content is None else str(content)


def build_client_helper_tools() -> list[dict[str, Any]]:
    """Expose MCP prompt/resource APIs to the model as local helper tools."""
    return [
        {
            "type": "function",
            "function": {
                "name": "list_prompts",
                "description": "List the MCP prompts advertised by the server.",
                "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_prompt",
                "description": "Retrieve one MCP prompt by name, optionally passing string arguments.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "name": {"type": "string", "description": "Prompt name to retrieve."},
                        "arguments": {
                            "type": "object",
                            "description": "Optional prompt arguments as string values.",
                            "additionalProperties": {"type": "string"},
                        },
                    },
                    "required": ["name"],
                    "additionalProperties": False,
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "list_resources",
                "description": "List concrete MCP resources currently advertised by the server.",
                "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "list_resource_templates",
                "description": "List MCP resource templates, including paginated URI patterns.",
                "parameters": {"type": "object", "properties": {}, "additionalProperties": False},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "read_resource",
                "description": "Read a resource URI returned by the server or shown in a resource template.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "uri": {"type": "string", "description": "Full resource URI to read."},
                    },
                    "required": ["uri"],
                    "additionalProperties": False,
                },
            },
        },
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


def supports_terminal_elicitation() -> bool:
    """Return True when the lecture client can safely prompt the local user."""
    return sys.stdin.isatty() and sys.stdout.isatty()


async def terminal_elicitation_callback(
    _context,  # noqa: ANN001
    params: ElicitRequestParams,
) -> types.ElicitResult | types.ErrorData:
    """Handle MCP form elicitation in the lecture client's local terminal."""
    if getattr(params, "mode", None) != "form":
        return types.ErrorData(code=types.INVALID_REQUEST, message="Only form elicitation is supported.")

    requested_schema = params.requestedSchema
    if not isinstance(requested_schema, dict):
        return types.ErrorData(code=types.INVALID_REQUEST, message="Unsupported elicitation schema.")

    properties = requested_schema.get("properties")
    if not isinstance(properties, dict) or len(properties) != 1:
        return types.ErrorData(code=types.INVALID_REQUEST, message="Only single-field elicitation forms are supported.")

    field_name, field_schema = next(iter(properties.items()))
    if not isinstance(field_schema, dict):
        return types.ErrorData(code=types.INVALID_REQUEST, message="Unsupported elicitation field schema.")

    print(f"\n[elicit] {params.message}")
    if _field_has_choices(field_schema):
        return await asyncio.to_thread(_prompt_for_choice, field_name, field_schema)
    return await asyncio.to_thread(_prompt_for_text, field_name, field_schema)


def _field_has_choices(field_schema: dict[str, Any]) -> bool:
    return isinstance(field_schema.get("oneOf"), list) or isinstance(field_schema.get("enum"), list)


def _prompt_for_choice(field_name: str, field_schema: dict[str, Any]) -> types.ElicitResult | types.ErrorData:
    options = _extract_choice_options(field_schema)
    if not options:
        return types.ErrorData(code=types.INVALID_REQUEST, message="No selectable options were provided.")

    for index, option in enumerate(options, start=1):
        print(f"  {index}. {option['title']}")

    while True:
        choice = input("Selection (blank cancels): ").strip()
        if not choice:
            return types.ElicitResult(action="cancel")
        try:
            selected_index = int(choice)
        except ValueError:
            print("Enter a number from the list or press Enter to cancel.")
            continue
        if 1 <= selected_index <= len(options):
            selected = options[selected_index - 1]
            return types.ElicitResult(action="accept", content={field_name: selected["value"]})
        print("Selection out of range. Try again.")


def _extract_choice_options(field_schema: dict[str, Any]) -> list[dict[str, str]]:
    if isinstance(field_schema.get("oneOf"), list):
        options: list[dict[str, str]] = []
        for option in field_schema["oneOf"]:
            if not isinstance(option, dict) or "const" not in option:
                continue
            value = str(option["const"])
            title = str(option.get("title") or value)
            options.append({"value": value, "title": title})
        return options

    if isinstance(field_schema.get("enum"), list):
        titles = field_schema.get("enumTitles")
        return [
            {
                "value": str(value),
                "title": str(titles[index]) if isinstance(titles, list) and index < len(titles) else str(value),
            }
            for index, value in enumerate(field_schema["enum"])
        ]

    return []


def _prompt_for_text(field_name: str, field_schema: dict[str, Any]) -> types.ElicitResult:
    title = field_schema.get("title")
    description = field_schema.get("description")
    if title:
        print(f"{title}:")
    if description:
        print(description)
    value = input("Value (blank cancels): ").strip()
    if not value:
        return types.ElicitResult(action="cancel")
    return types.ElicitResult(action="accept", content={field_name: value})


async def call_client_helper(session: ClientSession, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    """Execute a prompt/resource helper call through the MCP client session."""

    if name == "list_prompts":
        return (await session.list_prompts()).model_dump(mode="json")
    if name == "get_prompt":
        prompt_name = str(arguments["name"])
        raw_arguments = arguments.get("arguments") or {}
        prompt_arguments = {key: str(value) for key, value in raw_arguments.items()}
        return (await session.get_prompt(prompt_name, prompt_arguments or None)).model_dump(mode="json")
    if name == "list_resources":
        return (await session.list_resources()).model_dump(mode="json")
    if name == "list_resource_templates":
        return (await session.list_resource_templates()).model_dump(mode="json")
    if name == "read_resource":
        return (await session.read_resource(str(arguments["uri"]))).model_dump(mode="json")
    raise ValueError(f"Unknown local helper tool '{name}'.")


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
            if tool_call.name in {"list_prompts", "get_prompt", "list_resources", "list_resource_templates", "read_resource"}:
                serialized_result = json.dumps(
                    await call_client_helper(session, tool_call.name, tool_call.arguments),
                    indent=2,
                    sort_keys=True,
                )
            else:
                result = await session.call_tool(tool_call.name, tool_call.arguments)
                serialized_result = serialize_tool_result(result)
            messages.append(
                {
                    "role": "tool",
                    "tool_call_id": tool_call.id,
                    "content": serialized_result,
                }
            )

    raise RuntimeError("The model did not finish within the tool-call limit.")


async def wait_for_server(host: str, port: int, process: asyncio.subprocess.Process, *, timeout_seconds: float = 10.0) -> None:
    """Wait until the local HTTP server is accepting TCP connections."""
    deadline = asyncio.get_running_loop().time() + timeout_seconds
    last_error: Exception | None = None

    while asyncio.get_running_loop().time() < deadline:
        if process.returncode is not None:
            raise RuntimeError(f"Local MCP server exited early with code {process.returncode}.")
        try:
            _reader, writer = await asyncio.open_connection(host, port)
            writer.close()
            await writer.wait_closed()
            return
        except OSError as exc:
            last_error = exc
            await asyncio.sleep(0.1)

    raise RuntimeError(f"Timed out waiting for local MCP HTTP server on {host}:{port}: {last_error}")


async def terminate_server(process: asyncio.subprocess.Process) -> None:
    """Stop the local HTTP server subprocess."""
    if process.returncode is not None:
        return

    process.terminate()
    try:
        await asyncio.wait_for(process.wait(), timeout=5)
    except asyncio.TimeoutError:
        process.kill()
        await process.wait()


@asynccontextmanager
async def connect_local_mcp(
    *,
    server_module: str = "mcp_linux_diag_server",
    server_host: str = DEFAULT_HTTP_HOST,
    server_port: int = DEFAULT_HTTP_PORT,
    sampling_callback=None,  # noqa: ANN001
    elicitation_callback=None,  # noqa: ANN001
):
    """Launch the local MCP HTTP server and yield an initialized client session."""  # noqa: ANN201
    env = dict(os.environ)
    src_path = str(REPO_ROOT / "src")
    env["PYTHONPATH"] = f"{src_path}:{env['PYTHONPATH']}" if env.get("PYTHONPATH") else src_path
    process = await asyncio.create_subprocess_exec(
        sys.executable,
        "-m",
        server_module,
        "--host",
        server_host,
        "--port",
        str(server_port),
        cwd=str(REPO_ROOT),
        env=env,
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
    )
    try:
        await wait_for_server(server_host, server_port, process)
        async with httpx.AsyncClient(headers={API_KEY_HEADER: DEMO_API_KEY}) as http_client:
            async with streamable_http_client(
                build_mcp_url(host=server_host, port=server_port),
                http_client=http_client,
            ) as (read, write, get_session_id):
                resolved_elicitation_callback = elicitation_callback
                if resolved_elicitation_callback is None and supports_terminal_elicitation():
                    resolved_elicitation_callback = terminal_elicitation_callback
                async with ClientSession(
                    read,
                    write,
                    sampling_callback=sampling_callback,
                    elicitation_callback=resolved_elicitation_callback,
                ) as session:
                    await session.initialize()
                    if not get_session_id():
                        raise RuntimeError("MCP HTTP session initialization did not return an mcp-session-id header.")
                    yield session
    finally:
        await terminate_server(process)


async def run_single_prompt(
    *,
    config: ChatConfig,
    prompt: str,
    server_module: str = "mcp_linux_diag_server",
    server_host: str = DEFAULT_HTTP_HOST,
    server_port: int = DEFAULT_HTTP_PORT,
    emit_trace: bool = False,
) -> dict[str, Any]:
    """Run one prompt and return a structured result for scripts or tests."""
    model = AzureOpenAIChatModel(config)

    async with connect_local_mcp(
        server_module=server_module,
        server_host=server_host,
        server_port=server_port,
        sampling_callback=model.sample,
    ) as session:
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
            tools=build_openai_tools(mcp_tools) + build_client_helper_tools(),
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
    server_host: str = DEFAULT_HTTP_HOST,
    server_port: int = DEFAULT_HTTP_PORT,
    as_json: bool = False,
) -> None:
    """Start the MCP server, connect to it, and run the chat loop."""
    model = AzureOpenAIChatModel(config)

    async with connect_local_mcp(
        server_module=server_module,
        server_host=server_host,
        server_port=server_port,
        sampling_callback=model.sample,
    ) as session:
        tool_list = await session.list_tools()
        mcp_tools = tool_list.tools
        tool_names = ", ".join(tool.name for tool in mcp_tools) or "(none)"
        print(f"Connected to MCP server at {build_mcp_url(host=server_host, port=server_port)}. Tools: {tool_names}")

        messages: list[dict[str, Any]] = [{"role": "system", "content": config.system_prompt}]
        openai_tools = build_openai_tools(mcp_tools) + build_client_helper_tools()

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
    parser = argparse.ArgumentParser(description="Run the Milestone 6 Azure OpenAI chat client.")
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
    parser.add_argument("--server-host", default=DEFAULT_HTTP_HOST, help=f"Local MCP server host. Defaults to {DEFAULT_HTTP_HOST}.")
    parser.add_argument("--server-port", type=int, default=DEFAULT_HTTP_PORT, help=f"Local MCP server port. Defaults to {DEFAULT_HTTP_PORT}.")
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
                server_host=args.server_host,
                server_port=args.server_port,
                as_json=args.json,
            )
        )
    except Exception as exc:  # pragma: no cover - CLI guardrail
        print(f"Diagnostics chat client failed: {exc}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
