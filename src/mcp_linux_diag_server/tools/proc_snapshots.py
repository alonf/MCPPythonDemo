"""Allowed-root proc/sys snapshot tools and resource helpers for Milestone 7."""

from __future__ import annotations

import json
import os
import stat
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import ClassVar
from uuid import uuid4

import mcp.types as types
from mcp.server.fastmcp import Context
from pydantic import BaseModel

DEFAULT_PROC_RESOURCE_LIMIT = 50
MAX_PROC_RESOURCE_LIMIT = 500
RESOURCE_SCHEME = "proc"
_SUPPORTED_ROOT_PREFIXES = ("/proc", "/sys")
_FORBIDDEN_TOKENS = (";", "`", "$(", "&&", "||", ">", "<")
_DEFAULT_ALLOWED_ROOTS = (
    "/proc/loadavg",
    "/proc/meminfo",
    "/proc/net",
    "/proc/pressure",
    "/proc/self",
    "/proc/stat",
    "/proc/sys/kernel",
    "/proc/sys/vm",
    "/proc/uptime",
    "/proc/version",
    "/sys/devices/system/cpu",
    "/sys/fs/cgroup",
)


class ProcSnapshotEntry(BaseModel):
    """One stored proc/sys snapshot entry."""

    entry_number: int
    path: str
    relative_path: str
    entry_type: str
    line_number: int | None = None
    text: str | None = None
    size_bytes: int | None = None


class ProcSnapshotPagination(BaseModel):
    """Pagination metadata returned with every proc snapshot resource read."""

    total_count: int
    returned_count: int
    limit: int
    offset: int
    has_more: bool
    next_offset: int | None


class ProcSnapshotSummary(BaseModel):
    """Result returned by the proc snapshot tool."""

    snapshot_id: str
    path: str
    resolved_path: str
    matched_allowed_root: str
    path_kind: str
    created_at_utc: str
    entry_count: int
    resource_uri: str
    paginated_resource_template: str


class ProcSnapshotPage(BaseModel):
    """Paged resource payload for one proc/sys snapshot."""

    snapshot_id: str
    path: str
    resolved_path: str
    matched_allowed_root: str
    path_kind: str
    created_at_utc: str
    entry_count: int
    entries: list[ProcSnapshotEntry]
    pagination: ProcSnapshotPagination


class ProcAccessResult(BaseModel):
    """Result returned by the proc access request tool."""

    status: str
    requested_root: str
    reason: str | None
    message: str
    allowed_roots: list[str]


@dataclass(slots=True)
class _StoredProcSnapshot:
    snapshot_id: str
    path: str
    resolved_path: str
    matched_allowed_root: str
    path_kind: str
    created_at_utc: str
    entries: tuple[ProcSnapshotEntry, ...] = field(default_factory=tuple)

    @property
    def entry_count(self) -> int:
        return len(self.entries)


class _ProcSnapshotStore:
    """Thread-safe in-memory proc snapshot storage."""

    _snapshots: dict[str, _StoredProcSnapshot]
    _lock: Lock
    _instance: ClassVar[_ProcSnapshotStore | None] = None

    def __init__(self) -> None:
        self._snapshots = {}
        self._lock = Lock()

    @classmethod
    def instance(cls) -> _ProcSnapshotStore:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def save(self, snapshot: _StoredProcSnapshot) -> None:
        with self._lock:
            self._snapshots[snapshot.snapshot_id] = snapshot

    def get(self, snapshot_id: str) -> _StoredProcSnapshot | None:
        with self._lock:
            return self._snapshots.get(snapshot_id)

    def clear(self) -> None:
        with self._lock:
            self._snapshots.clear()


class ProcRootsService:
    """Thread-safe allowed-roots service for proc/sys paths."""

    _allowed_roots: set[str]
    _lock: Lock
    _instance: ClassVar[ProcRootsService | None] = None

    def __init__(self) -> None:
        self._lock = Lock()
        self._allowed_roots = set(_DEFAULT_ALLOWED_ROOTS)

    @classmethod
    def instance(cls) -> ProcRootsService:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def get_allowed_roots(self) -> list[str]:
        with self._lock:
            return sorted(self._allowed_roots)

    def add_allowed_root(self, path: str) -> str:
        normalized = _normalize_proc_path(path)
        with self._lock:
            self._allowed_roots.add(normalized)
        return normalized

    def reset(self) -> None:
        with self._lock:
            self._allowed_roots = set(_DEFAULT_ALLOWED_ROOTS)

    def resolve_matching_root(self, path: str) -> str | None:
        normalized_path = _normalize_proc_path(path)
        resolved_path = os.path.realpath(normalized_path)
        for root in self.get_allowed_roots():
            resolved_root = os.path.realpath(root)
            if _is_path_within(normalized_path, root) and _is_path_within(resolved_path, resolved_root):
                return root
        return None


def create_proc_snapshot(path: str) -> ProcSnapshotSummary:
    """Create a read-only snapshot from an allowed proc/sys path."""

    path_info = validate_proc_snapshot_path(path)
    entries = _snapshot_entries(path_info["normalized_path"], kind=path_info["path_kind"])
    snapshot = _StoredProcSnapshot(
        snapshot_id=uuid4().hex,
        path=path_info["normalized_path"],
        resolved_path=path_info["resolved_path"],
        matched_allowed_root=path_info["matched_allowed_root"],
        path_kind=path_info["path_kind"],
        created_at_utc=datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        entries=entries,
    )
    _ProcSnapshotStore.instance().save(snapshot)
    return ProcSnapshotSummary(
        snapshot_id=snapshot.snapshot_id,
        path=snapshot.path,
        resolved_path=snapshot.resolved_path,
        matched_allowed_root=snapshot.matched_allowed_root,
        path_kind=snapshot.path_kind,
        created_at_utc=snapshot.created_at_utc,
        entry_count=snapshot.entry_count,
        resource_uri=_build_snapshot_uri(snapshot.snapshot_id),
        paginated_resource_template=_build_snapshot_uri(snapshot.snapshot_id, limit="{limit}", offset="{offset}"),
    )


async def request_proc_access(path: str, *, reason: str | None, ctx: Context) -> ProcAccessResult:
    """Request access to an additional proc/sys root via elicitation."""

    path_info = validate_proc_snapshot_path(path, require_allowed_root=False)
    normalized_path = path_info["normalized_path"]
    roots_service = ProcRootsService.instance()
    if roots_service.resolve_matching_root(normalized_path) is not None:
        allowed_roots = roots_service.get_allowed_roots()
        return ProcAccessResult(
            status="already_allowed",
            requested_root=normalized_path,
            reason=reason.strip() if reason else None,
            message=f"{normalized_path} is already inside the current allowed roots.",
            allowed_roots=allowed_roots,
        )

    if not _client_supports_form_elicitation(ctx):
        raise RuntimeError(
            "Client does not support elicitation. "
            "A client that can fulfill form elicitation is required for request_proc_access."
        )

    response = await ctx.request_context.session.elicit_form(
        _build_proc_access_message(normalized_path, reason),
        _build_proc_access_schema(normalized_path),
        ctx.request_id,
    )
    selected_root = (response.content or {}).get("root")
    if response.action != "accept" or selected_root != normalized_path:
        return ProcAccessResult(
            status="denied",
            requested_root=normalized_path,
            reason=reason.strip() if reason else None,
            message=f"Access was not granted for {normalized_path}.",
            allowed_roots=roots_service.get_allowed_roots(),
        )

    approved_root = roots_service.add_allowed_root(normalized_path)
    allowed_roots = roots_service.get_allowed_roots()
    await ctx.info(f"Granted proc/sys access to {approved_root}")
    return ProcAccessResult(
        status="granted",
        requested_root=approved_root,
        reason=reason.strip() if reason else None,
        message=f"Access granted for {approved_root}. You can now call create_proc_snapshot for paths under that root.",
        allowed_roots=allowed_roots,
    )


def render_proc_snapshot_resource(snapshot_id: str, *, limit: int = DEFAULT_PROC_RESOURCE_LIMIT, offset: int = 0) -> str:
    """Render a proc snapshot resource as JSON text."""

    page = get_proc_snapshot_page(snapshot_id, limit=limit, offset=offset)
    return json.dumps(page.model_dump(mode="json"), indent=2, sort_keys=True)


def get_proc_snapshot_page(snapshot_id: str, *, limit: int = DEFAULT_PROC_RESOURCE_LIMIT, offset: int = 0) -> ProcSnapshotPage:
    """Return one paged slice of a stored proc snapshot."""

    if limit <= 0:
        raise ValueError("limit must be greater than zero.")
    if offset < 0:
        raise ValueError("offset must be zero or greater.")

    resolved_limit = min(limit, MAX_PROC_RESOURCE_LIMIT)
    snapshot = _ProcSnapshotStore.instance().get(snapshot_id)
    if snapshot is None:
        raise ValueError(f"No proc snapshot found for id '{snapshot_id}'.")

    page_entries = list(snapshot.entries[offset : offset + resolved_limit])
    returned_count = len(page_entries)
    total_count = snapshot.entry_count
    next_offset = offset + returned_count if (offset + returned_count) < total_count else None
    pagination = ProcSnapshotPagination(
        total_count=total_count,
        returned_count=returned_count,
        limit=resolved_limit,
        offset=offset,
        has_more=next_offset is not None,
        next_offset=next_offset,
    )
    return ProcSnapshotPage(
        snapshot_id=snapshot.snapshot_id,
        path=snapshot.path,
        resolved_path=snapshot.resolved_path,
        matched_allowed_root=snapshot.matched_allowed_root,
        path_kind=snapshot.path_kind,
        created_at_utc=snapshot.created_at_utc,
        entry_count=total_count,
        entries=page_entries,
        pagination=pagination,
    )


def validate_proc_snapshot_path(path: str, *, require_allowed_root: bool = True) -> dict[str, str]:
    """Normalize and validate a proc/sys snapshot path."""

    normalized_path = _normalize_proc_path(path)
    path_info = _read_path_info(normalized_path)
    matched_allowed_root = ProcRootsService.instance().resolve_matching_root(normalized_path)
    if require_allowed_root and matched_allowed_root is None:
        allowed_roots = ", ".join(ProcRootsService.instance().get_allowed_roots())
        raise ValueError(
            f"Access denied for '{normalized_path}'. Allowed roots: {allowed_roots}. "
            "Call request_proc_access before retrying blocked paths."
        )

    return {
        "normalized_path": normalized_path,
        "resolved_path": path_info["resolved_path"],
        "path_kind": path_info["path_kind"],
        "matched_allowed_root": matched_allowed_root or "",
    }


def clear_proc_snapshots() -> None:
    """Test helper to reset in-memory proc snapshots."""

    _ProcSnapshotStore.instance().clear()


def reset_proc_roots() -> None:
    """Test helper to restore the default proc roots."""

    ProcRootsService.instance().reset()


def _normalize_proc_path(path: str) -> str:
    raw_path = path.strip()
    if not raw_path:
        raise ValueError("Path is required.")
    if any(token in raw_path for token in _FORBIDDEN_TOKENS):
        raise ValueError("Unsafe path input is not allowed.")
    if "\x00" in raw_path:
        raise ValueError("Null bytes are not allowed in paths.")
    if not raw_path.startswith("/"):
        raise ValueError("Path must be absolute.")
    if ".." in Path(raw_path).parts:
        raise ValueError("Path traversal is not allowed.")

    normalized_path = os.path.normpath(raw_path)
    if not any(normalized_path == root or normalized_path.startswith(f"{root}/") for root in _SUPPORTED_ROOT_PREFIXES):
        raise ValueError("Only /proc and /sys paths are supported for Milestone 7 snapshots.")
    return normalized_path


def _read_path_info(path: str) -> dict[str, str]:
    try:
        stat_result = os.lstat(path)
    except FileNotFoundError as exc:
        raise ValueError(f"Path not found: {path}") from exc
    except OSError as exc:
        raise ValueError(f"Unable to inspect {path}: {exc}") from exc

    if stat.S_ISLNK(stat_result.st_mode):
        raise ValueError(f"Symlink paths are not allowed for snapshots: {path}")

    resolved_path = os.path.realpath(path)
    if not any(_is_path_within(resolved_path, root) for root in _SUPPORTED_ROOT_PREFIXES):
        raise ValueError(f"Resolved path escapes /proc or /sys: {path}")

    path_kind = "directory" if stat.S_ISDIR(stat_result.st_mode) else "file"
    return {"resolved_path": resolved_path, "path_kind": path_kind}


def _snapshot_entries(path: str, *, kind: str) -> tuple[ProcSnapshotEntry, ...]:
    if kind == "directory":
        return _snapshot_directory(path)
    return _snapshot_file(path)


def _snapshot_file(path: str) -> tuple[ProcSnapshotEntry, ...]:
    try:
        content = Path(path).read_text(encoding="utf-8", errors="replace")
    except PermissionError as exc:
        raise ValueError(f"Permission denied for {path}.") from exc
    except OSError as exc:
        raise ValueError(f"Unable to read {path}: {exc}") from exc

    entries = [
        ProcSnapshotEntry(
            entry_number=index,
            path=path,
            relative_path=Path(path).name,
            entry_type="line",
            line_number=index,
            text=line,
        )
        for index, line in enumerate(content.splitlines(), start=1)
    ]
    return tuple(entries)


def _snapshot_directory(path: str) -> tuple[ProcSnapshotEntry, ...]:
    entries: list[ProcSnapshotEntry] = []
    try:
        with os.scandir(path) as scanner:
            directory_entries = sorted(scanner, key=lambda item: item.name)
            for index, entry in enumerate(directory_entries, start=1):
                try:
                    stat_result = entry.stat(follow_symlinks=False)
                    entry_type = _classify_entry(entry, stat_result.st_mode)
                    size_bytes = int(stat_result.st_size)
                except OSError:
                    entry_type = "unreadable"
                    size_bytes = None
                entries.append(
                    ProcSnapshotEntry(
                        entry_number=index,
                        path=entry.path,
                        relative_path=entry.name,
                        entry_type=entry_type,
                        size_bytes=size_bytes,
                    )
                )
    except PermissionError as exc:
        raise ValueError(f"Permission denied for {path}.") from exc
    except OSError as exc:
        raise ValueError(f"Unable to read directory {path}: {exc}") from exc
    return tuple(entries)


def _classify_entry(entry: os.DirEntry[str], mode: int) -> str:
    if entry.is_symlink():
        return "symlink"
    if stat.S_ISDIR(mode):
        return "directory"
    if stat.S_ISREG(mode):
        return "file"
    return "other"


def _build_proc_access_message(path: str, reason: str | None) -> str:
    reason_suffix = f"\nReason: {reason.strip()}" if reason and reason.strip() else ""
    return (
        f"Allow read-only proc/sys access for {path}? "
        "This only expands the in-memory snapshot allow-list for the current server process."
        f"{reason_suffix}"
    )


def _build_proc_access_schema(path: str) -> dict[str, object]:
    return {
        "type": "object",
        "properties": {
            "root": {
                "type": "string",
                "title": "Proc/Sys Root",
                "description": "Choose whether to allow this additional read-only proc/sys root.",
                "oneOf": [
                    {"const": path, "title": f"Allow {path}"},
                    {"const": "__deny__", "title": "Deny access"},
                ],
            }
        },
        "required": ["root"],
        "additionalProperties": False,
    }


def _build_snapshot_uri(snapshot_id: str, *, limit: int | str | None = None, offset: int | str | None = None) -> str:
    base_uri = f"{RESOURCE_SCHEME}://snapshot/{snapshot_id}"
    if limit is None and offset is None:
        return base_uri

    resolved_limit = DEFAULT_PROC_RESOURCE_LIMIT if limit is None else limit
    resolved_offset = 0 if offset is None else offset
    return f"{base_uri}?limit={resolved_limit}&offset={resolved_offset}"


def _client_supports_form_elicitation(ctx: Context) -> bool:
    session = ctx.request_context.session
    return session.check_client_capability(
        types.ClientCapabilities(
            elicitation=types.ElicitationCapability(form=types.FormElicitationCapability())
        )
    )


def _is_path_within(path: str, root: str) -> bool:
    return path == root or path.startswith(f"{root}/")
