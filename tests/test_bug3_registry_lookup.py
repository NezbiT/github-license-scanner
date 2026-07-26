"""
Bug 3 — crates.io licenses live in versions[].license, not crate.license.

`crate` has no `license` key at all, so the old lookup returned None for
every crate that has ever existed. Also locks in SPDX compound-expression
handling (OR / AND) for cargo and npm.
"""

from __future__ import annotations

import pytest

from gls.license_analyzer import _extract_cargo_license, classify_license


# --------------------------------------------------------------------------
# crates.io payload shape
# --------------------------------------------------------------------------

AUTOCFG = {
    "crate": {
        "name": "autocfg",
        "default_version": "1.5.1",
        "max_stable_version": "1.5.1",
        "newest_version": "1.5.1",
        # note: no "license" key — this is the real payload shape
    },
    "versions": [
        {"num": "1.5.1", "license": "Apache-2.0 OR MIT", "yanked": False},
        {"num": "1.5.0", "license": "Apache-2.0 OR MIT", "yanked": False},
    ],
}


def test_extracts_license_from_versions_array():
    assert _extract_cargo_license(AUTOCFG) == "Apache-2.0 OR MIT"


def test_prefers_the_default_version():
    payload = {
        "crate": {"name": "x", "default_version": "1.0.0"},
        "versions": [
            {"num": "2.0.0-beta", "license": "GPL-3.0", "yanked": False},
            {"num": "1.0.0", "license": "MIT", "yanked": False},
        ],
    }
    assert _extract_cargo_license(payload) == "MIT"


def test_skips_yanked_versions():
    payload = {
        "crate": {"name": "x"},
        "versions": [
            {"num": "9.9.9", "license": "GPL-3.0", "yanked": True},
            {"num": "1.0.0", "license": "MIT", "yanked": False},
        ],
    }
    assert _extract_cargo_license(payload) == "MIT"


def test_missing_license_returns_none():
    payload = {"crate": {"name": "x"}, "versions": [{"num": "1.0.0", "yanked": False}]}
    assert _extract_cargo_license(payload) is None
    assert _extract_cargo_license({}) is None


# --------------------------------------------------------------------------
# SPDX compound expressions
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "expression,expected",
    [
        # OR — the user picks, so classify by the least restrictive option
        ("MIT OR Apache-2.0", "permissive"),
        ("Apache-2.0 OR MIT", "permissive"),
        ("(MIT OR Apache-2.0)", "permissive"),
        ("GPL-2.0 OR MIT", "permissive"),
        ("MIT/Apache-2.0", "permissive"),
        # AND — all apply, so classify by the most restrictive
        ("GPL-2.0 AND MIT", "strong_copyleft"),
        ("MIT AND GPL-3.0", "strong_copyleft"),
        ("MIT AND LGPL-2.1", "weak_copyleft"),
        # WITH — an exception does not lower the base risk
        ("GPL-2.0 WITH Linux-syscall-note", "strong_copyleft"),
        # single ids still work
        ("MIT", "permissive"),
        ("AGPL-3.0", "strong_copyleft"),
    ],
)
def test_compound_expression_classification(expression, expected):
    assert classify_license(expression) == expected


# --------------------------------------------------------------------------
# End to end: the four crates from the git/git scan
# --------------------------------------------------------------------------

def test_git_cargo_dependencies_resolve(replay):
    """
    All four crates in git/git came back Unknown. Every one of them has a
    clear public license on crates.io.
    """
    result = replay.scan("git__git", "git/git")
    cargo = {p.name: p for p in result.packages if p.ecosystem == "cargo"}

    assert cargo, "expected cargo dependencies in the git/git fixture"
    unresolved = sorted(n for n, p in cargo.items() if p.license_id is None)
    assert not unresolved, f"unresolved crates: {unresolved}"
    assert not [n for n, p in cargo.items() if p.risk == "unknown"]


@pytest.mark.parametrize(
    "crate,license_id,risk",
    [
        ("autocfg", "Apache-2.0 OR MIT", "permissive"),
        ("libz-sys", "MIT OR Apache-2.0", "permissive"),
        ("make-cmd", "MIT", "permissive"),
        # git's own crate really is GPL-2.0-only — resolving it correctly is
        # the point, not classifying everything as permissive.
        ("libgit-sys", "GPL-2.0-only", "strong_copyleft"),
    ],
)
def test_git_crates_resolve_to_their_real_licenses(replay, crate, license_id, risk):
    result = replay.scan("git__git", "git/git")
    pkg = next((p for p in result.packages if p.name == crate), None)

    assert pkg is not None, f"{crate} missing from the scan"
    assert pkg.license_id == license_id
    assert pkg.risk == risk
