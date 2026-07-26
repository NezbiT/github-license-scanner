"""
Shared data models for the GitHub License Scanner.

All modules import dataclasses from here to avoid circular dependencies
and keep a single source of truth for scan-related structures.
"""

from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any


@dataclass
class Dependency:
    """A single package declared in a dependency manifest file."""

    name: str
    version_spec: str | None
    ecosystem: str  # npm | pypi | cargo | go | rubygems | composer | maven | gradle
    source_file: str  # path inside the repository, e.g. "package.json"
    is_dev: bool = False  # True for dev/test/build-only dependencies


@dataclass
class PackageLicense:
    """License information resolved for one dependency."""

    name: str
    ecosystem: str
    license_id: str | None  # SPDX-like id or raw registry string
    risk: str  # permissive | weak_copyleft | strong_copyleft | unknown
    source_file: str
    license_url: str | None = None
    version_spec: str | None = None
    is_dev: bool = False

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ReplacementSuggestion:
    """Suggested permissive alternative for a problematic package."""

    package: str
    ecosystem: str
    license_id: str | None
    alternatives: list[str]
    note: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class DeployAdvice:
    """One deploy platform recommendation with rationale."""

    platform: str
    score: int  # higher is better match
    reasons: list[str]
    docs_url: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass
class ScanResult:
    """Full analysis result for a single GitHub repository."""

    owner: str
    repo: str
    url: str
    repo_license: str | None
    packages: list[PackageLicense] = field(default_factory=list)
    # license_id -> list of packages using that license
    grouped: dict[str, list[PackageLicense]] = field(default_factory=dict)
    can_sell_closed: bool = True
    forces_open_source: bool = False
    has_weak_copyleft: bool = False
    has_unknown_licenses: bool = False
    verdict_summary: str = ""
    copyright_notice: str = ""
    replacements: list[ReplacementSuggestion] = field(default_factory=list)
    deploy_advice: list[DeployAdvice] = field(default_factory=list)
    scanned_at: str = ""
    errors: list[str] = field(default_factory=list)
    # False when GitHub/network failed before a reliable verdict
    scan_complete: bool = True
    # Extra metadata used by deploy advisor / UI
    primary_language: str | None = None
    description: str | None = None
    topics: list[str] = field(default_factory=list)
    dependency_files: list[str] = field(default_factory=list)
    has_dockerfile: bool = False
    # Risk score 0 (safest) … 100 (highest copyleft / uncertainty pressure)
    risk_score: int = 0
    risk_score_label: str = "n/a"
    # Counts after prod/dev split (filled by analyzer)
    prod_package_count: int = 0
    dev_package_count: int = 0
    # Strong copyleft only in dev deps (warning, does not force open by default)
    strong_copyleft_dev_only: bool = False
    # True when AGPL/network-copyleft signals were detected (extra SaaS caution)
    has_network_copyleft: bool = False
    # --- Unknown-license tracking -----------------------------------------
    # These separate "we know it is safe" from "we could not find out", which
    # the boolean can_sell_closed / forces_open_source pair cannot express.
    # How repo_license was determined: github_api | license_text | unresolved
    license_detection_source: str = "unresolved"
    # True when neither GitHub nor the license-file text yielded a license
    repo_license_unresolved: bool = False
    # True when at least one *production* dependency could not be resolved
    has_unknown_prod_licenses: bool = False

    @property
    def verdict_undetermined(self) -> bool:
        """
        True when the scan cannot support any closed-source conclusion.

        Strong copyleft is a determination, so it takes precedence: a repo
        that forces open source is not "undetermined" merely because some
        dependency was also unresolvable.
        """
        if self.forces_open_source:
            return False
        return self.repo_license_unresolved or self.has_unknown_prod_licenses

    def to_history_entry(self) -> dict[str, Any]:
        """Compact dict suitable for history.json persistence."""
        return {
            "owner": self.owner,
            "repo": self.repo,
            "url": self.url,
            "repo_license": self.repo_license,
            "scanned_at": self.scanned_at,
            "can_sell_closed": self.can_sell_closed,
            "forces_open_source": self.forces_open_source,
            "scan_complete": self.scan_complete,
            "package_count": len(self.packages),
            "risk_score": self.risk_score,
            "has_network_copyleft": self.has_network_copyleft,
            # Truncate free text for privacy / storage hygiene
            "verdict_summary": (self.verdict_summary or "")[:500],
        }

    def risk_counts(self, *, prod_only: bool = False) -> dict[str, int]:
        """Count packages by risk category."""
        counts = {
            "permissive": 0,
            "weak_copyleft": 0,
            "strong_copyleft": 0,
            "unknown": 0,
        }
        for pkg in self.packages:
            if prod_only and pkg.is_dev:
                continue
            key = pkg.risk if pkg.risk in counts else "unknown"
            counts[key] += 1
        return counts

    @property
    def prod_packages(self) -> list[PackageLicense]:
        return [p for p in self.packages if not p.is_dev]

    @property
    def dev_packages(self) -> list[PackageLicense]:
        return [p for p in self.packages if p.is_dev]
