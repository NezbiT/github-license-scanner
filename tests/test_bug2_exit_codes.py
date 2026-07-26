"""
Bug 2 — exit code, risk score and verdict text must tell the same story.

Precedence:
  1 — strong copyleft (GPL/AGPL/SSPL) in the repo or a production dependency
  2 — any production dependency unknown, or repo license unresolved
  0 — everything resolved, no strong copyleft
"""

from __future__ import annotations

import pytest


# --------------------------------------------------------------------------
# Exit codes
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "fixture,url",
    [
        ("git__git", "git/git"),
        ("torvalds__linux", "torvalds/linux"),
        ("mongodb__mongo", "mongodb/mongo"),
    ],
)
def test_strong_copyleft_exits_1(replay, fixture, url):
    assert replay.exit_code(fixture, url) == 1


def test_fully_resolved_permissive_exits_0(replay):
    assert replay.exit_code("psf__requests", "psf/requests") == 0


def test_unknown_production_dependency_exits_2(replay):
    """Permissive repo license, but two production deps cannot be resolved."""
    assert replay.exit_code("synthetic__unknown_prod", "acme/widget") == 2


def test_unknown_dev_dependency_alone_exits_0(replay):
    """Dev-only unknowns are reported but must not gate the build."""
    assert replay.exit_code("synthetic__unknown_dev", "acme/gadget") == 0


def test_strong_copyleft_wins_over_unknown(replay):
    """git/git has both GPL-2.0 and unresolved deps; 1 must beat 2."""
    assert replay.exit_code("git__git", "git/git") == 1


# --------------------------------------------------------------------------
# The report must agree with the exit code
# --------------------------------------------------------------------------

def test_unknown_prod_reports_undetermined_not_possibly(replay):
    result = replay.scan("synthetic__unknown_prod", "acme/widget")

    assert result.has_unknown_prod_licenses is True
    # "we don't know" must not render as "NO" / "POSSIBLY"
    assert result.verdict_undetermined is True
    assert result.forces_open_source is False
    assert result.can_sell_closed is False


def test_unknown_dev_only_is_not_undetermined(replay):
    result = replay.scan("synthetic__unknown_dev", "acme/gadget")

    assert result.has_unknown_prod_licenses is False
    assert result.verdict_undetermined is False
    assert result.can_sell_closed is True
    # dev unknowns still have to show up somewhere
    assert result.risk_counts()["unknown"] == 1


def test_unresolved_prod_licenses_raise_the_risk_score(replay):
    """
    An unresolvable production dependency must not score in the "low" band.
    Before the fix this repo scored 21/100 "low" while its own verdict text
    asked for manual review.
    """
    result = replay.scan("synthetic__unknown_prod", "acme/widget")

    assert result.risk_score >= 40
    assert result.risk_score_label in {"medium", "high"}


def test_cli_output_says_unknown_not_no(replay, capsys):
    replay.exit_code("synthetic__unknown_prod", "acme/widget")
    out = capsys.readouterr().out

    assert "Forces open source : UNKNOWN" in out
    assert "Can sell closed    : UNKNOWN" in out


def test_disclaimer_is_preserved_verbatim(replay):
    """The legal disclaimer must survive every verdict path, word for word."""
    expected = (
        " DISCLAIMER: Automated heuristic only — NOT legal advice, NOT a license "
        "compatibility opinion, and NOT a warranty of non-infringement. Consult a "
        "qualified attorney for compliance decisions."
    )
    for fixture, url in [
        ("git__git", "git/git"),
        ("psf__requests", "psf/requests"),
        ("synthetic__unknown_prod", "acme/widget"),
    ]:
        result = replay.scan(fixture, url)
        assert result.verdict_summary.endswith(expected)
