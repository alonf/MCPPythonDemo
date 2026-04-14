"""Linux log snapshot tools and resource helpers for Milestone 3."""

from __future__ import annotations

import json
from collections import deque
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from threading import Lock
from typing import ClassVar
from uuid import uuid4

from pydantic import BaseModel

DEFAULT_LOG_SNAPSHOT_LINES = 200
DEFAULT_RESOURCE_LIMIT = 50
MAX_RESOURCE_LIMIT = 500
RESOURCE_SCHEME = "syslog"

LOG_SOURCE_CANDIDATES: dict[str, tuple[Path, ...]] = {
    "system": (Path("/var/log/syslog"), Path("/var/log/messages")),
    "security": (Path("/var/log/auth.log"), Path("/var/log/secure")),
    "kernel": (Path("/var/log/kern.log"), Path("/var/log/dmesg")),
    "package": (Path("/var/log/dpkg.log"),),
}


class LogSnapshotLine(BaseModel):
    """One captured log line."""

    line_number: int
    text: str


class LogSnapshotPagination(BaseModel):
    """Pagination metadata returned with every resource read."""

    total_count: int
    returned_count: int
    limit: int
    offset: int
    has_more: bool
    next_offset: int | None


class LogSnapshotSummary(BaseModel):
    """Result returned by the snapshot tool."""

    snapshot_id: str
    log_name: str
    source_path: str
    filter_text: str | None
    created_at_utc: str
    line_count: int
    resource_uri: str
    paginated_resource_template: str


class LogSnapshotPage(BaseModel):
    """Paged resource payload for one log snapshot."""

    snapshot_id: str
    log_name: str
    source_path: str
    filter_text: str | None
    created_at_utc: str
    line_count: int
    lines: list[LogSnapshotLine]
    pagination: LogSnapshotPagination


@dataclass(slots=True)
class _StoredSnapshot:
    snapshot_id: str
    log_name: str
    source_path: str
    filter_text: str | None
    created_at_utc: str
    lines: tuple[LogSnapshotLine, ...] = field(default_factory=tuple)

    @property
    def line_count(self) -> int:
        return len(self.lines)


class _LogSnapshotStore:
    """Thread-safe in-memory snapshot storage."""

    _snapshots: dict[str, _StoredSnapshot]
    _lock: Lock
    _instance: ClassVar[_LogSnapshotStore | None] = None

    def __init__(self) -> None:
        self._snapshots = {}
        self._lock = Lock()

    @classmethod
    def instance(cls) -> _LogSnapshotStore:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def save(self, snapshot: _StoredSnapshot) -> None:
        with self._lock:
            self._snapshots[snapshot.snapshot_id] = snapshot

    def get(self, snapshot_id: str) -> _StoredSnapshot | None:
        with self._lock:
            return self._snapshots.get(snapshot_id)

    def clear(self) -> None:
        with self._lock:
            self._snapshots.clear()


def create_log_snapshot(
    log_name: str | None = None,
    *,
    filter_text: str | None = None,
    max_lines: int | None = None,
) -> LogSnapshotSummary:
    """Create a read-only snapshot from a common Linux log file."""

    resolved_max_lines = _validate_max_lines(max_lines)
    resolved_log_name, source_path = _resolve_log_source(log_name)
    lines = _read_matching_lines(source_path, filter_text=filter_text, max_lines=resolved_max_lines)
    snapshot_id = uuid4().hex
    snapshot = _StoredSnapshot(
        snapshot_id=snapshot_id,
        log_name=resolved_log_name,
        source_path=str(source_path),
        filter_text=filter_text.strip() if filter_text else None,
        created_at_utc=datetime.now(UTC).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
        lines=lines,
    )
    _LogSnapshotStore.instance().save(snapshot)
    return LogSnapshotSummary(
        snapshot_id=snapshot.snapshot_id,
        log_name=snapshot.log_name,
        source_path=snapshot.source_path,
        filter_text=snapshot.filter_text,
        created_at_utc=snapshot.created_at_utc,
        line_count=snapshot.line_count,
        resource_uri=_build_snapshot_uri(snapshot.snapshot_id),
        paginated_resource_template=_build_snapshot_uri(snapshot.snapshot_id, limit="{limit}", offset="{offset}"),
    )


def render_log_snapshot_resource(snapshot_id: str, *, limit: int = DEFAULT_RESOURCE_LIMIT, offset: int = 0) -> str:
    """Render a snapshot resource as JSON text."""

    page = get_log_snapshot_page(snapshot_id, limit=limit, offset=offset)
    return json.dumps(page.model_dump(mode="json"), indent=2, sort_keys=True)


def get_log_snapshot_page(snapshot_id: str, *, limit: int = DEFAULT_RESOURCE_LIMIT, offset: int = 0) -> LogSnapshotPage:
    """Return one paged slice of a stored snapshot."""

    if limit <= 0:
        raise ValueError("limit must be greater than zero.")
    if offset < 0:
        raise ValueError("offset must be zero or greater.")

    resolved_limit = min(limit, MAX_RESOURCE_LIMIT)
    snapshot = _LogSnapshotStore.instance().get(snapshot_id)
    if snapshot is None:
        raise ValueError(f"No log snapshot found for id '{snapshot_id}'.")

    page_lines = list(snapshot.lines[offset : offset + resolved_limit])
    returned_count = len(page_lines)
    total_count = snapshot.line_count
    next_offset = offset + returned_count if (offset + returned_count) < total_count else None
    pagination = LogSnapshotPagination(
        total_count=total_count,
        returned_count=returned_count,
        limit=resolved_limit,
        offset=offset,
        has_more=next_offset is not None,
        next_offset=next_offset,
    )
    return LogSnapshotPage(
        snapshot_id=snapshot.snapshot_id,
        log_name=snapshot.log_name,
        source_path=snapshot.source_path,
        filter_text=snapshot.filter_text,
        created_at_utc=snapshot.created_at_utc,
        line_count=total_count,
        lines=page_lines,
        pagination=pagination,
    )


def clear_log_snapshots() -> None:
    """Test helper to reset in-memory snapshots."""

    _LogSnapshotStore.instance().clear()


def _validate_max_lines(max_lines: int | None) -> int:
    resolved = DEFAULT_LOG_SNAPSHOT_LINES if max_lines is None else max_lines
    if resolved <= 0:
        raise ValueError("max_lines must be greater than zero.")
    return min(resolved, 1_000)


def _resolve_log_source(log_name: str | None) -> tuple[str, Path]:
    available_sources = {
        name: path
        for name, candidates in LOG_SOURCE_CANDIDATES.items()
        for path in candidates
        if path.exists() and path.is_file()
    }
    if log_name is None:
        if not available_sources:
            raise ValueError("No supported Linux log files were found.")
        first_available = next(iter(available_sources.items()))
        return first_available

    normalized_name = log_name.strip().lower()
    if normalized_name not in LOG_SOURCE_CANDIDATES:
        supported = ", ".join(sorted(LOG_SOURCE_CANDIDATES))
        raise ValueError(f"Unsupported log_name '{log_name}'. Choose one of: {supported}.")

    for candidate in LOG_SOURCE_CANDIDATES[normalized_name]:
        if candidate.exists() and candidate.is_file():
            return normalized_name, candidate

    raise ValueError(f"No readable log file is available for '{normalized_name}' on this machine.")


def _read_matching_lines(path: Path, *, filter_text: str | None, max_lines: int) -> tuple[LogSnapshotLine, ...]:
    needle = filter_text.strip().lower() if filter_text and filter_text.strip() else None
    recent_lines: deque[LogSnapshotLine] = deque(maxlen=max_lines)
    with path.open("r", encoding="utf-8", errors="replace") as handle:
        for line_number, raw_line in enumerate(handle, start=1):
            line = raw_line.rstrip("\n")
            if needle is not None and needle not in line.lower():
                continue
            recent_lines.append(LogSnapshotLine(line_number=line_number, text=line))
    return tuple(recent_lines)


def _build_snapshot_uri(snapshot_id: str, *, limit: int | str | None = None, offset: int | str | None = None) -> str:
    base_uri = f"{RESOURCE_SCHEME}://snapshot/{snapshot_id}"
    if limit is None and offset is None:
        return base_uri

    resolved_limit = DEFAULT_RESOURCE_LIMIT if limit is None else limit
    resolved_offset = 0 if offset is None else offset
    return f"{base_uri}?limit={resolved_limit}&offset={resolved_offset}"
