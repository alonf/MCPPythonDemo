"""Sampling-assisted Linux diagnostics helpers."""

from __future__ import annotations

import os
import re
from pathlib import Path
from typing import Any

import mcp.types as types
from mcp.server.fastmcp import Context
from pydantic import BaseModel, ConfigDict, Field

_MAX_QUERY_ATTEMPTS = 4
_MAX_QUERY_TOKENS = 180
_MAX_SUMMARY_TOKENS = 220
_MAX_RENDERED_LINES = 40
_MAX_RENDERED_CHARS = 6000
_PROC_ROOT = Path("/proc")
_FORBIDDEN_TOKENS = (";", "`", "$(", "&&", "||", ">", "<")
_QUERY_PATTERN = re.compile(r"^(?P<path>/\S+)(?:\s*\|\s*grep\s+(?P<field>[A-Za-z0-9_.:-]+))?$")
_PROCESS_PATH_PATTERN = re.compile(r"^/proc/(?P<pid>\d+)/(stat|status|cmdline)$")
_FIELD_HINTS: dict[str, tuple[str, ...]] = {
    "/proc/meminfo": ("MemTotal", "MemAvailable", "MemFree", "Cached", "Buffers", "Dirty", "SwapFree"),
    "/proc/cpuinfo": ("model name", "cpu cores", "processor", "vendor_id"),
    "/proc/stat": ("cpu", "cpu0", "intr", "ctxt", "btime"),
    "/etc/os-release": ("NAME", "PRETTY_NAME", "VERSION_ID"),
    "/proc/self/status": ("VmRSS", "VmSize", "Threads", "State"),
}
_ALLOWED_EXACT_PATHS = {
    "/etc/os-release",
    "/proc/cpuinfo",
    "/proc/loadavg",
    "/proc/meminfo",
    "/proc/net/tcp",
    "/proc/net/udp",
    "/proc/self/cmdline",
    "/proc/self/stat",
    "/proc/self/status",
    "/proc/stat",
    "/proc/uptime",
    "/proc/version",
    "/sys/devices/system/cpu/online",
    "/sys/fs/cgroup/cpu.max",
    "/sys/fs/cgroup/memory.current",
    "/sys/fs/cgroup/memory.max",
}
_ALLOWED_PREFIXES = (
    "/proc/pressure/",
    "/proc/sys/fs/",
    "/proc/sys/kernel/",
    "/proc/sys/vm/",
)
_FORBIDDEN_PATH_SEGMENTS = (
    "/proc/kcore",
    "/proc/kmem",
    "/proc/mem",
    "/proc/sysvipc/",
    "/sys/class/gpio",
    "/sys/class/pwm",
    "/sys/kernel/debug",
)


class LinuxDiagnosticQuery(BaseModel):
    """Validated query produced by the sampling-assisted diagnostics flow."""

    model_config = ConfigDict(extra="forbid")

    path: str = Field(description="Absolute allowlisted /proc or /sys path.")
    field: str | None = Field(default=None, description="Optional field selector from a structured file.")


class LinuxDiagnosticObservation(BaseModel):
    """Deterministic observation collected from the validated Linux source."""

    path: str
    field: str | None = None
    value: str
    details: dict[str, Any] = Field(default_factory=dict)


async def troubleshoot_linux_diagnostics(user_request: str, *, ctx: Context) -> str:
    """Use sampling to choose a safe Linux diagnostic source and summarize it."""
    if not _client_supports_sampling(ctx):
        raise RuntimeError(
            "Client does not support sampling. "
            "A sampling-capable lecture client is required for troubleshoot_linux_diagnostics."
        )

    validation_errors: list[str] = []
    query: LinuxDiagnosticQuery | None = None
    observation: LinuxDiagnosticObservation | None = None

    for attempt in range(1, _MAX_QUERY_ATTEMPTS + 1):
        response = await ctx.session.create_message(
            messages=[
                types.SamplingMessage(
                    role="user",
                    content=types.TextContent(
                        type="text",
                        text=_build_query_request_message(user_request, validation_errors, attempt),
                    ),
                )
            ],
            max_tokens=_MAX_QUERY_TOKENS,
            system_prompt=_build_query_system_prompt(),
            temperature=0.0,
            related_request_id=ctx.request_id,
        )

        try:
            query = validate_linux_diagnostic_query(extract_sampling_text(response))
            observation = read_linux_diagnostic(query)
            await ctx.info(
                f"Sampling diagnostics selected {query.path}"
                + (f" (field {query.field})" if query.field else "")
            )
            break
        except ValueError as exc:
            validation_errors.append(str(exc))
            await ctx.warning(f"Sampling diagnostics attempt {attempt} rejected: {exc}")

    if query is None or observation is None:
        joined_errors = "; ".join(validation_errors) if validation_errors else "No safe Linux diagnostics source was produced."
        return (
            f"Unable to complete Linux diagnostics after {_MAX_QUERY_ATTEMPTS} attempts. "
            f"Validation errors: {joined_errors}"
        )

    return await _sample_summary(ctx, user_request, observation)


async def _sample_summary(ctx: Context, user_request: str, observation: LinuxDiagnosticObservation) -> str:
    response = await ctx.session.create_message(
        messages=[
            types.SamplingMessage(
                role="user",
                content=types.TextContent(
                    type="text",
                    text=(
                        f"User request: {user_request}\n"
                        f"Diagnostics source: {observation.path}\n"
                        f"Field: {observation.field or 'entire file excerpt'}\n"
                        f"Environment notes: {detect_environment_notes() or ['none']}\n"
                        f"Deterministic diagnostics output:\n{observation.value}\n\n"
                        "Provide a concise Linux-focused diagnosis. Explain what the data says, "
                        "mention scope limits like container or WSL boundaries when relevant, "
                        "and suggest one safe next check if the evidence is incomplete."
                    ),
                ),
            )
        ],
        max_tokens=_MAX_SUMMARY_TOKENS,
        system_prompt="You summarize Linux diagnostics results for the user. Use only the provided observation.",
        temperature=0.2,
        related_request_id=ctx.request_id,
    )
    summary = extract_sampling_text(response).strip()
    if summary:
        return summary
    return f"Observed {observation.field or 'diagnostic output'} from {observation.path}: {observation.value}."


def validate_linux_diagnostic_query(raw_text: str) -> LinuxDiagnosticQuery:
    """Sanitize and validate an LLM-proposed Linux diagnostics query."""
    cleaned_lines = [line.strip() for line in _strip_code_fences(raw_text).splitlines() if line.strip()]
    if not cleaned_lines:
        raise ValueError("Sampling returned no diagnostics source.")
    if len(cleaned_lines) != 1:
        raise ValueError("Sampling must return exactly one line: PATH or PATH | grep FIELD.")
    cleaned = cleaned_lines[0]
    if any(token in cleaned for token in _FORBIDDEN_TOKENS):
        raise ValueError("Sampling output used forbidden shell metacharacters.")
    if "|" in cleaned and not re.search(r"\|\s*grep\s+[A-Za-z0-9_.:-]+\s*$", cleaned):
        raise ValueError("Only the pattern 'PATH | grep FIELD' is allowed.")

    match = _QUERY_PATTERN.fullmatch(cleaned)
    if match is None:
        raise ValueError("Sampling must return PATH or PATH | grep FIELD.")

    raw_path = match.group("path")
    field = match.group("field")
    normalized_path = os.path.normpath(raw_path)
    if not normalized_path.startswith("/"):
        raise ValueError("Diagnostics path must be absolute.")
    if ".." in raw_path.split("/"):
        raise ValueError("Path traversal is not allowed.")
    if "[" in normalized_path or "]" in normalized_path:
        raise ValueError("Sampling must provide a concrete path or real PID, not placeholders.")
    if any(normalized_path == forbidden or normalized_path.startswith(f"{forbidden}/") for forbidden in _FORBIDDEN_PATH_SEGMENTS):
        raise ValueError(f"Path is forbidden: {normalized_path}")

    resolved_path = os.path.realpath(normalized_path)
    if not _is_allowed_path(normalized_path, resolved_path):
        raise ValueError("Diagnostics path is not allowlisted for Milestone 6.")

    return LinuxDiagnosticQuery(path=normalized_path, field=field)


def read_linux_diagnostic(query: LinuxDiagnosticQuery) -> LinuxDiagnosticObservation:
    """Read a validated Linux diagnostic source deterministically."""
    path = Path(query.path)
    try:
        if path.is_dir():
            raise ValueError("Diagnostics path resolved to a directory.")
        raw_text = path.read_text(encoding="utf-8")
    except PermissionError as exc:
        raise ValueError(
            f"Permission denied for {query.path}. Try a world-readable source like /proc/meminfo or /proc/loadavg."
        ) from exc
    except FileNotFoundError as exc:
        raise ValueError(f"Diagnostics source not found: {query.path}") from exc
    except OSError as exc:
        raise ValueError(f"Unable to read {query.path}: {exc}") from exc

    return LinuxDiagnosticObservation(
        path=query.path,
        field=query.field,
        value=_render_content(path=query.path, content=raw_text, field_name=query.field),
        details={"environment_notes": detect_environment_notes()},
    )


def extract_sampling_text(response: types.CreateMessageResult | types.CreateMessageResultWithTools) -> str:
    """Extract plain text from a sampling response."""
    content = response.content
    if isinstance(content, types.TextContent):
        return content.text
    if isinstance(content, list):
        return "\n".join(item.text for item in content if isinstance(item, types.TextContent)).strip()
    raise RuntimeError(f"Expected text sampling content, received {type(content).__name__}.")


def detect_environment_notes() -> list[str]:
    """Return low-cost notes about container or WSL scope."""
    notes: list[str] = []
    version_text = _safe_read_text(_PROC_ROOT / "version")
    if "microsoft" in version_text.casefold():
        notes.append("WSL-style kernel detected; readings reflect the Linux guest environment.")
    cgroup_text = _safe_read_text(_PROC_ROOT / "self" / "cgroup")
    if any(token in cgroup_text.casefold() for token in ("docker", "containerd", "kubepods", "lxc")):
        notes.append("Container cgroup markers detected; readings reflect the current container namespace.")
    return notes


def _build_query_system_prompt() -> str:
    allowlist = "\n".join(
        [
            "- /proc/meminfo | grep MemAvailable",
            "- /proc/meminfo | grep Dirty",
            "- /proc/loadavg",
            "- /proc/uptime",
            "- /proc/stat | grep cpu",
            "- /proc/pressure/memory | grep avg10",
            "- /proc/self/status | grep VmRSS",
            "- /proc/sys/vm/swappiness",
            "- /sys/fs/cgroup/memory.current",
            "- /etc/os-release | grep PRETTY_NAME",
        ]
    )
    return (
        "You generate one safe Linux diagnostics read target. "
        "Only use /proc, /sys, or /etc/os-release sources that are read-only and world-readable. "
        "Return exactly PATH or PATH | grep FIELD. "
        "No prose, no markdown, no shell chaining.\n\n"
        f"Example allowlisted targets:\n{allowlist}"
    )


def _build_query_request_message(user_request: str, validation_errors: list[str], attempt: int) -> str:
    return (
        f"User request: {user_request}\n"
        f"Previous validation errors: {validation_errors or ['none']}\n"
        f"Attempt: {attempt}\n\n"
        "Return exactly one Linux diagnostics source in one of these forms:\n"
        "- /proc/meminfo\n"
        "- /proc/meminfo | grep MemAvailable\n"
        "- /proc/loadavg\n"
        "- /proc/pressure/memory | grep avg10\n"
        "- /proc/self/status | grep VmRSS\n"
        "- /sys/fs/cgroup/memory.current"
    )


def _strip_code_fences(value: str) -> str:
    lines = []
    for raw_line in value.replace("\r", "\n").splitlines():
        stripped = raw_line.strip()
        if not stripped or stripped.startswith("```") or stripped.startswith("#"):
            continue
        lines.append(stripped)
    return "\n".join(lines).strip()


def _is_allowed_path(path: str, resolved_path: str) -> bool:
    if path in _ALLOWED_EXACT_PATHS or resolved_path in _ALLOWED_EXACT_PATHS:
        return True
    if any(path.startswith(prefix) or resolved_path.startswith(prefix) for prefix in _ALLOWED_PREFIXES):
        return True

    match = _PROCESS_PATH_PATTERN.fullmatch(path)
    if match is None:
        return False

    process_path = _PROC_ROOT / match.group("pid") / Path(path).name
    try:
        return process_path.is_file()
    except OSError:
        return False


def _render_content(*, path: str, content: str, field_name: str | None) -> str:
    if field_name is not None:
        matches = _extract_field_lines(path=path, content=content, field_name=field_name)
        if not matches:
            suggestions = ", ".join(_FIELD_HINTS.get(path, ())[:5])
            if suggestions:
                raise ValueError(f"Field '{field_name}' was not found. Try one of: {suggestions}.")
            raise ValueError(f"Field '{field_name}' was not found in {path}.")
        return "\n".join(matches)

    normalized = content.strip()
    if not normalized:
        raise ValueError(f"Diagnostics source {path} was empty.")

    lines = normalized.splitlines()[:_MAX_RENDERED_LINES]
    rendered = "\n".join(lines)
    if len(rendered) > _MAX_RENDERED_CHARS:
        rendered = rendered[: _MAX_RENDERED_CHARS - 15].rstrip() + "\n...[truncated]"
    elif len(normalized.splitlines()) > len(lines):
        rendered += "\n...[truncated]"
    return rendered


def _extract_field_lines(*, path: str, content: str, field_name: str) -> list[str]:
    lines = [line.strip() for line in content.splitlines() if line.strip()]
    lower_field = field_name.casefold()
    matches: list[str] = []

    for line in lines:
        if ":" in line:
            key, _value = line.split(":", 1)
            if key.strip().casefold() == lower_field:
                matches.append(line)
                continue
        if "=" in line:
            key, _value = line.split("=", 1)
            if key.strip().casefold() == lower_field:
                matches.append(line)
                continue
        first_token = line.split()[0]
        if first_token.casefold() == lower_field:
            matches.append(line)
            continue
        if path.startswith("/proc/pressure/") and re.search(rf"\b{re.escape(field_name)}=", line):
            matches.append(line)

    return matches[:_MAX_RENDERED_LINES]


def _safe_read_text(path: Path) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError:
        return ""


def _client_supports_sampling(ctx: Context) -> bool:
    return ctx.request_context.session.check_client_capability(
        types.ClientCapabilities(sampling=types.SamplingCapability())
    )
