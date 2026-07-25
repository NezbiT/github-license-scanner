"""
Optional multi-user authentication for the web UI.

When GLS_AUTH_ENABLED is true, the NiceGUI app requires a login.
Each user gets an isolated history file under data/history/<user>.json.

Password storage uses PBKDF2-HMAC-SHA256 (stdlib only).
Users file format (JSON):
  {
    "alice": {"salt": "hex", "hash": "hex", "iterations": 200000},
    ...
  }

CLI:
  python auth.py hash-password
  python auth.py add-user alice
  python auth.py list-users
"""

from __future__ import annotations

import getpass
import hashlib
import json
import os
import re
import secrets
import sys
import tempfile
from pathlib import Path
from typing import Any

try:
    from config import DATA_DIR  # type: ignore
except Exception:  # noqa: BLE001
    DATA_DIR = Path(__file__).resolve().parent / "data"

USERS_PATH = Path(
    os.environ.get("GLS_USERS_FILE")
    or (Path(__file__).resolve().parent / "data" / "users.json")
)

DEFAULT_ITERATIONS = 200_000
USERNAME_RE = re.compile(r"^[A-Za-z0-9_.-]{1,64}$")


def auth_enabled() -> bool:
    """Return True when multi-user auth is required for the web UI."""
    return os.environ.get("GLS_AUTH_ENABLED", "").strip().lower() in {
        "1",
        "true",
        "yes",
        "on",
    }


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(path.parent), prefix=".users_", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        Path(tmp).replace(path)
    except Exception:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def load_users() -> dict[str, dict[str, Any]]:
    """Load users database (empty dict if missing)."""
    if not USERS_PATH.exists():
        return {}
    try:
        data = json.loads(USERS_PATH.read_text(encoding="utf-8") or "{}")
        return data if isinstance(data, dict) else {}
    except (json.JSONDecodeError, OSError):
        return {}


def save_users(users: dict[str, dict[str, Any]]) -> None:
    _atomic_write(USERS_PATH, json.dumps(users, indent=2, ensure_ascii=False))


def hash_password(password: str, *, salt: bytes | None = None, iterations: int = DEFAULT_ITERATIONS) -> dict[str, Any]:
    """Create a password record."""
    if not password or len(password) < 8:
        raise ValueError("Password must be at least 8 characters")
    salt = salt or secrets.token_bytes(16)
    dk = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return {
        "salt": salt.hex(),
        "hash": dk.hex(),
        "iterations": iterations,
    }


def verify_password(password: str, record: dict[str, Any]) -> bool:
    """Constant-time-ish verify of password against stored record."""
    try:
        salt = bytes.fromhex(record["salt"])
        expected = bytes.fromhex(record["hash"])
        iterations = int(record.get("iterations") or DEFAULT_ITERATIONS)
    except (KeyError, ValueError, TypeError):
        return False
    got = hashlib.pbkdf2_hmac("sha256", password.encode("utf-8"), salt, iterations)
    return secrets.compare_digest(got, expected)


def authenticate(username: str, password: str) -> bool:
    """Return True if credentials are valid."""
    user = (username or "").strip()
    if not user or not password:
        return False
    users = load_users()
    rec = users.get(user)
    if not rec:
        # Also try case-insensitive match
        for k, v in users.items():
            if k.lower() == user.lower():
                rec = v
                user = k
                break
    if not rec:
        # Dummy work to reduce timing oracle on missing users
        hash_password("dummy-password-xx", salt=b"\x00" * 16)
        return False
    return verify_password(password, rec)


def add_user(username: str, password: str) -> None:
    """Create or update a user password."""
    user = (username or "").strip()
    if not USERNAME_RE.match(user):
        raise ValueError(
            "Username must be 1–64 chars: letters, digits, _ . -"
        )
    users = load_users()
    users[user] = hash_password(password)
    save_users(users)


def delete_user(username: str) -> bool:
    users = load_users()
    if username in users:
        del users[username]
        save_users(users)
        return True
    return False


def list_usernames() -> list[str]:
    return sorted(load_users().keys())


def normalize_username(username: str) -> str:
    return (username or "").strip()


def history_user_key(username: str | None) -> str | None:
    """
    Return a filesystem-safe history key.

    None means shared/local anonymous history (auth disabled).
    """
    if not username:
        return None
    u = normalize_username(username)
    if not USERNAME_RE.match(u):
        return None
    return u.lower()


# ---------------------------------------------------------------------------
# CLI helpers
# ---------------------------------------------------------------------------

def _cli(argv: list[str]) -> int:
    if len(argv) < 2 or argv[1] in {"-h", "--help"}:
        print(__doc__)
        return 0
    cmd = argv[1]
    if cmd == "list-users":
        names = list_usernames()
        if not names:
            print("No users. Create one with: python auth.py add-user <name>")
            print(f"Users file: {USERS_PATH}")
            return 0
        for n in names:
            print(n)
        return 0
    if cmd == "add-user":
        if len(argv) < 3:
            print("Usage: python auth.py add-user <username>", file=sys.stderr)
            return 2
        username = argv[2]
        pw = getpass.getpass("Password: ")
        pw2 = getpass.getpass("Confirm: ")
        if pw != pw2:
            print("Passwords do not match", file=sys.stderr)
            return 2
        try:
            add_user(username, pw)
        except ValueError as exc:
            print(exc, file=sys.stderr)
            return 2
        print(f"User {username!r} saved to {USERS_PATH}")
        print("Enable auth with GLS_AUTH_ENABLED=1")
        return 0
    if cmd == "hash-password":
        pw = getpass.getpass("Password: ")
        rec = hash_password(pw)
        print(json.dumps(rec, indent=2))
        return 0
    if cmd == "delete-user":
        if len(argv) < 3:
            print("Usage: python auth.py delete-user <username>", file=sys.stderr)
            return 2
        ok = delete_user(argv[2])
        print("Deleted" if ok else "Not found")
        return 0 if ok else 1
    print(f"Unknown command: {cmd}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    raise SystemExit(_cli(sys.argv))
