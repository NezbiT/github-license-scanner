"""
License classification, registry lookups, compatibility verdicts, and
end-to-end repository analysis orchestration.

IMPORTANT: Results are automated heuristics for developer guidance only.
They are NOT legal advice. Always consult a qualified attorney for
compliance decisions involving copyleft and commercial distribution.
"""

from __future__ import annotations

import asyncio
import re
import time
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

import httpx

from dependency_scanner import parse_many
from deploy_advisor import recommend_deploy
from github_api import (
    GitHubAPIError,
    create_client,
    download_dependency_files,
    find_dependency_files,
    get_repo_info,
    parse_github_url,
)
from models import (
    Dependency,
    PackageLicense,
    ReplacementSuggestion,
    ScanResult,
)

try:
    from config import (
        LICENSE_CACHE_MAX_ENTRIES,
        LICENSE_CACHE_TTL_SECONDS,
        MAX_CONCURRENT_LOOKUPS,
        MAX_PACKAGES_LOOKUP,
        USER_AGENT,
    )
except Exception:  # noqa: BLE001
    MAX_CONCURRENT_LOOKUPS = 12
    MAX_PACKAGES_LOOKUP = 80
    USER_AGENT = "github-license-scanner/1.1 (license-lookup; educational)"
    LICENSE_CACHE_TTL_SECONDS = 3600
    LICENSE_CACHE_MAX_ENTRIES = 2000

# ---------------------------------------------------------------------------
# License classification maps (SPDX-oriented, case-insensitive matching)
# ---------------------------------------------------------------------------

PERMISSIVE = {
    "mit",
    "apache-2.0",
    "apache 2.0",
    "apache2",
    "apache-2",
    "bsd-2-clause",
    "bsd-3-clause",
    "bsd",
    "isc",
    "unlicense",
    "0bsd",
    "cc0-1.0",
    "cc0",
    "zlib",
    "boost",
    "bsl-1.0",
    "python-2.0",
    "psf-2.0",
    "blueoak-1.0.0",
    "artistic-2.0",
    "wtfpl",
    "postgresql",
    "openssl",
}

WEAK_COPYLEFT = {
    "lgpl-2.1",
    "lgpl-3.0",
    "lgpl-2.0",
    "lgpl-2.1-only",
    "lgpl-2.1-or-later",
    "lgpl-3.0-only",
    "lgpl-3.0-or-later",
    "lgpl",
    "mpl-2.0",
    "mpl",
    "epl-1.0",
    "epl-2.0",
    "cpl-1.0",
    "cddl-1.0",
    "cddl-1.1",
    "ms-pl",
    "eupl-1.1",
    "eupl-1.2",
}

STRONG_COPYLEFT = {
    "gpl-2.0",
    "gpl-3.0",
    "gpl-2.0-only",
    "gpl-2.0-or-later",
    "gpl-3.0-only",
    "gpl-3.0-or-later",
    "gpl",
    "agpl-3.0",
    "agpl-1.0",
    "agpl-3.0-only",
    "agpl-3.0-or-later",
    "agpl",
    "sspl-1.0",
    "sspl",
    "sleepycat",
    "osl-3.0",  # treated as strong for distribution (conservative)
    "cecill-2.1",
}

# Licenses with network-use / SaaS-sensitive obligations (subset of strong)
NETWORK_COPYLEFT_MARKERS = ("agpl", "sspl")

# Heuristic replacements for known strong-copyleft packages (not exhaustive)
REPLACEMENT_MAP: dict[str, list[str]] = {
    # name lowercased -> permissive alternatives
    "readline": ["prompt_toolkit (BSD)", "pyreadline3 (BSD-ish)"],
    "gnu-readline": ["prompt_toolkit"],
    "ffmpeg-python": ["imageio-ffmpeg (check binary license)", "moviepy with care"],
    "mysql-connector-python": ["PyMySQL (MIT)", "mysqlclient (check license)", "asyncmy (Apache-2.0)"],
    "psycopg2": ["psycopg (LGPL — still weak)", "asyncpg (Apache-2.0)"],
    "qtpy": ["consider pure web UI (NiceGUI/Streamlit) to avoid Qt GPL builds"],
    "pyside2": ["PySide6 is LGPL; or use web UI frameworks"],
    "pyside6": ["dearpygui (MIT)", "NiceGUI (MIT)", "Streamlit (Apache-2.0)"],
    "pyqt5": ["PySide6 (LGPL)", "NiceGUI (MIT)", "tkinter (PSF)"],
    "pyqt6": ["PySide6 (LGPL)", "NiceGUI (MIT)"],
    "ghostscript": ["pypdf (BSD)", "pikepdf (MPL-2.0)"],
    "copyleft": [],  # placeholder
    # npm
    "node-gpl-example": ["look for MIT alternatives on npm"],
}

# In-process cache: (ecosystem, name_lower) -> (license_id, url, expires_at)
_license_cache: dict[tuple[str, str], tuple[str | None, str | None, float]] = {}


def _cache_get(key: tuple[str, str]) -> tuple[str | None, str | None] | None:
    entry = _license_cache.get(key)
    if not entry:
        return None
    lic, url, expires = entry
    if time.monotonic() > expires:
        _license_cache.pop(key, None)
        return None
    return lic, url


def _cache_set(key: tuple[str, str], lic: str | None, url: str | None) -> None:
    # Evict oldest-ish entries if over capacity (simple size guard)
    if len(_license_cache) >= LICENSE_CACHE_MAX_ENTRIES:
        # Drop ~10% of keys
        for drop_key in list(_license_cache.keys())[: max(1, LICENSE_CACHE_MAX_ENTRIES // 10)]:
            _license_cache.pop(drop_key, None)
    _license_cache[key] = (lic, url, time.monotonic() + LICENSE_CACHE_TTL_SECONDS)


# ---------------------------------------------------------------------------
# Classification helpers
# ---------------------------------------------------------------------------

def normalize_license_id(raw: str | None) -> str | None:
    """Normalize a license string for comparison and display."""
    if raw is None:
        return None
    text = str(raw).strip()
    if not text or text.upper() in {"NOASSERTION", "NONE", "UNKNOWN", "UNLICENSED", "SEE LICENSE IN LICENSE"}:
        # "UNLICENSED" in npm often means proprietary — keep a marker
        if text.upper() == "UNLICENSED":
            return "UNLICENSED"
        return None

    # npm sometimes returns {"type": "MIT", "url": "..."}
    # handled before calling this function

    # Common cleanup
    text = text.replace("License", "").replace("license", "").strip()
    # Take first alternative of dual licenses for classification display
    # e.g. "(MIT OR Apache-2.0)" -> keep original for display but classify carefully
    return text


def classify_license(license_id: str | None) -> str:
    """
    Classify a license string into a risk bucket.

    Returns one of: permissive | weak_copyleft | strong_copyleft | unknown
    """
    if not license_id:
        return "unknown"

    raw = license_id.strip()
    lower = raw.lower()

    # Proprietary / explicit unlicensed (npm)
    if lower in {"unlicensed", "proprietary", "commercial"}:
        return "unknown"

    # Dual / multi licenses: if ANY alternative is permissive-only OK,
    # but if ALL include strong copyleft, flag strong.
    # Heuristic for "MIT OR GPL-2.0" → permissive choice available → permissive
    if " or " in lower or "||" in lower or lower.startswith("("):
        tokens = re.split(r"\s+or\s+|\s*\|\|\s*|[()]", lower)
        tokens = [t.strip() for t in tokens if t.strip() and t.strip() not in {"and", "with"}]
        if tokens:
            classes = {_classify_single(t) for t in tokens}
            if "permissive" in classes:
                return "permissive"
            if "weak_copyleft" in classes and "strong_copyleft" not in classes:
                return "weak_copyleft"
            if "strong_copyleft" in classes:
                return "strong_copyleft"

    # AND composition: more conservative — strong if any strong
    if " and " in lower or "&&" in lower:
        tokens = re.split(r"\s+and\s+|\s*&&\s*", lower)
        classes = {_classify_single(t.strip(" ()")) for t in tokens if t.strip()}
        if "strong_copyleft" in classes:
            return "strong_copyleft"
        if "weak_copyleft" in classes:
            return "weak_copyleft"
        if classes == {"permissive"}:
            return "permissive"

    return _classify_single(lower)


def _classify_single(token: str) -> str:
    """Classify a single license token (already lowercased-ish)."""
    t = token.lower().strip().strip("()")
    t = t.replace(" ", "-")
    # Normalize common variants
    t = t.replace("gnu-", "").replace("licence", "license")

    # Direct set membership
    if t in PERMISSIVE or t.replace("-", "") in {p.replace("-", "") for p in PERMISSIVE}:
        return "permissive"
    if t in WEAK_COPYLEFT:
        return "weak_copyleft"
    if t in STRONG_COPYLEFT:
        return "strong_copyleft"

    # Substring heuristics
    if "agpl" in t or "sspl" in t:
        return "strong_copyleft"
    if re.search(r"(^|-)gpl", t) and "lgpl" not in t:
        return "strong_copyleft"
    if "lgpl" in t or "mpl" in t or t.startswith("epl"):
        return "weak_copyleft"
    if any(p in t for p in ("mit", "apache", "bsd", "isc", "unlicense", "zlib", "boost")):
        return "permissive"

    return "unknown"


def risk_color(risk: str) -> str:
    """Map risk to a simple color name for the UI."""
    return {
        "permissive": "green",
        "weak_copyleft": "orange",
        "strong_copyleft": "red",
        "unknown": "orange",
    }.get(risk, "grey")


# ---------------------------------------------------------------------------
# Registry license lookups
# ---------------------------------------------------------------------------

def _extract_npm_license(data: dict[str, Any]) -> str | None:
    """Extract license field from npm registry JSON."""
    lic = data.get("license")
    if isinstance(lic, str):
        return normalize_license_id(lic)
    if isinstance(lic, dict):
        return normalize_license_id(lic.get("type") or lic.get("name"))
    # Older packages: licenses array
    licenses = data.get("licenses")
    if isinstance(licenses, list) and licenses:
        first = licenses[0]
        if isinstance(first, dict):
            return normalize_license_id(first.get("type"))
        if isinstance(first, str):
            return normalize_license_id(first)
    # Prefer latest version info
    latest = (data.get("dist-tags") or {}).get("latest")
    versions = data.get("versions") or {}
    if latest and latest in versions:
        return _extract_npm_license(versions[latest])
    return None


def _extract_pypi_license(data: dict[str, Any]) -> str | None:
    """Extract license from PyPI JSON API."""
    info = data.get("info") or {}
    lic = info.get("license") or info.get("license_expression")
    if lic and str(lic).strip() and str(lic).strip() not in {"UNKNOWN", "License :: Other/Proprietary License"}:
        # Sometimes license is a long text; try to grab SPDX-like token
        text = str(lic).strip()
        if len(text) < 80:
            return normalize_license_id(text)

    # Classifiers: License :: OSI Approved :: MIT License
    for classifier in info.get("classifiers") or []:
        if not isinstance(classifier, str):
            continue
        if classifier.startswith("License ::"):
            parts = classifier.split("::")
            label = parts[-1].strip()
            # Map common classifier labels
            mapping = {
                "MIT License": "MIT",
                "Apache Software License": "Apache-2.0",
                "BSD License": "BSD",
                "GNU General Public License v3 (GPLv3)": "GPL-3.0",
                "GNU General Public License v2 (GPLv2)": "GPL-2.0",
                "GNU Affero General Public License v3": "AGPL-3.0",
                "GNU Lesser General Public License v3 (LGPLv3)": "LGPL-3.0",
                "GNU Lesser General Public License v2 (LGPLv2)": "LGPL-2.0",
                "Mozilla Public License 2.0 (MPL 2.0)": "MPL-2.0",
                "ISC License (ISCL)": "ISC",
                "The Unlicense (Unlicense)": "Unlicense",
                "Public Domain": "Unlicense",
            }
            if label in mapping:
                return mapping[label]
            return normalize_license_id(label)
    return normalize_license_id(str(lic) if lic else None)


async def lookup_package_license(
    client: httpx.AsyncClient,
    dep: Dependency,
) -> tuple[str | None, str | None]:
    """
    Query the official registry for a package license.

    Returns (license_id, info_url). Uses an in-process cache.
    """
    cache_key = (dep.ecosystem, dep.name.lower())
    cached = _cache_get(cache_key)
    if cached is not None:
        return cached

    license_id: str | None = None
    info_url: str | None = None

    try:
        if dep.ecosystem == "npm":
            # Scoped packages: @scope/name → %40scope%2Fname
            encoded = quote(dep.name, safe="@")
            # httpx quote: better encode slash in scope
            encoded = dep.name.replace("/", "%2F")
            url = f"https://registry.npmjs.org/{encoded}"
            info_url = f"https://www.npmjs.com/package/{dep.name}"
            resp = await client.get(url)
            if resp.status_code == 200:
                license_id = _extract_npm_license(resp.json())

        elif dep.ecosystem == "pypi":
            name = dep.name
            url = f"https://pypi.org/pypi/{quote(name)}/json"
            info_url = f"https://pypi.org/project/{name}/"
            resp = await client.get(url)
            if resp.status_code == 200:
                license_id = _extract_pypi_license(resp.json())

        elif dep.ecosystem == "cargo":
            url = f"https://crates.io/api/v1/crates/{quote(dep.name)}"
            info_url = f"https://crates.io/crates/{dep.name}"
            resp = await client.get(url, headers={"User-Agent": USER_AGENT})
            if resp.status_code == 200:
                crate = (resp.json().get("crate") or {})
                # license field on crate
                license_id = normalize_license_id(crate.get("license"))

        elif dep.ecosystem == "go":
            # Best-effort: pkg.go.dev does not have a stable simple JSON API.
            # Leave unknown; go.mod often has no license metadata remotely.
            info_url = f"https://pkg.go.dev/{dep.name}"
            license_id = None

        elif dep.ecosystem == "rubygems":
            url = f"https://rubygems.org/api/v1/gems/{quote(dep.name)}.json"
            info_url = f"https://rubygems.org/gems/{dep.name}"
            resp = await client.get(url)
            if resp.status_code == 200:
                data = resp.json()
                licenses = data.get("licenses") or []
                if isinstance(licenses, list) and licenses:
                    license_id = normalize_license_id(str(licenses[0]))
                else:
                    license_id = normalize_license_id(data.get("license"))

        elif dep.ecosystem == "composer":
            # Packagist
            if "/" in dep.name:
                url = f"https://repo.packagist.org/p2/{dep.name}.json"
                info_url = f"https://packagist.org/packages/{dep.name}"
                resp = await client.get(url)
                if resp.status_code == 200:
                    packages = (resp.json().get("packages") or {}).get(dep.name) or []
                    if packages and isinstance(packages, list):
                        lic_list = packages[0].get("license") or []
                        if isinstance(lic_list, list) and lic_list:
                            license_id = normalize_license_id(str(lic_list[0]))

        # maven / gradle: no free bulk API without coordinates API keys — skip
        else:
            license_id = None

    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        license_id = None

    _cache_set(cache_key, license_id, info_url)
    return license_id, info_url


async def resolve_all_licenses(
    dependencies: list[Dependency],
) -> list[PackageLicense]:
    """
    Resolve licenses for a list of dependencies with bounded concurrency.
    """
    deps = dependencies[:MAX_PACKAGES_LOOKUP]
    semaphore = asyncio.Semaphore(MAX_CONCURRENT_LOOKUPS)
    results: list[PackageLicense] = []

    async with httpx.AsyncClient(
        timeout=20.0,
        headers={"User-Agent": USER_AGENT},
        follow_redirects=True,
    ) as client:

        async def one(dep: Dependency) -> PackageLicense:
            async with semaphore:
                lic, url = await lookup_package_license(client, dep)
                risk = classify_license(lic)
                return PackageLicense(
                    name=dep.name,
                    ecosystem=dep.ecosystem,
                    license_id=lic,
                    risk=risk,
                    source_file=dep.source_file,
                    license_url=url,
                    version_spec=dep.version_spec,
                    is_dev=dep.is_dev,
                )

        tasks = [one(d) for d in deps]
        results = list(await asyncio.gather(*tasks))

    return results


# ---------------------------------------------------------------------------
# Verdicts, replacements, copyright notice
# ---------------------------------------------------------------------------

def build_copyright_notice(
    owner: str,
    repo: str,
    repo_license: str | None,
    year: int | None = None,
) -> str:
    """
    Build a plain-text *template* for notices — NOT a legal copyright claim.

    Important: the GitHub owner/organization name is often NOT the copyright
    holder (forks, orgs, employers, multi-author projects). Users must verify
    the LICENSE file, NOTICE file, and commit authorship before relying on this.
    """
    y = year or datetime.now(timezone.utc).year
    lic = repo_license or "SEE LICENSE IN REPOSITORY"
    return (
        f"=== NOTICE TEMPLATE (NOT LEGAL ADVICE) ===\n"
        f"WARNING: Do NOT treat the GitHub account name as proof of copyright\n"
        f"ownership. Verify rights holders from LICENSE, NOTICE, and history.\n"
        f"\n"
        f"Repository: https://github.com/{owner}/{repo}\n"
        f"Detected project license (heuristic): {lic}\n"
        f"GitHub owner/org (may differ from copyright holder): {owner}\n"
        f"\n"
        f"--- Suggested skeleton (edit before use) ---\n"
        f"Copyright (c) {y} [COPYRIGHT HOLDER NAME(S) — verify manually]\n"
        f"Licensed under {lic}. See the repository LICENSE file for full terms.\n"
        f"\n"
        f"Third-party software: list each dependency with its license id,\n"
        f"copyright holders, and any required attribution / NOTICE text.\n"
        f"Permissive licenses (MIT/BSD/Apache-2.0) still require attribution\n"
        f"and preservation of license/notice files upon distribution.\n"
        f"\n"
        f"Generated by GitHub License Scanner for convenience only.\n"
        f"Always verify against upstream sources before commercial use."
    )


def suggest_replacements(packages: list[PackageLicense]) -> list[ReplacementSuggestion]:
    """
    Suggest permissive alternatives for strong_copyleft (and notable weak) packages.
    """
    suggestions: list[ReplacementSuggestion] = []
    for pkg in packages:
        if pkg.risk not in {"strong_copyleft", "weak_copyleft"}:
            continue
        key = pkg.name.lower().split("/")[-1]  # strip scope / module path tail
        alts = REPLACEMENT_MAP.get(pkg.name.lower()) or REPLACEMENT_MAP.get(key)
        if alts:
            note = "Curated heuristic alternatives — verify licenses yourself."
            alternatives = alts
        else:
            note = (
                "No curated alternative on file. Search the same ecosystem for "
                "packages licensed under MIT, Apache-2.0, or BSD."
            )
            alternatives = [
                f"Search {pkg.ecosystem} for MIT/Apache alternatives to '{pkg.name}'"
            ]
        suggestions.append(
            ReplacementSuggestion(
                package=pkg.name,
                ecosystem=pkg.ecosystem,
                license_id=pkg.license_id,
                alternatives=alternatives,
                note=note,
            )
        )
    return suggestions


def _is_network_copyleft(license_id: str | None) -> bool:
    """True if the license string looks like AGPL/SSPL (SaaS/network sensitive)."""
    if not license_id:
        return False
    lower = license_id.lower()
    return any(m in lower for m in NETWORK_COPYLEFT_MARKERS)


def compute_verdict(
    repo_license: str | None,
    packages: list[PackageLicense],
) -> tuple[bool, bool, bool, bool, str, bool, bool]:
    """
    Heuristic closed-source risk signals (NOT a legal determination).

    Strong copyleft in **production** deps (or the repo license) sets
    forces_open_source. Strong copyleft only in **dev** deps is reported but
    does not auto-force open.

    Linking models (static vs dynamic), distribution vs SaaS, dual-licensing,
    additional permissions, and contractual overlays are NOT fully modeled.

    Returns:
        can_sell_closed, forces_open_source, has_weak_copyleft,
        has_unknown_licenses, verdict_summary, strong_copyleft_dev_only,
        has_network_copyleft
    """
    repo_risk = classify_license(repo_license)
    prod = [p for p in packages if not p.is_dev]
    dev = [p for p in packages if p.is_dev]

    strong_prod = [p for p in prod if p.risk == "strong_copyleft"]
    strong_dev = [p for p in dev if p.risk == "strong_copyleft"]
    weak_pkgs = [p for p in packages if p.risk == "weak_copyleft"]
    unknown_pkgs = [p for p in packages if p.risk == "unknown"]
    unknown_prod = [p for p in prod if p.risk == "unknown"]

    network_hits = []
    if _is_network_copyleft(repo_license):
        network_hits.append(f"repo:{repo_license}")
    for p in packages:
        if _is_network_copyleft(p.license_id):
            network_hits.append(p.name)
    has_network = bool(network_hits)

    forces = False
    reasons: list[str] = []
    strong_dev_only = False

    if repo_risk == "strong_copyleft":
        forces = True
        reasons.append(
            f"The repository license ({repo_license}) is classified as strong "
            f"copyleft (GPL/AGPL/SSPL-class). Distributing a modified or combined "
            f"work often requires providing corresponding source under compatible "
            f"terms — outcome depends on how you combine and distribute the code."
        )

    if strong_prod:
        forces = True
        names = ", ".join(sorted({p.name for p in strong_prod})[:12])
        extra = "…" if len(strong_prod) > 12 else ""
        reasons.append(
            f"Strong copyleft in production dependencies ({len(strong_prod)}): "
            f"{names}{extra}. Depending on linking/distribution model, this can "
            f"require opening source of combined works (GPL family). This tool "
            f"does not analyze your binary linking graph."
        )

    if has_network:
        names = ", ".join(sorted(set(network_hits))[:8])
        reasons.append(
            f"Network-copyleft / SaaS-sensitive license signal (AGPL/SSPL-class): "
            f"{names}. Even without traditional 'distribution', offering the "
            f"software over a network may trigger source-offer obligations. "
            f"Review AGPL §13 / SSPL terms with counsel before SaaS deployment."
        )

    if strong_dev and not strong_prod:
        strong_dev_only = True
        names = ", ".join(sorted({p.name for p in strong_dev})[:8])
        reasons.append(
            f"Strong copyleft only in dev/test dependencies ({len(strong_dev)}): "
            f"{names}. These often do not ship in production, but confirm your "
            f"build/distribution pipeline does not bundle them."
        )

    has_weak = bool(weak_pkgs) or repo_risk == "weak_copyleft"
    has_unknown = bool(unknown_pkgs) or repo_risk == "unknown" or not repo_license

    can_sell = not forces

    if can_sell and has_weak:
        weak_prod = [p for p in weak_pkgs if not p.is_dev]
        reasons.append(
            f"Weak copyleft packages present ({len(weak_pkgs)} total, "
            f"{len(weak_prod)} production: MPL/LGPL/EPL/EUPL-class). "
            f"You may often keep your own code closed if you comply with "
            f"file-level, library, or reciprocal obligations — review each license."
        )
    if can_sell and has_unknown:
        reasons.append(
            f"Some licenses could not be determined "
            f"({len(unknown_prod)} production / {len(unknown_pkgs)} total packages"
            f"{' and/or missing repo license' if not repo_license else ''}). "
            f"Manual review required before commercial closed-source distribution."
        )
    if can_sell and not reasons:
        reasons.append(
            "No strong copyleft (GPL/AGPL-class) signals found in the repository "
            "license or production dependencies. Closed-source commercial sale may "
            "be feasible, subject to attribution, NOTICE, patent, trademark, and "
            "export terms of each permissive license (MIT/BSD/Apache-2.0, etc.)."
        )
    elif can_sell:
        reasons.append(
            "Even without strong copyleft, permissive licenses still require "
            "preserving copyright/license notices upon redistribution."
        )

    summary = " ".join(reasons)
    summary += (
        " DISCLAIMER: Automated heuristic only — NOT legal advice, NOT a license "
        "compatibility opinion, and NOT a warranty of non-infringement. Consult a "
        "qualified attorney for compliance decisions."
    )
    return can_sell, forces, has_weak, has_unknown, summary, strong_dev_only, has_network


def compute_risk_score(
    repo_license: str | None,
    packages: list[PackageLicense],
) -> tuple[int, str]:
    """
    Compute a 0–100 risk score (higher = more concern for closed-source sale).

    Weight production deps more heavily than dev deps.
    """
    score = 0
    repo_risk = classify_license(repo_license)
    if repo_risk == "strong_copyleft":
        score += 55
    elif repo_risk == "weak_copyleft":
        score += 15
    elif repo_risk == "unknown" or not repo_license:
        score += 10

    for pkg in packages:
        w = 0.35 if pkg.is_dev else 1.0
        if pkg.risk == "strong_copyleft":
            score += 18 * w
        elif pkg.risk == "weak_copyleft":
            score += 6 * w
        elif pkg.risk == "unknown":
            score += 4 * w

    score_i = int(min(100, round(score)))
    if score_i >= 70:
        label = "high"
    elif score_i >= 40:
        label = "medium"
    elif score_i >= 15:
        label = "low"
    else:
        label = "minimal"
    return score_i, label


def group_by_license(packages: list[PackageLicense]) -> dict[str, list[PackageLicense]]:
    """Group packages by license id (display key)."""
    grouped: dict[str, list[PackageLicense]] = {}
    for pkg in packages:
        key = pkg.license_id or "Unknown"
        grouped.setdefault(key, []).append(pkg)
    # Sort groups: strong first (red), then weak, unknown, permissive
    risk_order = {"strong_copyleft": 0, "weak_copyleft": 1, "unknown": 2, "permissive": 3}

    def group_sort_key(item: tuple[str, list[PackageLicense]]) -> tuple[int, str]:
        lic, pkgs = item
        worst = min((risk_order.get(p.risk, 9) for p in pkgs), default=9)
        return (worst, lic.lower())

    return dict(sorted(grouped.items(), key=group_sort_key))


# ---------------------------------------------------------------------------
# Orchestration
# ---------------------------------------------------------------------------

async def analyze_repository(url: str) -> ScanResult:
    """
    Full pipeline: parse URL → GitHub metadata → dependency files →
    registry licenses → verdict → replacements → deploy advice.
    """
    scanned_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")
    errors: list[str] = []

    try:
        owner, repo = parse_github_url(url)
    except ValueError as exc:
        return ScanResult(
            owner="",
            repo="",
            url=url,
            repo_license=None,
            scanned_at=scanned_at,
            can_sell_closed=False,
            forces_open_source=False,
            scan_complete=False,
            verdict_summary=str(exc),
            errors=[str(exc)],
            copyright_notice="",
        )

    repo_license: str | None = None
    primary_language: str | None = None
    description: str | None = None
    topics: list[str] = []
    dep_paths: list[str] = []
    has_dockerfile = False
    packages: list[PackageLicense] = []
    dependencies: list[Dependency] = []
    html_url = f"https://github.com/{owner}/{repo}"

    async with create_client() as gh:
        try:
            info = await get_repo_info(gh, owner, repo)
            repo_license = info.get("license_spdx") or info.get("license_name")
            primary_language = info.get("language")
            description = info.get("description")
            topics = list(info.get("topics") or [])
            html_url = info.get("html_url") or html_url
            branch = info["default_branch"]

            dep_paths, has_dockerfile = await find_dependency_files(
                gh, owner, repo, branch
            )
            if dep_paths:
                contents = await download_dependency_files(
                    gh, owner, repo, dep_paths, ref=branch
                )
                dependencies = parse_many(contents)
            else:
                errors.append("No dependency manifest files found in the repository.")

        except GitHubAPIError as exc:
            errors.append(str(exc))
            # Incomplete scan — do not imply a closed-sale decision either way
            return ScanResult(
                owner=owner,
                repo=repo,
                url=html_url,
                repo_license=None,
                scanned_at=scanned_at,
                can_sell_closed=False,
                forces_open_source=False,
                scan_complete=False,
                has_weak_copyleft=False,
                has_unknown_licenses=True,
                verdict_summary=(
                    f"Scan incomplete: {exc} "
                    "No closed-source sellability decision can be made until "
                    "GitHub data is available. Set GITHUB_TOKEN if you hit rate limits. "
                    "DISCLAIMER: Automated heuristic only — NOT legal advice."
                ),
                errors=errors,
                copyright_notice=build_copyright_notice(owner, repo, None),
            )
        except httpx.HTTPError as exc:
            errors.append(f"Network error talking to GitHub: {exc}")
            return ScanResult(
                owner=owner,
                repo=repo,
                url=html_url,
                repo_license=None,
                scanned_at=scanned_at,
                can_sell_closed=False,
                forces_open_source=False,
                scan_complete=False,
                has_weak_copyleft=False,
                has_unknown_licenses=True,
                verdict_summary=(
                    f"Scan incomplete (network error): {exc} "
                    "DISCLAIMER: Automated heuristic only — NOT legal advice."
                ),
                errors=errors,
                copyright_notice=build_copyright_notice(owner, repo, None),
            )

    if len(dependencies) > MAX_PACKAGES_LOOKUP:
        errors.append(
            f"Package list truncated to {MAX_PACKAGES_LOOKUP} of {len(dependencies)} "
            f"for registry lookup performance."
        )

    if dependencies:
        try:
            packages = await resolve_all_licenses(dependencies)
        except httpx.HTTPError as exc:
            errors.append(f"Registry lookup network error: {exc}")
            packages = [
                PackageLicense(
                    name=d.name,
                    ecosystem=d.ecosystem,
                    license_id=None,
                    risk="unknown",
                    source_file=d.source_file,
                    version_spec=d.version_spec,
                    is_dev=d.is_dev,
                )
                for d in dependencies[:MAX_PACKAGES_LOOKUP]
            ]

    (
        can_sell,
        forces,
        has_weak,
        has_unknown,
        summary,
        strong_dev_only,
        has_network,
    ) = compute_verdict(repo_license, packages)
    risk_score, risk_label = compute_risk_score(repo_license, packages)
    grouped = group_by_license(packages)
    replacements = suggest_replacements(packages)
    deploy = recommend_deploy(
        primary_language=primary_language,
        topics=topics,
        dependencies=dependencies,
        dependency_files=dep_paths,
        has_dockerfile=has_dockerfile,
        description=description,
    )
    notice = build_copyright_notice(owner, repo, repo_license)
    prod_n = sum(1 for p in packages if not p.is_dev)
    dev_n = sum(1 for p in packages if p.is_dev)

    return ScanResult(
        owner=owner,
        repo=repo,
        url=html_url,
        repo_license=repo_license,
        packages=packages,
        grouped=grouped,
        can_sell_closed=can_sell,
        forces_open_source=forces,
        has_weak_copyleft=has_weak,
        has_unknown_licenses=has_unknown,
        verdict_summary=summary,
        copyright_notice=notice,
        replacements=replacements,
        deploy_advice=deploy,
        scanned_at=scanned_at,
        errors=errors,
        scan_complete=True,
        primary_language=primary_language,
        description=description,
        topics=topics,
        dependency_files=dep_paths,
        risk_score=risk_score,
        risk_score_label=risk_label,
        prod_package_count=prod_n,
        dev_package_count=dev_n,
        strong_copyleft_dev_only=strong_dev_only,
        has_network_copyleft=has_network,
        has_dockerfile=has_dockerfile,
    )
