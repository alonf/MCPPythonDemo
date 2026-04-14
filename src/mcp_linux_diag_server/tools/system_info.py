"""Linux system information tool for Milestone 1."""

from __future__ import annotations

import getpass
import os
import platform
from pathlib import Path

from pydantic import BaseModel, Field

_PROC_UPTIME = Path("/proc/uptime")
_PROC_LOADAVG = Path("/proc/loadavg")
_PROC_MEMINFO = Path("/proc/meminfo")
_OS_RELEASE = Path("/etc/os-release")
_KIBIBYTE = 1024


class LoadAverage(BaseModel):
    """Current Linux load average."""

    one_minute: float = Field(description="1 minute load average.")
    five_minutes: float = Field(description="5 minute load average.")
    fifteen_minutes: float = Field(description="15 minute load average.")


class MemorySnapshot(BaseModel):
    """Small memory snapshot derived from /proc/meminfo."""

    total_bytes: int = Field(description="Installed memory in bytes.")
    available_bytes: int = Field(description="Currently available memory in bytes.")
    used_bytes: int = Field(description="Computed used memory in bytes.")


class SystemInfoResult(BaseModel):
    """System diagnostics payload returned by get_system_info."""

    machine_name: str = Field(description="Host name reported by the Linux kernel.")
    user_name: str = Field(description="Current user running the MCP server.")
    os_description: str = Field(description="Friendly Linux distribution name.")
    kernel_release: str = Field(description="Kernel release string.")
    architecture: str = Field(description="Machine architecture.")
    processor_count: int = Field(description="Logical CPU count.")
    python_runtime: str = Field(description="Python runtime used by the server.")
    current_directory: str = Field(description="Current working directory of the server process.")
    uptime_seconds: float = Field(description="System uptime from /proc/uptime.")
    uptime_human: str = Field(description="Human readable uptime.")
    load_average: LoadAverage
    memory: MemorySnapshot
    wsl_detected: bool = Field(description="True when the server appears to run inside Windows Subsystem for Linux.")


def collect_system_info() -> SystemInfoResult:
    """Collect a minimal Linux diagnostics snapshot."""
    uptime_seconds = _read_uptime_seconds()
    total_memory, available_memory = _read_memory_bytes()

    return SystemInfoResult(
        machine_name=platform.node(),
        user_name=getpass.getuser(),
        os_description=_read_os_description(),
        kernel_release=platform.release(),
        architecture=platform.machine(),
        processor_count=os.cpu_count() or 1,
        python_runtime=platform.python_version(),
        current_directory=os.getcwd(),
        uptime_seconds=uptime_seconds,
        uptime_human=_format_uptime(uptime_seconds),
        load_average=_read_load_average(),
        memory=MemorySnapshot(
            total_bytes=total_memory,
            available_bytes=available_memory,
            used_bytes=max(total_memory - available_memory, 0),
        ),
        wsl_detected=_detect_wsl(),
    )


def _read_os_description() -> str:
    release_data: dict[str, str] = {}

    try:
        for line in _OS_RELEASE.read_text(encoding="utf-8").splitlines():
            if not line or "=" not in line:
                continue
            key, value = line.split("=", 1)
            release_data[key] = value.strip().strip('"')
    except OSError:
        return platform.platform()

    return release_data.get("PRETTY_NAME") or release_data.get("NAME") or platform.platform()


def _read_uptime_seconds() -> float:
    try:
        uptime_text = _PROC_UPTIME.read_text(encoding="utf-8").strip()
        return round(float(uptime_text.split()[0]), 2)
    except (OSError, ValueError, IndexError):
        return 0.0


def _read_load_average() -> LoadAverage:
    try:
        load_parts = _PROC_LOADAVG.read_text(encoding="utf-8").split()
        return LoadAverage(
            one_minute=float(load_parts[0]),
            five_minutes=float(load_parts[1]),
            fifteen_minutes=float(load_parts[2]),
        )
    except (OSError, ValueError, IndexError):
        return LoadAverage(one_minute=0.0, five_minutes=0.0, fifteen_minutes=0.0)


def _read_memory_bytes() -> tuple[int, int]:
    meminfo: dict[str, int] = {}

    try:
        lines = _PROC_MEMINFO.read_text(encoding="utf-8").splitlines()
    except OSError:
        return 0, 0

    for line in lines:
        if ":" not in line:
            continue
        key, raw_value = line.split(":", 1)
        value_parts = raw_value.strip().split()
        if not value_parts:
            continue
        try:
            meminfo[key] = int(value_parts[0]) * _KIBIBYTE
        except ValueError:
            continue

    total_memory = meminfo.get("MemTotal", 0)
    available_memory = meminfo.get("MemAvailable", meminfo.get("MemFree", 0))
    return total_memory, available_memory


def _format_uptime(uptime_seconds: float) -> str:
    total_seconds = int(uptime_seconds)
    days, remainder = divmod(total_seconds, 86_400)
    hours, remainder = divmod(remainder, 3_600)
    minutes, seconds = divmod(remainder, 60)

    if days:
        return f"{days}d {hours}h {minutes}m {seconds}s"
    if hours:
        return f"{hours}h {minutes}m {seconds}s"
    if minutes:
        return f"{minutes}m {seconds}s"
    return f"{seconds}s"


def _detect_wsl() -> bool:
    release = platform.release().lower()
    if "microsoft" in release or "wsl" in release:
        return True

    try:
        version_text = Path("/proc/version").read_text(encoding="utf-8").lower()
    except OSError:
        return False

    return "microsoft" in version_text or "wsl" in version_text
