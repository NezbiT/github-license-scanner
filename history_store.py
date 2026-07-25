"""
Persistent scan history stored as a local JSON file.

Keeps a bounded list of recent scans so the UI and CLI can show
repositories that were analyzed previously without a database.

Privacy notes:
  - History is stored on the machine running the app (local disk).
  - In a multi-user deployment this file is shared by all users of that
    instance — do not treat it as private per-user data unless you add
    authentication and per-user stores.
  - Entries are pruned by count and optional max age (see config).
"""

from __future__ import annotations

import json
import os
import tempfile
import threading
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from models import ScanResult

try:
    from config import HISTORY_MAX_AGE_DAYS, HISTORY_MAX_ENTRIES
except Exception:  # noqa: BLE001 — allow import during partial bootstrap
    HISTORY_MAX_ENTRIES = 100
    HISTORY_MAX_AGE_DAYS = 90

# History lives next to the project under data/
DATA_DIR = Path(__file__).resolve().parent / "data"
HISTORY_PATH = DATA_DIR / "history.json"

# Process-local lock (multi-process still needs external coordination)
_lock = threading.Lock()


def _ensure_store() -> None:
    """Create the data directory and empty history file if needed."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not HISTORY_PATH.exists():
        _atomic_write(HISTORY_PATH, "[]")


def _atomic_write(path: Path, text: str) -> None:
    """Write via temp file + replace to reduce partial-write corruption."""
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


def _parse_scanned_at(value: Any) -> datetime | None:
    """Best-effort parse of history timestamps."""
    if not value or not isinstance(value, str):
        return None
    text = value.strip()
    # Expected: "2026-07-24 12:00:00 UTC"
    for fmt in ("%Y-%m-%d %H:%M:%S UTC", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%d"):
        try:
            if fmt.endswith("%z") and text.endswith("Z"):
                text = text[:-1] + "+0000"
            dt = datetime.strptime(text.replace(" UTC", ""), fmt.replace(" UTC", ""))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except ValueError:
            continue
    return None


def _prune(entries: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Apply max-age and max-count retention policies."""
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


def load_history() -> list[dict[str, Any]]:
    """Return all history entries (newest first), after retention prune."""
    with _lock:
        _ensure_store()
        try:
            raw = HISTORY_PATH.read_text(encoding="utf-8")
            data = json.loads(raw or "[]")
            if not isinstance(data, list):
                return []
            pruned = _prune(data)
            # Persist prune if it removed rows (lazy cleanup)
            if len(pruned) != len(data):
                _atomic_write(
                    HISTORY_PATH,
                    json.dumps(pruned, indent=2, ensure_ascii=False),
                )
            return pruned
        except (json.JSONDecodeError, OSError):
            return []


def save_history(entries: list[dict[str, Any]]) -> None:
    """Overwrite history with the given entries list."""
    with _lock:
        _ensure_store()
        trimmed = _prune(entries)
        _atomic_write(
            HISTORY_PATH,
            json.dumps(trimmed, indent=2, ensure_ascii=False),
        )


def append_scan(result: ScanResult) -> None:
    """
    Prepend a scan result to history.

    If the same owner/repo already exists, the old entry is removed first
    so the list stays unique by repository and shows the latest scan.
    Incomplete scans (no owner) are not stored.
    """
    if not result.owner or not result.repo:
        return
    with _lock:
        _ensure_store()
        try:
            raw = HISTORY_PATH.read_text(encoding="utf-8")
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
            HISTORY_PATH,
            json.dumps(trimmed, indent=2, ensure_ascii=False),
        )


def clear_history() -> None:
    """Delete all history entries (local erasure / privacy control)."""
    save_history([])
