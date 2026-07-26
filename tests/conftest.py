"""
Offline test harness.

Every HTTP call is served from a recorded fixture in tests/fixtures/*.json,
so the suite never touches the network. Fixtures were captured by
scripts/record_fixtures.py against the live GitHub / registry APIs and
trimmed to the fields the scanner actually reads.

A request with no recorded response is a hard error rather than a silent
404 — an unrecorded call means the code under test changed which endpoints
it hits, and that must be an explicit fixture update.
"""

from __future__ import annotations

import asyncio
import json
from pathlib import Path

import httpx
import pytest

from gls import cli, license_analyzer
from gls.models import ScanResult

FIXTURE_DIR = Path(__file__).parent / "fixtures"


class UnrecordedRequest(AssertionError):
    """Raised when the code under test hits an endpoint with no fixture."""


def load_fixture(name: str) -> dict[str, dict]:
    """Load a recorded response map keyed by absolute request URL."""
    path = FIXTURE_DIR / f"{name}.json"
    if not path.exists():
        raise FileNotFoundError(f"No fixture {name!r} in {FIXTURE_DIR}")
    return json.loads(path.read_text(encoding="utf-8"))


def build_transport(entries: dict[str, dict]) -> httpx.MockTransport:
    """Build a MockTransport that replays `entries` and records what was hit."""

    def handler(request: httpx.Request) -> httpx.Response:
        url = str(request.url)
        entry = entries.get(url)
        if entry is None:
            raise UnrecordedRequest(
                f"No recorded response for {request.method} {url}.\n"
                f"Re-run scripts/record_fixtures.py if the scanner now needs "
                f"this endpoint."
            )
        body = entry.get("json")
        return httpx.Response(
            entry.get("status", 200),
            json=body if body is not None else {},
            request=request,
        )

    return httpx.MockTransport(handler)


@pytest.fixture(autouse=True)
def _clear_license_cache():
    """The registry lookup cache is process-global; isolate every test."""
    license_analyzer._license_cache.clear()
    yield
    license_analyzer._license_cache.clear()


class Replay:
    """Runs the real scan pipeline against a recorded fixture."""

    def __init__(self, monkeypatch: pytest.MonkeyPatch) -> None:
        self._monkeypatch = monkeypatch
        # Captured once: a test may replay several fixtures in turn, and
        # re-reading these after patching would close over the previous
        # fixture's transport.
        self._real_github_client = license_analyzer.create_client
        self._real_registry_client = license_analyzer.create_registry_client

    def _install(self, fixture: str) -> None:
        transport = build_transport(load_fixture(fixture))
        gh, registry = self._real_github_client, self._real_registry_client
        self._monkeypatch.setattr(
            license_analyzer,
            "create_client",
            lambda *a, **k: gh(transport=transport),
        )
        self._monkeypatch.setattr(
            license_analyzer,
            "create_registry_client",
            lambda *a, **k: registry(transport=transport),
        )
        # The registry cache is keyed by (ecosystem, name) only, so results
        # from a previous fixture would leak across a fixture swap.
        license_analyzer._license_cache.clear()

    def scan(self, fixture: str, url: str) -> ScanResult:
        """Return the ScanResult for `url`, served entirely from fixtures."""
        self._install(fixture)
        return asyncio.run(license_analyzer.analyze_repository(url))

    def exit_code(self, fixture: str, url: str) -> int:
        """Return the real CLI exit code for `url`, served from fixtures."""
        self._install(fixture)
        return asyncio.run(cli.cmd_scan(url, save=False, verbose=False))


@pytest.fixture
def replay(monkeypatch: pytest.MonkeyPatch) -> Replay:
    return Replay(monkeypatch)
