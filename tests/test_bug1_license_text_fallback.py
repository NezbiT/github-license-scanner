"""
Bug 1 — GitHub's "other" / NOASSERTION must not collapse into "permissive".

When GitHub's licensee detector fails, the scanner must download the license
file and detect it from its text. Failing that, the result is an explicit
UNKNOWN — never a silent "does not force open source".
"""

from __future__ import annotations

import pytest

from gls.license_analyzer import detect_license_from_text


# --------------------------------------------------------------------------
# Text detection, in isolation
# --------------------------------------------------------------------------

GPL2_HEADER = """
                    GNU GENERAL PUBLIC LICENSE
                       Version 2, June 1991

 Copyright (C) 1989, 1991 Free Software Foundation, Inc.,
"""

GPL3_HEADER = """
                    GNU GENERAL PUBLIC LICENSE
                       Version 3, 29 June 2007

 Copyright (C) 2007 Free Software Foundation, Inc.
"""


@pytest.mark.parametrize(
    "text,expected",
    [
        (GPL2_HEADER, "GPL-2.0"),
        (GPL3_HEADER, "GPL-3.0"),
        ("GNU AFFERO GENERAL PUBLIC LICENSE\nVersion 3, 19 November 2007", "AGPL-3.0"),
        ("GNU LESSER GENERAL PUBLIC LICENSE\nVersion 2.1, February 1999", "LGPL-2.1"),
        ("GNU LESSER GENERAL PUBLIC LICENSE\nVersion 3, 29 June 2007", "LGPL-3.0"),
        ("Mozilla Public License Version 2.0", "MPL-2.0"),
        ("Server Side Public License\nVERSION 1, OCTOBER 16, 2018", "SSPL-1.0"),
        ("Apache License\nVersion 2.0, January 2004", "Apache-2.0"),
        (
            'Permission is hereby granted, free of charge, to any person '
            'obtaining a copy of this software',
            "MIT",
        ),
        (
            "Redistribution and use in source and binary forms, with or without "
            "modification, are permitted provided that the following conditions",
            "BSD",
        ),
    ],
)
def test_detects_license_from_text(text, expected):
    assert detect_license_from_text(text) == expected


def test_detection_is_case_insensitive():
    assert detect_license_from_text(GPL2_HEADER.lower()) == "GPL-2.0"


def test_gpl2_preamble_does_not_leak_into_gpl3():
    """git's COPYING mentions v3 in a preamble; the title still says Version 2."""
    text = (
        " Note that the only valid version of the GPL as far as this project\n"
        " is concerned is _this_ particular version of the license (ie v2, not\n"
        " v2.2 or v3.x or whatever), unless explicitly otherwise stated.\n"
        " HOWEVER, in order to allow a migration to GPLv3 if that seems like\n"
        " a good idea, I also ask that people involved make their preferences known.\n"
        "----------------------------------------\n" + GPL2_HEADER
    )
    assert detect_license_from_text(text) == "GPL-2.0"


def test_unrecognized_text_returns_none_not_permissive():
    """Absence of a match must be None — never a permissive default."""
    assert detect_license_from_text("This file intentionally left blank.") is None
    assert detect_license_from_text("") is None
    assert detect_license_from_text(None) is None


# --------------------------------------------------------------------------
# End-to-end, against recorded API responses
# --------------------------------------------------------------------------

def test_git_git_is_detected_as_gpl2(replay):
    """
    The regression that started this: GitHub reports spdx_id=NOASSERTION,
    name="Other" for git/git, and the scanner said "you may sell this closed".
    """
    result = replay.scan("git__git", "git/git")

    assert result.repo_license == "GPL-2.0"
    assert result.forces_open_source is True
    assert result.can_sell_closed is False
    assert result.repo_license_unresolved is False
    assert result.license_detection_source == "license_text"


def test_torvalds_linux_is_detected_as_gpl2(replay):
    result = replay.scan("torvalds__linux", "torvalds/linux")

    assert result.repo_license == "GPL-2.0"
    assert result.forces_open_source is True
    assert result.can_sell_closed is False


def test_mongodb_mongo_is_detected_as_sspl(replay):
    """mongo's license file is LICENSE-Community.txt — found via root listing."""
    result = replay.scan("mongodb__mongo", "mongodb/mongo")

    assert result.repo_license == "SSPL-1.0"
    assert result.forces_open_source is True
    assert result.can_sell_closed is False
    assert result.has_network_copyleft is True


def test_psf_requests_keeps_github_spdx_id(replay):
    """When GitHub resolves the license, no fallback should run."""
    result = replay.scan("psf__requests", "psf/requests")

    assert result.repo_license == "Apache-2.0"
    assert result.forces_open_source is False
    assert result.license_detection_source == "github_api"


def test_other_is_never_reported_as_the_repo_license(replay):
    """The literal string "Other" must never survive into the result."""
    for fixture, url in [
        ("git__git", "git/git"),
        ("torvalds__linux", "torvalds/linux"),
        ("mongodb__mongo", "mongodb/mongo"),
    ]:
        result = replay.scan(fixture, url)
        assert result.repo_license != "Other"
