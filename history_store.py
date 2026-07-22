"""
Persistent scan history stored as a local JSON file.

Keeps a bounded list of recent scans so the UI and CLI can show
repositories that were analyzed previously without a database.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from models import ScanResult

# History lives next to the project under data/
DATA_DIR = Path(__file__).resolve().parent / "data"
HISTORY_PATH = DATA_DIR / "history.json"
MAX_ENTRIES = 100


def _ensure_store() -> None:
    """Create the data directory and empty history file if needed."""
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    if not HISTORY_PATH.exists():
        HISTORY_PATH.write_text("[]", encoding="utf-8")


def load_history() -> list[dict[str, Any]]:
    """Return all history entries (newest first)."""
    _ensure_store()
    try:
        raw = HISTORY_PATH.read_text(encoding="utf-8")
        data = json.loads(raw or "[]")
        if isinstance(data, list):
            return data
    except (json.JSONDecodeError, OSError):
        return []
    return []


def save_history(entries: list[dict[str, Any]]) -> None:
    """Overwrite history with the given entries list."""
    _ensure_store()
    # Keep only the most recent MAX_ENTRIES
    trimmed = entries[:MAX_ENTRIES]
    HISTORY_PATH.write_text(
        json.dumps(trimmed, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def append_scan(result: ScanResult) -> None:
    """
    Prepend a scan result to history.

    If the same owner/repo already exists, the old entry is removed first
    so the list stays unique by repository and shows the latest scan.
    """
    entries = load_history()
    key = f"{result.owner}/{result.repo}".lower()
    entries = [
        e
        for e in entries
        if f"{e.get('owner', '')}/{e.get('repo', '')}".lower() != key
    ]
    entries.insert(0, result.to_history_entry())
    save_history(entries)


def clear_history() -> None:
    """Delete all history entries."""
    save_history([])
