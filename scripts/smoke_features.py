import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from dependency_scanner import parse_dependencies
from license_analyzer import analyze_repository, compute_risk_score, compute_verdict
from models import PackageLicense
from report import render_markdown_report


def test_units() -> None:
    deps = parse_dependencies(
        "package.json",
        '{"dependencies":{"react":"1"},"devDependencies":{"vite":"5"}}',
    )
    assert any(d.name == "react" and not d.is_dev for d in deps)
    assert any(d.name == "vite" and d.is_dev for d in deps)

    prod_strong = PackageLicense(
        "x", "pypi", "GPL-3.0", "strong_copyleft", "r", is_dev=False
    )
    dev_strong = PackageLicense(
        "y", "pypi", "GPL-3.0", "strong_copyleft", "r", is_dev=True
    )
    c, f, _w, _u, _s, dev_only = compute_verdict("MIT", [dev_strong])
    assert c and not f and dev_only
    c, f, _w, _u, _s, dev_only = compute_verdict("MIT", [prod_strong])
    assert not c and f and not dev_only
    score, label = compute_risk_score("MIT", [prod_strong])
    assert score > 15 and label in {"low", "medium", "high", "minimal"}
    print("units OK")


async def test_live() -> None:
    r = await analyze_repository("https://github.com/psf/requests")
    print(
        r.owner,
        "score",
        r.risk_score,
        r.risk_score_label,
        "prod",
        r.prod_package_count,
        "dev",
        r.dev_package_count,
        "sell",
        r.can_sell_closed,
    )
    md = render_markdown_report(r)
    assert "Risk score" in md and r.owner in md
    print("md_chars", len(md))
    print("scopes", [(p.name, p.is_dev) for p in r.packages])
    print("live OK")


if __name__ == "__main__":
    test_units()
    asyncio.run(test_live())
