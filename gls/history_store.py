"""
Persistent scan history stored as local JSON file(s).

Files live in the per-user data directory (platformdirs), never inside the
installed package and never in the current working directory.

Privacy notes:
  - Without auth: single shared file <data_dir>/history.json (local/dev).
  - With multi-user auth: <data_dir>/history/<username>.json per user.
  - Entries are pruned by count and optional max age (see config).
"""

from __future__ import annotations

import json
import os
import re
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .models import ScanResult

try:
    from .config import DATA_DIR, HISTORY_MAX_AGE_DAYS, HISTORY_MAX_ENTRIES
except Exception:  # noqa: BLE001
    from platformdirs import user_data_dir

    HISTORY_MAX_ENTRIES = 100
    HISTORY_MAX_AGE_DAYS = 90
    DATA_DIR = Path(user_data_dir("github-license-scanner", "NezbiT"))

HISTORY_PATH = DATA_DIR / "history.json"
HISTORY_USERS_DIR = DATA_DIR / "history"

_lock = threading.Lock()
_SAFE_USER = re.compile(r"^[a-z0-9_.-]{1,64}$")


def _ensure_store(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        _atomic_write(path, "[]")


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        dir=str(path.parent),
        prefix=".history_",
        suffix=".tmp",
    )
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        Path(tmp_name).replace(path)
    except Exception:
        try:
            os.unlink(tmp_name)
        except OSError:
            pass
        raise


def history_path_for(user: str | None = None) -> Path:
    """Resolve history file path for optional authenticated user."""
    if user:
        key = user.strip().lower()
        if not _SAFE_USER.match(key):
            raise ValueError(f"Invalid history user key: {user!r}")
        return HISTORY_USERS_DIR / f"{key}.json"
    return HISTORY_PATH


def _parse_scanned_at(value: Any) -> datetime | None:
    if not value or not isinstance(value, str):
        return None
    text = value.strip()
    for fmt in ("%Y-%m-%d %H:%M:%S UTC", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d"):
        try:
            candidate = text
            if fmt.endswith("%z") and candidate.endswith("Z"):
                candidate = candidate[:-1] + "+0000"
            dt = datetime.strptime(
                candidate.replace(" UTC", ""),
                fmt.replace(" UTC", ""),
            )
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    return None


def _prune(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    if HISTORY_MAX_AGE_DAYS and HISTORY_MAX_AGE_DAYS > 0:
        cutoff = datetime.now(timezone.utc).timestamp() - (
            HISTORY_MAX_AGE_DAYS * 24 * 3600
        )
        kept: list[dict[str, Any]] = []
        for e in entries:
            dt = _parse_scanned_at(e.get("scanned_at"))
            if dt is None or dt.timestamp() >= cutoff:
                kept.append(e)
        entries = kept
    return entries[:HISTORY_MAX_ENTRIES]


def load_history(user: str | None = None) -> list[dict[str, Any]]:
    """Return history entries (newest first) for the given user scope."""
    path = history_path_for(user)
    with _lock:
        _ensure_store(path)
        try:
            raw = path.read_text(encoding="utf-8")
            data = json.loads(raw or "[]")
            if not isinstance(data, list):
                return []
            pruned = _prune(data)
            if len(pruned) != len(data):
                _atomic_write(
                    path,
                    json.dumps(pruned, indent=2, ensure_ascii=False),
                )
            return pruned
        except (json.JSONDecodeError, OSError):
            return []


def save_history(entries: list[dict[str, Any]], user: str | None = None) -> None:
    path = history_path_for(user)
    with _lock:
        _ensure_store(path)
        trimmed = _prune(entries)
        _atomic_write(
            path,
            json.dumps(trimmed, indent=2, ensure_ascii=False),
        )


def append_scan(result: ScanResult, user: str | None = None) -> None:
    """Prepend a complete scan; unique by owner/repo within the user scope."""
    if not result.owner or not result.repo:
        return
    path = history_path_for(user)
    with _lock:
        _ensure_store(path)
        try:
            raw = path.read_text(encoding="utf-8")
            entries = json.loads(raw or "[]")
            if not isinstance(entries, list):
                entries = []
        except (json.JSONDecodeError, OSError):
            entries = []

        key = f"{result.owner}/{result.repo}".lower()
        entries = [
            e
            for e in entries
            if f"{e.get('owner', '')}/{e.get('repo', '')}".lower() != key
        ]
        entries.insert(0, result.to_history_entry())
        trimmed = _prune(entries)
        _atomic_write(
            path,
            json.dumps(trimmed, indent=2, ensure_ascii=False),
        )


def clear_history(user: str | None = None) -> None:
    """Erase history for the given scope."""
    save_history([], user=user)
