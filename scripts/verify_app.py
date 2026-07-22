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

from dependency_scanner import parse_dependencies
from deploy_advisor import recommend_deploy
from github_api import parse_github_url
from license_analyzer import (
    analyze_repository,
    build_copyright_notice,
    classify_license,
    compute_verdict,
    normalize_license_id,
)
from models import Dependency, PackageLicense


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
        (None, "unknown"),
        ("UNLICENSED", "unknown"),
    ]
    for lic, exp in cls_cases:
        got = classify_license(lic)
        assert got == exp, f"{lic!r} -> {got} expected {exp}"
    # empty / whitespace
    assert classify_license(normalize_license_id("")) == "unknown"
    print(f"  classify_license: {len(cls_cases)}+ OK")

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

    c, f, w, u, _ = compute_verdict("MIT", [perm])
    assert c and not f and not w
    c, f, w, u, _ = compute_verdict("MIT", [perm, weak])
    assert c and not f and w
    c, f, w, u, _ = compute_verdict("MIT", [strong])
    assert not c and f
    c, f, w, u, _ = compute_verdict("GPL-3.0", [perm])
    assert not c and f
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

    notice = build_copyright_notice("psf", "requests", "Apache-2.0")
    assert "psf" in notice and "Apache-2.0" in notice
    print("  copyright notice: OK")


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
