"""
Runtime configuration for GitHub License Scanner.

All sensitive or environment-specific values are read from environment
variables (optionally loaded from a local .env file). Defaults are safe
for local development only.
"""

from __future__ import annotations

import os
import secrets
import warnings
from pathlib import Path

# Load .env if python-dotenv is available (optional dependency)
try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent / ".env")
except ImportError:
    pass

# ---------------------------------------------------------------------------
# Server
# ---------------------------------------------------------------------------

HOST: str = os.environ.get("GLS_HOST", "127.0.0.1")
PORT: int = int(os.environ.get("GLS_PORT", "8080"))
# When True, open browser on start (local UX). Disable in containers/CI.
SHOW_BROWSER: bool = os.environ.get("GLS_SHOW_BROWSER", "1").strip().lower() not in {
    "0",
    "false",
    "no",
}

# ---------------------------------------------------------------------------
# Session signing secret (CRITICAL for multi-user / public deploys)
# ---------------------------------------------------------------------------

_DEFAULT_DEV_SECRET = "github-license-scanner-dev-only-not-for-production"


def _resolve_storage_secret() -> str:
    """
    Resolve NiceGUI storage_secret.

    Prefer GLS_STORAGE_SECRET / NICEGUI_STORAGE_SECRET.
    In production-like hosts (0.0.0.0), refuse the insecure default.
    """
    secret = (
        os.environ.get("GLS_STORAGE_SECRET")
        or os.environ.get("NICEGUI_STORAGE_SECRET")
        or ""
    ).strip()
    if secret:
        return secret

    host = os.environ.get("GLS_HOST", "127.0.0.1").strip()
    if host in {"0.0.0.0", "::", "[::]"}:
        # Generate an ephemeral secret so the process still starts, but warn:
        # sessions will not survive restarts and operators must set a fixed secret.
        generated = secrets.token_urlsafe(48)
        warnings.warn(
            "GLS_STORAGE_SECRET is not set while binding a public interface. "
            "Using an ephemeral secret (sessions reset on restart). "
            "Set GLS_STORAGE_SECRET to a long random value in production.",
            stacklevel=2,
        )
        return generated

    warnings.warn(
        "Using development storage_secret. Set GLS_STORAGE_SECRET before "
        "any multi-user or public deployment.",
        stacklevel=2,
    )
    return _DEFAULT_DEV_SECRET


STORAGE_SECRET: str = _resolve_storage_secret()

# ---------------------------------------------------------------------------
# Abuse / resource limits
# ---------------------------------------------------------------------------

# Max concurrent registry lookups (also in analyzer; kept here for docs)
MAX_CONCURRENT_LOOKUPS: int = int(os.environ.get("GLS_MAX_CONCURRENT_LOOKUPS", "12"))
MAX_PACKAGES_LOOKUP: int = int(os.environ.get("GLS_MAX_PACKAGES_LOOKUP", "80"))
MAX_DEPENDENCY_FILES: int = int(os.environ.get("GLS_MAX_DEPENDENCY_FILES", "30"))
MAX_BATCH_URLS: int = int(os.environ.get("GLS_MAX_BATCH_URLS", "15"))

# Scan rate limit per client key (IP / session): N scans per window
RATE_LIMIT_SCANS: int = int(os.environ.get("GLS_RATE_LIMIT_SCANS", "20"))
RATE_LIMIT_WINDOW_SECONDS: int = int(os.environ.get("GLS_RATE_LIMIT_WINDOW", "3600"))

# In-process registry license cache
LICENSE_CACHE_TTL_SECONDS: int = int(os.environ.get("GLS_LICENSE_CACHE_TTL", "3600"))
LICENSE_CACHE_MAX_ENTRIES: int = int(os.environ.get("GLS_LICENSE_CACHE_MAX", "2000"))

# History retention
HISTORY_MAX_ENTRIES: int = int(os.environ.get("GLS_HISTORY_MAX", "100"))
# Auto-prune history entries older than this many days (0 = disabled)
HISTORY_MAX_AGE_DAYS: int = int(os.environ.get("GLS_HISTORY_MAX_AGE_DAYS", "90"))

# ---------------------------------------------------------------------------
# GitHub
# ---------------------------------------------------------------------------

GITHUB_TOKEN: str | None = (
    os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN") or None
)

USER_AGENT: str = os.environ.get(
    "GLS_USER_AGENT",
    "github-license-scanner/1.2 (+https://github.com/NezbiT/github-license-scanner; educational)",
)

# ---------------------------------------------------------------------------
# Multi-user authentication (web UI)
# ---------------------------------------------------------------------------

AUTH_ENABLED: bool = os.environ.get("GLS_AUTH_ENABLED", "").strip().lower() in {
    "1",
    "true",
    "yes",
    "on",
}
# JSON file of {username: {salt, hash, iterations}} — see auth.py
USERS_FILE: str = os.environ.get(
    "GLS_USERS_FILE",
    str(Path(__file__).resolve().parent / "data" / "users.json"),
)
