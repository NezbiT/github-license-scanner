"""
SBOM export for scan results.

Formats:
  - CycloneDX 1.5 JSON (application + library components)
  - SPDX 2.3 JSON document (packages + relationships)

These documents are generated from *declared* dependencies and registry
license metadata. They are not a full binary SBOM from a build graph.
"""

from __future__ import annotations

import json
import re
import uuid
from datetime import datetime, timezone
from typing import Any
from urllib.parse import quote

from models import PackageLicense, ScanResult
from spdx_engine import expression_to_spdx_ids


TOOL_NAME = "github-license-scanner"
TOOL_VERSION = "1.2.0"


def _now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _purl(pkg: PackageLicense) -> str | None:
    """Best-effort package URL (purl)."""
    name = pkg.name
    ver = (pkg.version_spec or "").lstrip("=^~><! ")
    # Strip complex version ranges for purl version field
    if any(c in ver for c in " ,|"):
        ver = ""
    eco = pkg.ecosystem
    if eco == "npm":
        # scoped: @scope/name
        if name.startswith("@") and "/" in name:
            scope, n = name[1:].split("/", 1)
            base = f"pkg:npm/{quote(scope)}/{quote(n)}"
        else:
            base = f"pkg:npm/{quote(name)}"
        return f"{base}@{quote(ver)}" if ver else base
    if eco == "pypi":
        base = f"pkg:pypi/{quote(name)}"
        return f"{base}@{quote(ver)}" if ver else base
    if eco == "cargo":
        base = f"pkg:cargo/{quote(name)}"
        return f"{base}@{quote(ver)}" if ver else base
    if eco == "go":
        base = f"pkg:golang/{name}"  # path may contain /
        return f"{base}@{quote(ver)}" if ver else base
    if eco == "rubygems":
        base = f"pkg:gem/{quote(name)}"
        return f"{base}@{quote(ver)}" if ver else base
    if eco == "composer":
        base = f"pkg:composer/{name}"
        return f"{base}@{quote(ver)}" if ver else base
    if eco in {"maven", "gradle"} and ":" in name:
        group, artifact = name.split(":", 1)
        base = f"pkg:maven/{quote(group)}/{quote(artifact)}"
        return f"{base}@{quote(ver)}" if ver else base
    return None


def _bom_ref(pkg: PackageLicense, idx: int) -> str:
    purl = _purl(pkg)
    if purl:
        return purl
    return f"{pkg.ecosystem}:{pkg.name}#{idx}"


def render_cyclonedx_json(result: ScanResult) -> str:
    """Serialize a ScanResult as CycloneDX 1.5 JSON."""
    serial = f"urn:uuid:{uuid.uuid4()}"
    components: list[dict[str, Any]] = []
    for i, pkg in enumerate(result.packages):
        licenses = []
        if pkg.license_id:
            ids = expression_to_spdx_ids(pkg.license_id)
            if ids:
                for lid in ids:
                    licenses.append({"license": {"id": lid}})
            else:
                licenses.append({"license": {"name": pkg.license_id}})

        comp: dict[str, Any] = {
            "type": "library",
            "bom-ref": _bom_ref(pkg, i),
            "name": pkg.name,
            "purl": _purl(pkg),
            "scope": "optional" if pkg.is_dev else "required",
            "properties": [
                {"name": "gls:ecosystem", "value": pkg.ecosystem},
                {"name": "gls:risk", "value": pkg.risk},
                {"name": "gls:source_file", "value": pkg.source_file},
            ],
        }
        if pkg.version_spec:
            # CycloneDX version is a single version; store range as property
            if re_is_single_version(pkg.version_spec):
                comp["version"] = pkg.version_spec.lstrip("=v")
            else:
                comp["properties"].append(
                    {"name": "gls:version_spec", "value": pkg.version_spec}
                )
        if licenses:
            comp["licenses"] = licenses
        if pkg.license_url:
            comp["externalReferences"] = [
                {"type": "website", "url": pkg.license_url}
            ]
        # Drop null purl
        if not comp.get("purl"):
            comp.pop("purl", None)
        components.append(comp)

    metadata_licenses = []
    if result.repo_license:
        for lid in expression_to_spdx_ids(result.repo_license) or [result.repo_license]:
            metadata_licenses.append({"license": {"id": lid if _looks_spdx(lid) else None, "name": lid}})
            if metadata_licenses[-1]["license"].get("id") is None:
                metadata_licenses[-1] = {"license": {"name": lid}}

    doc: dict[str, Any] = {
        "bomFormat": "CycloneDX",
        "specVersion": "1.5",
        "serialNumber": serial,
        "version": 1,
        "metadata": {
            "timestamp": _now_iso(),
            "tools": {
                "components": [
                    {
                        "type": "application",
                        "name": TOOL_NAME,
                        "version": TOOL_VERSION,
                    }
                ]
            },
            "component": {
                "type": "application",
                "name": f"{result.owner}/{result.repo}" if result.owner else (result.url or "unknown"),
                "bom-ref": f"app:{result.owner}/{result.repo}" if result.owner else "app:unknown",
                "purl": (
                    f"pkg:github/{result.owner}/{result.repo}"
                    if result.owner and result.repo
                    else None
                ),
                "licenses": metadata_licenses or None,
                "externalReferences": (
                    [{"type": "vcs", "url": result.url}] if result.url else []
                ),
                "properties": [
                    {"name": "gls:risk_score", "value": str(result.risk_score)},
                    {
                        "name": "gls:forces_open_source",
                        "value": str(result.forces_open_source).lower(),
                    },
                    {
                        "name": "gls:scan_complete",
                        "value": str(result.scan_complete).lower(),
                    },
                    {
                        "name": "gls:disclaimer",
                        "value": "Automated heuristic SBOM — not legal advice",
                    },
                ],
            },
        },
        "components": components,
    }
    # Clean nulls in component
    meta_comp = doc["metadata"]["component"]
    if not meta_comp.get("purl"):
        meta_comp.pop("purl", None)
    if not meta_comp.get("licenses"):
        meta_comp.pop("licenses", None)

    return json.dumps(doc, indent=2, ensure_ascii=False)


def re_is_single_version(spec: str) -> bool:
    s = (spec or "").strip().lstrip("=")
    return bool(re.fullmatch(r"v?\d+(?:\.\d+)*(?:[-+][A-Za-z0-9.]+)?", s))


def _looks_spdx(lid: str) -> bool:
    return bool(re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9.+_-]*", lid or ""))


def render_spdx_json(result: ScanResult) -> str:
    """Serialize a ScanResult as SPDX 2.3 JSON."""
    doc_name = (
        f"SPDXRef-DOCUMENT-{result.owner}-{result.repo}"
        if result.owner
        else "SPDXRef-DOCUMENT"
    )
    created = _now_iso()
    packages: list[dict[str, Any]] = []

    # Root package = repository
    root_spdx_id = "SPDXRef-Package-Root"
    root_lic = result.repo_license or "NOASSERTION"
    packages.append(
        {
            "SPDXID": root_spdx_id,
            "name": f"{result.owner}/{result.repo}" if result.owner else "root",
            "downloadLocation": result.url or "NOASSERTION",
            "filesAnalyzed": False,
            "licenseConcluded": root_lic if result.repo_license else "NOASSERTION",
            "licenseDeclared": root_lic if result.repo_license else "NOASSERTION",
            "copyrightText": "NOASSERTION",
            "externalRefs": (
                [
                    {
                        "referenceCategory": "PACKAGE-MANAGER",
                        "referenceType": "purl",
                        "referenceLocator": f"pkg:github/{result.owner}/{result.repo}",
                    }
                ]
                if result.owner
                else []
            ),
            "comment": (
                f"risk_score={result.risk_score}; forces_open={result.forces_open_source}; "
                "generated by github-license-scanner (heuristic, not legal advice)"
            ),
        }
    )

    relationships = [
        {
            "spdxElementId": "SPDXRef-DOCUMENT",
            "relationshipType": "DESCRIBES",
            "relatedSpdxElement": root_spdx_id,
        }
    ]

    for i, pkg in enumerate(result.packages):
        spdx_id = f"SPDXRef-Package-{i}"
        lic = pkg.license_id or "NOASSERTION"
        purl = _purl(pkg)
        ext = []
        if purl:
            ext.append(
                {
                    "referenceCategory": "PACKAGE-MANAGER",
                    "referenceType": "purl",
                    "referenceLocator": purl,
                }
            )
        packages.append(
            {
                "SPDXID": spdx_id,
                "name": pkg.name,
                "versionInfo": pkg.version_spec or "NOASSERTION",
                "downloadLocation": pkg.license_url or "NOASSERTION",
                "filesAnalyzed": False,
                "licenseConcluded": lic,
                "licenseDeclared": lic,
                "copyrightText": "NOASSERTION",
                "externalRefs": ext,
                "comment": (
                    f"ecosystem={pkg.ecosystem}; risk={pkg.risk}; "
                    f"scope={'dev' if pkg.is_dev else 'prod'}; source={pkg.source_file}"
                ),
            }
        )
        relationships.append(
            {
                "spdxElementId": root_spdx_id,
                "relationshipType": "DEPENDS_ON",
                "relatedSpdxElement": spdx_id,
            }
        )

    doc: dict[str, Any] = {
        "spdxVersion": "SPDX-2.3",
        "dataLicense": "CC0-1.0",
        "SPDXID": "SPDXRef-DOCUMENT",
        "name": doc_name,
        "documentNamespace": f"https://github.com/NezbiT/github-license-scanner/spdx/{uuid.uuid4()}",
        "creationInfo": {
            "created": created,
            "creators": [f"Tool: {TOOL_NAME}-{TOOL_VERSION}", "Organization: local"],
            "licenseListVersion": "3.22",
            "comment": "Automated heuristic export — not legal advice",
        },
        "packages": packages,
        "relationships": relationships,
    }
    return json.dumps(doc, indent=2, ensure_ascii=False)


def render_sbom(result: ScanResult, fmt: str = "cyclonedx") -> str:
    """
    Render SBOM text for the given format.

    fmt: cyclonedx | spdx | cdx | spdx-json
    """
    key = (fmt or "cyclonedx").lower().strip()
    if key in {"cyclonedx", "cdx", "cyclonedx-json"}:
        return render_cyclonedx_json(result)
    if key in {"spdx", "spdx-json", "spdx23"}:
        return render_spdx_json(result)
    raise ValueError(f"Unknown SBOM format: {fmt!r} (use cyclonedx or spdx)")
