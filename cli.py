"""
Command-line interface for the GitHub License Scanner.

Usage examples:
  python cli.py scan https://github.com/psf/requests
  python cli.py batch urls.txt
  python cli.py history

Exit codes for `scan` / `batch`:
  0 — no strong copyleft force-open signal
  1 — forces_open_source is True (useful in CI gates)
  2 — hard failure (bad URL, network, usage error)
"""

from __future__ import annotations

import argparse
import asyncio
import sys
from pathlib import Path

from history_store import append_scan, load_history
from license_analyzer import analyze_repository
from models import ScanResult
from report import render_markdown_report
from sbom_export import render_sbom


def _print_result(result: ScanResult, verbose: bool = True) -> None:
    """Pretty-print a scan result to stdout."""
    title = f"{result.owner}/{result.repo}" if result.owner else result.url
    print("=" * 72)
    print(f"Repository : {title}")
    print(f"URL        : {result.url}")
    print(f"Scanned at : {result.scanned_at}")
    print(f"Repo license: {result.repo_license or 'Unknown'}")
    print(f"Language   : {result.primary_language or 'n/a'}")
    print("-" * 72)

    if result.errors and not result.packages and not result.repo_license:
        print("ERRORS:")
        for err in result.errors:
            print(f"  - {err}")
        print("=" * 72)
        return

    if not result.scan_complete:
        print("Scan complete      : NO (incomplete — do not treat verdict as reliable)")
    flag = "YES — strong copyleft may force opening source" if result.forces_open_source else "NO"
    if result.scan_complete and result.can_sell_closed:
        sell = "POSSIBLY (heuristic; attribution & counsel still required)"
    else:
        sell = "NO / UNDETERMINED"
    print(f"Risk score         : {result.risk_score}/100 ({result.risk_score_label})")
    print(f"Forces open source : {flag}")
    print(f"Can sell closed    : {sell}")
    if result.has_network_copyleft:
        print("Network copyleft   : YES (AGPL/SSPL-class — SaaS obligations possible)")
    if result.strong_copyleft_dev_only:
        print("Dev-only copyleft  : YES (strong copyleft only in dev deps)")
    print()
    print("Verdict:")
    print(f"  {result.verdict_summary}")
    print()

    counts = result.risk_counts()
    prod_counts = result.risk_counts(prod_only=True)
    print(
        f"Packages analyzed: {len(result.packages)}  "
        f"(prod={result.prod_package_count}, dev={result.dev_package_count})"
    )
    print(
        f"  all  [permissive={counts['permissive']}, "
        f"weak_copyleft={counts['weak_copyleft']}, "
        f"strong_copyleft={counts['strong_copyleft']}, "
        f"unknown={counts['unknown']}]"
    )
    print(
        f"  prod [permissive={prod_counts['permissive']}, "
        f"weak_copyleft={prod_counts['weak_copyleft']}, "
        f"strong_copyleft={prod_counts['strong_copyleft']}, "
        f"unknown={prod_counts['unknown']}]"
    )

    if verbose and result.grouped:
        print()
        print("Packages by license:")
        for lic, pkgs in result.grouped.items():
            risks = {p.risk for p in pkgs}
            risk_label = ",".join(sorted(risks))
            print(f"  [{risk_label}] {lic} ({len(pkgs)})")
            for p in sorted(pkgs, key=lambda x: x.name.lower())[:15]:
                scope = "dev" if p.is_dev else "prod"
                print(f"      - {p.name} ({p.ecosystem}/{scope}) from {p.source_file}")
            if len(pkgs) > 15:
                print(f"      … and {len(pkgs) - 15} more")

    if result.replacements:
        print()
        print("Replacement suggestions (heuristic):")
        for rep in result.replacements[:20]:
            print(f"  * {rep.package} [{rep.license_id or '?'}] ({rep.ecosystem})")
            for alt in rep.alternatives:
                print(f"      → {alt}")

    if result.deploy_advice:
        print()
        print("Deploy recommendations:")
        for adv in result.deploy_advice:
            print(f"  • {adv.platform} (score={adv.score})")
            for reason in adv.reasons[:3]:
                print(f"      - {reason}")
            print(f"      docs: {adv.docs_url}")

    if result.copyright_notice:
        print()
        print("Copyright notice:")
        print("-" * 40)
        print(result.copyright_notice)
        print("-" * 40)

    if result.errors:
        print()
        print("Notes / soft errors:")
        for err in result.errors:
            print(f"  - {err}")

    print("=" * 72)


async def cmd_scan(
    url: str,
    save: bool = True,
    verbose: bool = True,
    markdown_path: str | None = None,
    sbom_path: str | None = None,
    sbom_format: str = "cyclonedx",
) -> int:
    """Scan a single repository URL. Returns process exit code."""
    print(f"Scanning {url} …")
    result = await analyze_repository(url)
    _print_result(result, verbose=verbose)

    if markdown_path:
        md = render_markdown_report(result)
        out = Path(markdown_path)
        out.write_text(md, encoding="utf-8")
        print(f"Markdown report written to {out}")

    if sbom_path:
        try:
            doc = render_sbom(result, sbom_format)
            out = Path(sbom_path)
            out.write_text(doc, encoding="utf-8")
            print(f"SBOM ({sbom_format}) written to {out}")
        except ValueError as exc:
            print(f"SBOM export failed: {exc}", file=sys.stderr)
            return 2

    if save and result.owner and result.scan_complete:
        append_scan(result)
        print("Saved to history.")

    if result.errors and not result.owner:
        return 2
    if not result.scan_complete:
        return 2
    if result.errors and not result.packages and result.repo_license is None:
        if any(
            any(k in e.lower() for k in ("not found", "rate limit", "forbidden", "exceeded"))
            for e in result.errors
        ):
            return 2
    return 1 if result.forces_open_source else 0


async def cmd_batch(file_path: str, save: bool = True) -> int:
    """Scan multiple URLs listed in a text file (one per line)."""
    path = Path(file_path)
    if not path.exists():
        print(f"File not found: {file_path}", file=sys.stderr)
        return 2

    urls = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if line and not line.startswith("#"):
            urls.append(line)

    if not urls:
        print("No URLs found in file.", file=sys.stderr)
        return 2

    exit_code = 0
    for i, url in enumerate(urls, 1):
        print(f"\n[{i}/{len(urls)}] ", end="")
        code = await cmd_scan(url, save=save, verbose=True)
        if code == 2:
            exit_code = 2
        elif code == 1 and exit_code != 2:
            exit_code = 1
    return exit_code


def cmd_history() -> int:
    """Print saved scan history."""
    entries = load_history()
    if not entries:
        print("No history yet. Run a scan first.")
        return 0
    print(f"History ({len(entries)} entries):\n")
    for e in entries:
        sell = "closed-OK" if e.get("can_sell_closed") else "OPEN-FORCE"
        print(
            f"  {e.get('scanned_at', '?'):<22}  "
            f"{e.get('owner', '?')}/{e.get('repo', '?'):<30}  "
            f"lic={e.get('repo_license') or '?':<12}  "
            f"pkgs={e.get('package_count', 0):<4}  "
            f"{sell}"
        )
    return 0


def build_parser() -> argparse.ArgumentParser:
    """Create the CLI argument parser."""
    parser = argparse.ArgumentParser(
        prog="cli.py",
        description="GitHub License Scanner — analyze repo & dependency licenses.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p_scan = sub.add_parser("scan", help="Scan a single GitHub repository URL")
    p_scan.add_argument("url", help="GitHub repository URL or owner/repo")
    p_scan.add_argument("--no-save", action="store_true", help="Do not write history")
    p_scan.add_argument(
        "--markdown",
        metavar="PATH",
        help="Write a Markdown report to PATH (e.g. report.md)",
    )
    p_scan.add_argument(
        "--sbom",
        metavar="PATH",
        help="Write an SBOM JSON file to PATH (CycloneDX or SPDX)",
    )
    p_scan.add_argument(
        "--sbom-format",
        choices=("cyclonedx", "spdx"),
        default="cyclonedx",
        help="SBOM format when using --sbom (default: cyclonedx)",
    )

    p_batch = sub.add_parser("batch", help="Scan URLs from a text file")
    p_batch.add_argument("file", help="Path to text file with one URL per line")
    p_batch.add_argument("--no-save", action="store_true", help="Do not write history")

    sub.add_parser("history", help="Show previous scan history")

    p_user = sub.add_parser("user-add", help="Add a web UI user (multi-user auth)")
    p_user.add_argument("username", help="Username (letters, digits, _ . -)")
    sub.add_parser("user-list", help="List web UI users")

    return parser


def main(argv: list[str] | None = None) -> int:
    """CLI entrypoint."""
    parser = build_parser()
    args = parser.parse_args(argv)

    if args.command == "scan":
        return asyncio.run(
            cmd_scan(
                args.url,
                save=not args.no_save,
                markdown_path=args.markdown,
                sbom_path=args.sbom,
                sbom_format=args.sbom_format,
            )
        )
    if args.command == "batch":
        return asyncio.run(cmd_batch(args.file, save=not args.no_save))
    if args.command == "history":
        return cmd_history()
    if args.command == "user-add":
        from auth import add_user

        import getpass

        pw = getpass.getpass("Password: ")
        pw2 = getpass.getpass("Confirm: ")
        if pw != pw2:
            print("Passwords do not match", file=sys.stderr)
            return 2
        try:
            add_user(args.username, pw)
        except ValueError as exc:
            print(exc, file=sys.stderr)
            return 2
        print(f"User {args.username!r} created. Set GLS_AUTH_ENABLED=1 to require login.")
        return 0
    if args.command == "user-list":
        from auth import list_usernames

        names = list_usernames()
        if not names:
            print("No users yet. Run: python cli.py user-add <name>")
        else:
            for n in names:
                print(n)
        return 0

    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
