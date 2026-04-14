"""Linux process inspection tools for Milestone 2."""

from __future__ import annotations

import asyncio
import os
import pwd
import signal
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import mcp.types as types
from mcp.server.fastmcp import Context
from pydantic import BaseModel, Field

_PROC_ROOT = Path("/proc")
_PROC_UPTIME = _PROC_ROOT / "uptime"
_PROC_STAT = _PROC_ROOT / "stat"
_DEFAULT_PAGE_SIZE = 5
_CLOCK_TICKS = os.sysconf("SC_CLK_TCK")
_PAGE_SIZE = os.sysconf("SC_PAGE_SIZE")
_CPU_SAMPLE_SECONDS = 0.75
_TERMINATION_TIMEOUT_SECONDS = 5.0


class BasicProcessInfo(BaseModel):
    """Lightweight process summary used for the list-first teaching flow."""

    process_id: int = Field(description="Linux process identifier.")
    process_name: str = Field(description="Short process name from /proc.")


class ProcessMemorySnapshot(BaseModel):
    """Small memory snapshot for one Linux process."""

    virtual_memory_bytes: int = Field(description="Virtual memory size in bytes.")
    resident_set_bytes: int = Field(description="Resident set size in bytes.")
    shared_memory_bytes: int = Field(description="Shared memory estimate in bytes.")


class ProcessDetailResult(BaseModel):
    """Detailed Linux process payload returned by PID and name lookups."""

    process_id: int = Field(description="Linux process identifier.")
    process_name: str = Field(description="Short process name from /proc.")
    parent_process_id: int = Field(description="Parent process ID.")
    state: str = Field(description="Kernel-reported process state.")
    thread_count: int = Field(description="Current thread count.")
    user_name: str | None = Field(description="Owning user name when available.")
    command_line: list[str] = Field(description="Command line arguments from /proc/[pid]/cmdline.")
    executable_path: str | None = Field(description="Resolved executable path when readable.")
    current_working_directory: str | None = Field(description="Resolved current working directory when readable.")
    start_time_utc: str | None = Field(description="Approximate UTC start time derived from kernel boot time.")
    uptime_seconds: float = Field(description="Approximate process uptime in seconds.")
    total_cpu_time_seconds: float = Field(description="Accumulated user plus system CPU time in seconds.")
    open_file_descriptor_count: int | None = Field(description="Visible open file descriptor count when readable.")
    memory: ProcessMemorySnapshot


class ProcessQueryResult(BaseModel):
    """Paged detailed process result for by-name lookups."""

    processes: list[ProcessDetailResult] = Field(default_factory=list)
    page_number: int = Field(description="1-based page number used for this query.")
    page_size: int = Field(description="Process detail count per page.")
    total_count: int = Field(description="Total matching process count before paging.")
    has_more: bool = Field(description="True when another page of results is available.")


class ProcessCpuUsage(BaseModel):
    """CPU-sampled process candidate used by the Milestone 5 kill flow."""

    process_id: int = Field(description="Linux process identifier.")
    process_name: str = Field(description="Short process name from /proc.")
    working_set_bytes: int = Field(description="Resident memory estimate in bytes.")
    cpu_percent: float = Field(description="CPU percent sampled over a short interval.")


class KillProcessResult(BaseModel):
    """Outcome payload for the Milestone 5 kill_process tool."""

    process_id: int = Field(description="Target process ID, or -1 when no process was selected.")
    process_name: str = Field(description="Resolved process name when available.")
    status: str = Field(description="Outcome status: terminated, cancelled, not-found, or failed.")
    message: str = Field(description="Human-readable outcome message.")
    reason: str | None = Field(default=None, description="Optional user-provided reason for the action.")

    @classmethod
    def success(cls, process_id: int, process_name: str, reason: str | None) -> KillProcessResult:
        return cls(
            process_id=process_id,
            process_name=process_name,
            status="terminated",
            message=f"Process {process_name} (PID {process_id}) was terminated successfully.",
            reason=reason,
        )

    @classmethod
    def cancelled(cls, message: str) -> KillProcessResult:
        return cls(
            process_id=-1,
            process_name="",
            status="cancelled",
            message=message,
        )

    @classmethod
    def not_found(cls, process_id: int) -> KillProcessResult:
        return cls(
            process_id=process_id,
            process_name="",
            status="not-found",
            message=f"No process found with PID {process_id}.",
        )

    @classmethod
    def failed(
        cls,
        process_id: int,
        process_name: str,
        error_message: str,
        *,
        reason: str | None = None,
    ) -> KillProcessResult:
        return cls(
            process_id=process_id,
            process_name=process_name,
            status="failed",
            message=f"Failed to terminate {process_name} (PID {process_id}): {error_message}",
            reason=reason,
        )


@dataclass(slots=True)
class _StatSnapshot:
    process_name: str
    state: str
    parent_process_id: int
    user_ticks: int
    system_ticks: int
    thread_count: int
    start_ticks: int
    virtual_memory_bytes: int
    resident_pages: int


@dataclass(slots=True)
class _ProcessRuntimeSnapshot:
    process_id: int
    process_name: str
    working_set_bytes: int
    total_cpu_ticks: int


def list_processes() -> list[BasicProcessInfo]:
    """Return a lightweight list of running Linux processes."""
    processes: list[BasicProcessInfo] = []

    for process_id in _iter_process_ids():
        process_name = _read_process_name(process_id)
        if process_name is None:
            continue
        processes.append(BasicProcessInfo(process_id=process_id, process_name=process_name))

    return sorted(processes, key=lambda item: (item.process_name.lower(), item.process_id))


def get_process_by_id(process_id: int) -> ProcessDetailResult:
    """Return detailed Linux process information for one PID."""
    process = _read_process_detail(process_id)
    if process is None:
        raise ValueError(f"No process found with ID '{process_id}'.")
    return process


def get_processes_by_name(
    process_name: str,
    *,
    page_number: int | None = None,
    page_size: int | None = None,
) -> ProcessQueryResult:
    """Return paged detailed Linux process information for matching names."""
    normalized_query = _normalize_process_name(process_name)
    actual_page_number = page_number if page_number and page_number > 0 else 1
    actual_page_size = page_size if page_size and page_size > 0 else _DEFAULT_PAGE_SIZE

    matches: list[ProcessDetailResult] = []
    for process_id in _iter_process_ids():
        if not _process_matches_name(process_id, normalized_query):
            continue

        detail = _read_process_detail(process_id)
        if detail is not None:
            matches.append(detail)

    matches.sort(key=lambda item: item.process_id)
    start_index = (actual_page_number - 1) * actual_page_size
    end_index = start_index + actual_page_size
    paged_matches = matches[start_index:end_index]

    return ProcessQueryResult(
        processes=paged_matches,
        page_number=actual_page_number,
        page_size=actual_page_size,
        total_count=len(matches),
        has_more=end_index < len(matches),
    )


async def kill_process(
    process_id: int | None = None,
    reason: str | None = None,
    *,
    ctx: Context,
) -> KillProcessResult:
    """Terminate a process only after server-driven elicitation confirms intent."""
    if not _client_supports_form_elicitation(ctx):
        raise RuntimeError(
            "Client does not support elicitation. "
            "A client that can fulfill form elicitation is required for killProcess."
        )

    candidate: ProcessCpuUsage | None
    if process_id is None:
        candidates = [item for item in await sample_top_cpu_processes(take=5) if not _is_protected_process_id(item.process_id)]
        if not candidates:
            raise RuntimeError("Unable to locate any safe running processes. Try again in a moment.")
        candidate = await _elicit_process_selection(ctx, candidates)
        if candidate is None:
            return KillProcessResult.cancelled("Process selection was cancelled by the user.")
    else:
        candidate = get_process_candidate_by_id(process_id)
        if candidate is None:
            return KillProcessResult.not_found(process_id)
        if _is_protected_process_id(process_id):
            return KillProcessResult.failed(
                process_id,
                candidate.process_name,
                "Refusing to terminate the active demo server or its parent process.",
                reason=reason,
            )

    confirmed = await _elicit_confirmation(ctx, candidate)
    if not confirmed:
        return KillProcessResult.cancelled("User declined to confirm the termination phrase.")

    try:
        await _terminate_process(candidate.process_id)
    except ProcessLookupError:
        return KillProcessResult.not_found(candidate.process_id)
    except PermissionError as exc:
        return KillProcessResult.failed(candidate.process_id, candidate.process_name, str(exc), reason=reason)
    except OSError as exc:
        return KillProcessResult.failed(candidate.process_id, candidate.process_name, str(exc), reason=reason)

    return KillProcessResult.success(candidate.process_id, candidate.process_name, reason)


async def sample_top_cpu_processes(*, take: int = 5) -> list[ProcessCpuUsage]:
    """Sample the current top CPU consumers using two /proc snapshots."""
    initial = _capture_runtime_snapshot()
    await asyncio.sleep(_CPU_SAMPLE_SECONDS)
    later = _capture_runtime_snapshot()
    processor_count = max(os.cpu_count() or 1, 1)
    interval_milliseconds = _CPU_SAMPLE_SECONDS * 1000.0

    candidates = [
        ProcessCpuUsage(
            process_id=sample.process_id,
            process_name=sample.process_name,
            working_set_bytes=sample.working_set_bytes,
            cpu_percent=round(
                max(sample.total_cpu_ticks - initial[sample.process_id].total_cpu_ticks, 0)
                / _CLOCK_TICKS
                * 1000.0
                / (interval_milliseconds * processor_count)
                * 100.0,
                1,
            ),
        )
        for sample in later.values()
        if sample.process_id in initial
    ]
    candidates = [candidate for candidate in candidates if candidate.working_set_bytes > 0]
    candidates.sort(key=lambda item: (-item.cpu_percent, -item.working_set_bytes, item.process_id))

    if candidates:
        return candidates[:take]

    fallback = [
        ProcessCpuUsage(
            process_id=sample.process_id,
            process_name=sample.process_name,
            working_set_bytes=sample.working_set_bytes,
            cpu_percent=0.0,
        )
        for sample in later.values()
    ]
    fallback.sort(key=lambda item: (-item.working_set_bytes, item.process_id))
    return fallback[:take]


def get_process_candidate_by_id(process_id: int) -> ProcessCpuUsage | None:
    """Return the M5 candidate view for one PID."""
    detail = _read_process_detail(process_id)
    if detail is None:
        return None
    return ProcessCpuUsage(
        process_id=detail.process_id,
        process_name=detail.process_name,
        working_set_bytes=detail.memory.resident_set_bytes,
        cpu_percent=0.0,
    )


def _iter_process_ids() -> list[int]:
    try:
        return sorted(
            int(entry.name)
            for entry in os.scandir(_PROC_ROOT)
            if entry.name.isdigit() and entry.is_dir(follow_symlinks=False)
        )
    except OSError:
        return []


def _read_process_name(process_id: int) -> str | None:
    status_fields = _read_status_fields(process_id)
    if status_fields is not None and status_fields.get("Name"):
        return status_fields["Name"]

    stat_snapshot = _read_stat_snapshot(process_id)
    if stat_snapshot is not None:
        return stat_snapshot.process_name

    return None


def _process_matches_name(process_id: int, normalized_query: str) -> bool:
    candidate_names = {
        _normalize_process_name(name)
        for name in (
            _read_process_name(process_id),
            _read_link(_PROC_ROOT / str(process_id) / "exe"),
            _read_first_command(_PROC_ROOT / str(process_id) / "cmdline"),
        )
        if name
    }
    return normalized_query in candidate_names


def _read_process_detail(process_id: int) -> ProcessDetailResult | None:
    process_dir = _PROC_ROOT / str(process_id)
    if not process_dir.is_dir():
        return None

    status_fields = _read_status_fields(process_id)
    stat_snapshot = _read_stat_snapshot(process_id)
    if status_fields is None and stat_snapshot is None:
        return None

    process_name = (
        (status_fields or {}).get("Name")
        or (stat_snapshot.process_name if stat_snapshot is not None else None)
        or str(process_id)
    )
    parent_process_id = _parse_status_int((status_fields or {}).get("PPid"))
    if not parent_process_id and stat_snapshot is not None:
        parent_process_id = stat_snapshot.parent_process_id

    thread_count = _parse_status_int((status_fields or {}).get("Threads"))
    if thread_count <= 0 and stat_snapshot is not None:
        thread_count = stat_snapshot.thread_count

    executable_path = _read_link(process_dir / "exe")
    current_working_directory = _read_link(process_dir / "cwd")
    command_line = _read_command_line(process_dir / "cmdline")

    user_name = _lookup_user_name((status_fields or {}).get("Uid"))
    start_time_utc = _format_process_start_time(stat_snapshot)
    uptime_seconds = _read_process_uptime_seconds(stat_snapshot)
    total_cpu_time_seconds = _read_total_cpu_time_seconds(stat_snapshot)

    return ProcessDetailResult(
        process_id=process_id,
        process_name=process_name,
        parent_process_id=parent_process_id,
        state=(status_fields or {}).get("State", "unknown"),
        thread_count=max(thread_count, 0),
        user_name=user_name,
        command_line=command_line,
        executable_path=executable_path,
        current_working_directory=current_working_directory,
        start_time_utc=start_time_utc,
        uptime_seconds=uptime_seconds,
        total_cpu_time_seconds=total_cpu_time_seconds,
        open_file_descriptor_count=_count_open_file_descriptors(process_dir / "fd"),
        memory=_read_process_memory(process_dir, stat_snapshot),
    )


def _read_status_fields(process_id: int) -> dict[str, str] | None:
    try:
        lines = (_PROC_ROOT / str(process_id) / "status").read_text(encoding="utf-8").splitlines()
    except OSError:
        return None

    fields: dict[str, str] = {}
    for line in lines:
        if ":" not in line:
            continue
        key, value = line.split(":", 1)
        fields[key] = value.strip()
    return fields


def _read_stat_snapshot(process_id: int) -> _StatSnapshot | None:
    try:
        stat_text = (_PROC_ROOT / str(process_id) / "stat").read_text(encoding="utf-8").strip()
    except OSError:
        return None

    prefix, separator, suffix = stat_text.rpartition(") ")
    if not separator:
        return None

    _, _, process_name = prefix.partition(" (")
    fields = suffix.split()
    if len(fields) < 22:
        return None

    try:
        return _StatSnapshot(
            process_name=process_name,
            state=fields[0],
            parent_process_id=int(fields[1]),
            user_ticks=int(fields[11]),
            system_ticks=int(fields[12]),
            thread_count=int(fields[17]),
            start_ticks=int(fields[19]),
            virtual_memory_bytes=int(fields[20]),
            resident_pages=int(fields[21]),
        )
    except ValueError:
        return None


def _read_process_memory(process_dir: Path, stat_snapshot: _StatSnapshot | None) -> ProcessMemorySnapshot:
    shared_pages = 0
    try:
        statm_parts = (process_dir / "statm").read_text(encoding="utf-8").split()
        if len(statm_parts) >= 3:
            shared_pages = int(statm_parts[2])
    except (OSError, ValueError):
        shared_pages = 0

    virtual_memory_bytes = stat_snapshot.virtual_memory_bytes if stat_snapshot is not None else 0
    resident_set_bytes = (stat_snapshot.resident_pages * _PAGE_SIZE) if stat_snapshot is not None else 0
    return ProcessMemorySnapshot(
        virtual_memory_bytes=max(virtual_memory_bytes, 0),
        resident_set_bytes=max(resident_set_bytes, 0),
        shared_memory_bytes=max(shared_pages * _PAGE_SIZE, 0),
    )


def _read_command_line(path: Path) -> list[str]:
    try:
        raw = path.read_bytes()
    except OSError:
        return []

    return [part.decode("utf-8", errors="replace") for part in raw.split(b"\0") if part]


def _read_first_command(path: Path) -> str | None:
    command_line = _read_command_line(path)
    return command_line[0] if command_line else None


def _read_link(path: Path) -> str | None:
    try:
        return str(path.readlink())
    except OSError:
        return None


def _lookup_user_name(uid_field: str | None) -> str | None:
    if not uid_field:
        return None

    try:
        uid = int(uid_field.split()[0])
    except (IndexError, ValueError):
        return None

    try:
        return pwd.getpwuid(uid).pw_name
    except KeyError:
        return str(uid)


def _format_process_start_time(stat_snapshot: _StatSnapshot | None) -> str | None:
    if stat_snapshot is None:
        return None

    boot_time = _read_boot_time_utc()
    if boot_time is None:
        return None

    started_at = boot_time + (stat_snapshot.start_ticks / _CLOCK_TICKS)
    return datetime.fromtimestamp(started_at, tz=UTC).isoformat()


def _read_boot_time_utc() -> float | None:
    try:
        for line in _PROC_STAT.read_text(encoding="utf-8").splitlines():
            if line.startswith("btime "):
                return float(line.split()[1])
    except (OSError, ValueError, IndexError):
        return None

    return None


def _read_process_uptime_seconds(stat_snapshot: _StatSnapshot | None) -> float:
    if stat_snapshot is None:
        return 0.0

    try:
        uptime_seconds = float(_PROC_UPTIME.read_text(encoding="utf-8").split()[0])
    except (OSError, ValueError, IndexError):
        return 0.0

    started_after_boot = stat_snapshot.start_ticks / _CLOCK_TICKS
    return round(max(uptime_seconds - started_after_boot, 0.0), 2)


def _read_total_cpu_time_seconds(stat_snapshot: _StatSnapshot | None) -> float:
    if stat_snapshot is None:
        return 0.0
    return round((stat_snapshot.user_ticks + stat_snapshot.system_ticks) / _CLOCK_TICKS, 2)


def _count_open_file_descriptors(path: Path) -> int | None:
    try:
        return len(os.listdir(path))
    except OSError:
        return None


def _parse_status_int(value: str | None) -> int:
    if not value:
        return 0
    try:
        return int(value.split()[0])
    except (IndexError, ValueError):
        return 0


def _normalize_process_name(value: str) -> str:
    candidate = Path(value).name.strip().lower()
    if candidate.endswith(".exe"):
        candidate = candidate[:-4]
    return candidate


def _capture_runtime_snapshot() -> dict[int, _ProcessRuntimeSnapshot]:
    snapshot: dict[int, _ProcessRuntimeSnapshot] = {}
    for process_id in _iter_process_ids():
        stat_snapshot = _read_stat_snapshot(process_id)
        if stat_snapshot is None:
            continue
        snapshot[process_id] = _ProcessRuntimeSnapshot(
            process_id=process_id,
            process_name=stat_snapshot.process_name,
            working_set_bytes=max(stat_snapshot.resident_pages * _PAGE_SIZE, 0),
            total_cpu_ticks=stat_snapshot.user_ticks + stat_snapshot.system_ticks,
        )
    return snapshot


def _client_supports_form_elicitation(ctx: Context) -> bool:
    session = ctx.request_context.session
    return session.check_client_capability(
        types.ClientCapabilities(
            elicitation=types.ElicitationCapability(form=types.FormElicitationCapability())
        )
    )


async def _elicit_process_selection(ctx: Context, candidates: list[ProcessCpuUsage]) -> ProcessCpuUsage | None:
    response = await ctx.request_context.session.elicit_form(
        "Select one of the top CPU consumers to terminate. Only a handful are shown for safety.",
        _build_process_selection_schema(candidates),
        ctx.request_id,
    )
    if response.action != "accept":
        return None

    selected_value = (response.content or {}).get("process")
    try:
        selected_pid = int(str(selected_value))
    except (TypeError, ValueError):
        return None

    return next((candidate for candidate in candidates if candidate.process_id == selected_pid), None) or get_process_candidate_by_id(selected_pid)


async def _elicit_confirmation(ctx: Context, process: ProcessCpuUsage) -> bool:
    confirmation_phrase = f"CONFIRM PID {process.process_id}"
    response = await ctx.request_context.session.elicit_form(
        f"You are about to terminate {process.process_name} (PID {process.process_id}). This cannot be undone.",
        _build_confirmation_schema(process.process_id),
        ctx.request_id,
    )
    provided = (response.content or {}).get("confirmation")
    return response.action == "accept" and isinstance(provided, str) and provided.strip().lower() == confirmation_phrase.lower()


def _build_process_selection_schema(candidates: list[ProcessCpuUsage]) -> dict[str, object]:
    return {
        "type": "object",
        "properties": {
            "process": {
                "type": "string",
                "title": "Process",
                "description": "Select the process you want to terminate.",
                "oneOf": [
                    {"const": str(candidate.process_id), "title": _format_process_candidate(candidate)}
                    for candidate in candidates
                ],
            }
        },
        "required": ["process"],
        "additionalProperties": False,
    }


def _build_confirmation_schema(process_id: int) -> dict[str, object]:
    confirmation_phrase = f"CONFIRM PID {process_id}"
    return {
        "type": "object",
        "properties": {
            "confirmation": {
                "type": "string",
                "title": "Confirmation Phrase",
                "description": f"Type '{confirmation_phrase}' to confirm termination.",
                "minLength": len(confirmation_phrase),
            }
        },
        "required": ["confirmation"],
        "additionalProperties": False,
    }


def _format_process_candidate(candidate: ProcessCpuUsage) -> str:
    return (
        f"{candidate.process_name} (PID {candidate.process_id}) • "
        f"CPU {candidate.cpu_percent:.1f}% • RAM {_format_bytes(candidate.working_set_bytes)}"
    )


def _format_bytes(byte_count: int) -> str:
    sizes = ["B", "KB", "MB", "GB", "TB"]
    size = float(max(byte_count, 0))
    order = 0
    while size >= 1024 and order < len(sizes) - 1:
        size /= 1024
        order += 1
    return f"{size:0.1f} {sizes[order]}"


def _is_protected_process_id(process_id: int) -> bool:
    current_pid = os.getpid()
    return process_id in {current_pid, os.getppid()}


async def _terminate_process(process_id: int) -> None:
    if _is_protected_process_id(process_id):
        raise OSError("Refusing to terminate the active demo server or its parent process.")

    os.kill(process_id, signal.SIGTERM)
    if await _wait_for_exit(process_id, timeout_seconds=_TERMINATION_TIMEOUT_SECONDS):
        return

    os.kill(process_id, signal.SIGKILL)
    if await _wait_for_exit(process_id, timeout_seconds=_TERMINATION_TIMEOUT_SECONDS):
        return

    raise OSError("Process did not exit after SIGTERM and SIGKILL.")


async def _wait_for_exit(process_id: int, *, timeout_seconds: float) -> bool:
    deadline = asyncio.get_running_loop().time() + timeout_seconds
    while asyncio.get_running_loop().time() < deadline:
        if _process_has_exited(process_id):
            return True
        await asyncio.sleep(0.1)

    return _process_has_exited(process_id)


def _process_has_exited(process_id: int) -> bool:
    stat_snapshot = _read_stat_snapshot(process_id)
    if stat_snapshot is None:
        return True
    return stat_snapshot.state == "Z"
