"""Linux process inspection tools for Milestone 2."""

from __future__ import annotations

import os
import pwd
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from pydantic import BaseModel, Field

_PROC_ROOT = Path("/proc")
_PROC_UPTIME = _PROC_ROOT / "uptime"
_PROC_STAT = _PROC_ROOT / "stat"
_DEFAULT_PAGE_SIZE = 5
_CLOCK_TICKS = os.sysconf("SC_CLK_TCK")
_PAGE_SIZE = os.sysconf("SC_PAGE_SIZE")


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


@dataclass(slots=True)
class _StatSnapshot:
    process_name: str
    parent_process_id: int
    user_ticks: int
    system_ticks: int
    thread_count: int
    start_ticks: int
    virtual_memory_bytes: int
    resident_pages: int


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
