"""
End-to-end verification: unit logic, integration scans, and speed metrics.
Run: python scripts/verify_app.py
"""

from __future__ import annotations

import asyncio
import statistics
import sys
import time
from pathlib import Path

# Project root on sys.path
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import httpx

from gls.dependency_scanner import parse_dependencies
from gls.deploy_advisor import recommend_deploy
from gls.github_api import parse_github_url
from gls.license_analyzer import (
    analyze_repository,
    build_copyright_notice,
    classify_license,
    compute_verdict,
    normalize_license_id,
)
from gls.models import Dependency, PackageLicense, ScanResult
from gls.sbom_export import render_sbom
from gls.spdx_engine import classify_expression, parse_expression


def section(title: str) -> None:
    print()
    print("=" * 70)
    print(title)
    print("=" * 70)


def test_units() -> None:
    section("1) UNIT LOGIC")

    cases = [
        ("https://github.com/psf/requests", ("psf", "requests")),
        ("https://github.com/psf/requests.git", ("psf", "requests")),
        ("https://github.com/psf/requests/tree/main/docs", ("psf", "requests")),
        ("git@github.com:owner/repo.git", ("owner", "repo")),
        ("psf/requests", ("psf", "requests")),
    ]
    for raw, exp in cases:
        got = parse_github_url(raw)
        assert got == exp, (raw, got, exp)
    print(f"  URL parse: {len(cases)}/{len(cases)} OK")

    cls_cases = [
        ("MIT", "permissive"),
        ("Apache-2.0", "permissive"),
        ("BSD-3-Clause", "permissive"),
        ("GPL-3.0", "strong_copyleft"),
        ("AGPL-3.0", "strong_copyleft"),
        ("LGPL-2.1", "weak_copyleft"),
        ("MPL-2.0", "weak_copyleft"),
        ("MIT OR GPL-2.0", "permissive"),
        ("GPL-2.0 AND MIT", "strong_copyleft"),
        ("(MIT OR Apache-2.0) AND GPL-3.0", "strong_copyleft"),
        ("MIT OR (GPL-2.0 AND BSD-3-Clause)", "permissive"),
        ("GPL-2.0+ WITH Classpath-exception-2.0", "strong_copyleft"),
        ("MIT/Apache-2.0", "permissive"),
        (None, "unknown"),
        ("UNLICENSED", "unknown"),
    ]
    for lic, exp in cls_cases:
        got = classify_license(lic)
        assert got == exp, f"{lic!r} -> {got} expected {exp}"
    # empty / whitespace
    assert classify_license(normalize_license_id("")) == "unknown"
    node = parse_expression("MIT OR Apache-2.0")
    assert node.op == "or"
    risk, _, err = classify_expression("MIT AND GPL-3.0")
    assert risk == "strong_copyleft" and err is None
    print(f"  classify_license / spdx_engine: {len(cls_cases)}+ OK")

    req = parse_dependencies(
        "requirements.txt", "httpx>=0.27\n# c\npackaging==24\n-r other.txt\n"
    )
    assert len(req) == 2 and req[0].ecosystem == "pypi"
    pkg = parse_dependencies(
        "package.json",
        '{"dependencies":{"react":"^18"},"devDependencies":{"vite":"5"}}',
    )
    assert len(pkg) == 2 and pkg[0].ecosystem == "npm"
    cargo = parse_dependencies("Cargo.toml", '[dependencies]\nserde = "1.0"\n')
    assert cargo[0].name == "serde" and cargo[0].ecosystem == "cargo"
    gomod = parse_dependencies("go.mod", "module x\nrequire github.com/a/b v1.0.0\n")
    assert gomod[0].name == "github.com/a/b"
    pyproj = parse_dependencies(
        "pyproject.toml", '[project]\ndependencies = ["httpx>=0.27"]\n'
    )
    assert any(d.name == "httpx" for d in pyproj)
    print("  dependency parsers: OK")

    strong = PackageLicense("badlib", "pypi", "GPL-3.0", "strong_copyleft", "req.txt")
    weak = PackageLicense("certifi", "pypi", "MPL-2.0", "weak_copyleft", "req.txt")
    perm = PackageLicense("httpx", "pypi", "BSD-3-Clause", "permissive", "req.txt")

    c, f, w, u, _, dev_only, net = compute_verdict("MIT", [perm])
    assert c and not f and not w and not dev_only and not net
    c, f, w, u, _, _, _ = compute_verdict("MIT", [perm, weak])
    assert c and not f and w
    c, f, w, u, _, _, _ = compute_verdict("MIT", [strong])
    assert not c and f
    c, f, w, u, _, _, _ = compute_verdict("GPL-3.0", [perm])
    assert not c and f
    agpl = PackageLicense("svc", "pypi", "AGPL-3.0", "strong_copyleft", "req.txt")
    c, f, w, u, summary, _, net = compute_verdict("MIT", [agpl])
    assert not c and f and net
    assert "AGPL" in summary or "network" in summary.lower() or "SaaS" in summary
    print("  compute_verdict: OK")

    adv = recommend_deploy(
        primary_language="Python",
        topics=["api"],
        dependencies=[
            Dependency("fastapi", None, "pypi", "pyproject.toml"),
            Dependency("uvicorn", None, "pypi", "pyproject.toml"),
        ],
        dependency_files=["pyproject.toml"],
        has_dockerfile=True,
    )
    assert adv and any(
        x in adv[0].platform for x in ("Railway", "Fly", "Render", "Cloud")
    ) or any("Railway" in a.platform for a in adv)
    print(f"  deploy_advisor: OK top={adv[0].platform} score={adv[0].score}")

    notice2 = build_copyright_notice("psf", "requests", "Apache-2.0")
    assert "psf" in notice2 and "Apache-2.0" in notice2
    assert "TEMPLATE" in notice2
    print("  copyright notice: OK")

    # SBOM export smoke
    sample = ScanResult(
        owner="psf",
        repo="requests",
        url="https://github.com/psf/requests",
        repo_license="Apache-2.0",
        packages=[
            PackageLicense(
                "httpx", "pypi", "BSD-3-Clause", "permissive", "requirements.txt",
                version_spec="0.27.0",
            ),
            PackageLicense(
                "bad", "pypi", "GPL-3.0", "strong_copyleft", "requirements.txt",
                is_dev=True,
            ),
        ],
        scan_complete=True,
        risk_score=10,
    )
    cdx = render_sbom(sample, "cyclonedx")
    assert '"bomFormat": "CycloneDX"' in cdx and "httpx" in cdx
    spdx = render_sbom(sample, "spdx")
    assert "SPDX-2.3" in spdx and "SPDXRef-Package" in spdx
    print("  sbom_export cyclonedx+spdx: OK")

    # Auth hash roundtrip
    from gls.auth import hash_password, verify_password, add_user, authenticate, delete_user

    rec = hash_password("test-password-99")
    assert verify_password("test-password-99", rec)
    assert not verify_password("wrong", rec)
    add_user("gls_test_user", "test-password-99")
    assert authenticate("gls_test_user", "test-password-99")
    delete_user("gls_test_user")
    print("  auth pbkdf2: OK")

    # Per-user history isolation
    from gls.history_store import append_scan, clear_history, load_history

    clear_history(user="gls_hist_a")
    clear_history(user="gls_hist_b")
    append_scan(sample, user="gls_hist_a")
    assert len(load_history(user="gls_hist_a")) == 1
    assert len(load_history(user="gls_hist_b")) == 0
    clear_history(user="gls_hist_a")
    print("  history per-user: OK")


async def timed_scan(url: str):
    t0 = time.perf_counter()
    r = await analyze_repository(url)
    ms = (time.perf_counter() - t0) * 1000
    return r, ms


async def test_integration():
    section("2) INTEGRATION SCANS + TIMING")
    jobs = [
        ("https://github.com/psf/requests", "psf/requests (python)"),
        ("https://github.com/encode/httpx", "encode/httpx (python)"),
        ("not-a-url", "bad-url"),
        ("https://github.com/psf/requests", "psf/requests WARM"),
    ]
    results = []
    for url, label in jobs:
        r, ms = await timed_scan(url)
        results.append((label, r, ms))
        counts = r.risk_counts()
        print(f"  [{ms:7.0f} ms] {label}")
        print(
            f"           owner={r.owner or '-'} lic={r.repo_license} "
            f"pkgs={len(r.packages)} sell={r.can_sell_closed} force={r.forces_open_source}"
        )
        print(
            f"           risks={counts} errors={len(r.errors)} deploy={len(r.deploy_advice)}"
        )
        if r.packages:
            sample = ", ".join(f"{p.name}:{p.license_id}" for p in r.packages[:4])
            print(f"           sample: {sample}")
    return results


def test_web_speed() -> dict:
    section("3) WEB UI SPEED (HTTP)")
    times: list[float] = []
    for i in range(5):
        t0 = time.perf_counter()
        try:
            resp = httpx.get("http://127.0.0.1:8080/", timeout=15.0, follow_redirects=True)
            ms = (time.perf_counter() - t0) * 1000
            times.append(ms)
            print(
                f"  GET /  try{i + 1}: {ms:6.1f} ms  "
                f"status={resp.status_code}  bytes={len(resp.content)}"
            )
        except Exception as exc:  # noqa: BLE001
            print(f"  GET /  try{i + 1}: FAIL {exc}")

    for path in ("/",):
        try:
            t0 = time.perf_counter()
            resp = httpx.get(f"http://127.0.0.1:8080{path}", timeout=10.0, follow_redirects=True)
            ms = (time.perf_counter() - t0) * 1000
            # Basic content checks
            body = resp.text
            has_title = "License" in body or "NiceGUI" in body or "gls" in body or len(body) > 100
            print(
                f"  content check: status={resp.status_code} "
                f"size={len(resp.content)} has_app_shell={has_title}"
            )
        except Exception as exc:  # noqa: BLE001
            print(f"  content check fail: {exc}")

    summary = {}
    if times:
        summary = {
            "avg": statistics.mean(times),
            "min": min(times),
            "max": max(times),
        }
        print(
            f"  homepage avg={summary['avg']:.1f} ms  "
            f"min={summary['min']:.1f}  max={summary['max']:.1f}"
        )
    return summary


async def test_batch():
    section("4) BATCH TIMING (2 repos sequential)")
    urls = [
        "https://github.com/psf/requests",
        "https://github.com/encode/httpx",
    ]
    t0 = time.perf_counter()
    outs = []
    for u in urls:
        outs.append(await analyze_repository(u))
    batch_ms = (time.perf_counter() - t0) * 1000
    print(f"  batch 2 repos sequential: {batch_ms:.0f} ms  ({batch_ms / 2:.0f} ms/repo avg)")
    for r in outs:
        print(f"    {r.owner}/{r.repo}: pkgs={len(r.packages)} force={r.forces_open_source}")
    return batch_ms


def test_live_assertions(loop_results) -> None:
    section("5) LIVE DATA ASSERTIONS")
    r = loop_results[0][1]
    assert r.owner == "psf" and r.repo == "requests"
    assert r.repo_license and "Apache" in str(r.repo_license)
    assert r.can_sell_closed is True
    assert r.forces_open_source is False
    assert len(r.packages) > 0
    assert r.copyright_notice
    assert r.deploy_advice
    print("  psf/requests live assertions: OK")

    rbad = loop_results[2][1]
    assert rbad.errors and not rbad.owner
    print("  bad URL handling: OK")

    ms1 = loop_results[0][2]
    ms2 = loop_results[3][2]
    print(f"  cold scan requests: {ms1:.0f} ms")
    print(f"  warm scan requests: {ms2:.0f} ms")
    print(f"  cache faster: {ms2 < ms1} (delta {ms1 - ms2:.0f} ms)")


def main() -> int:
    failures = 0
    try:
        test_units()
    except AssertionError as exc:
        print(f"  UNIT FAIL: {exc}")
        failures += 1
        raise

    loop_results = asyncio.run(test_integration())
    web = test_web_speed()
    batch_ms = asyncio.run(test_batch())
    try:
        test_live_assertions(loop_results)
    except AssertionError as exc:
        print(f"  LIVE FAIL: {exc}")
        failures += 1
        raise

    section("SUMMARY")
    scan_times = [x[2] for x in loop_results if x[1].owner]
    print(f"  Unit logic: PASS")
    print(f"  Integration scans: PASS ({len(scan_times)} successful)")
    if scan_times:
        print(
            f"  Scan times: avg={statistics.mean(scan_times):.0f} ms "
            f"min={min(scan_times):.0f} max={max(scan_times):.0f}"
        )
    if web:
        print(f"  Homepage: avg={web['avg']:.1f} ms")
    print(f"  Batch 2 repos: {batch_ms:.0f} ms")
    print(f"  Failures: {failures}")
    print("ALL CHECKS COMPLETED")
    return 0 if failures == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
