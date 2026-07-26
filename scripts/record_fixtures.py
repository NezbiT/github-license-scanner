"""
Record trimmed GitHub / registry API responses into tests/fixtures/*.json.

Run manually when a fixture needs refreshing:

    GITHUB_TOKEN=$(gh auth token) python scripts/record_fixtures.py

The output is committed so the test suite never touches the network.
Responses are trimmed to exactly the fields the scanner reads, and license
file bodies are truncated — keeping full LICENSE texts would add hundreds of
kilobytes of fixture for no extra coverage.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import httpx

REPO = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO))

from gls.github_api import _is_dependency_path, _is_docker_path, _prefer_root_sort_key  # noqa: E402
from gls.dependency_scanner import parse_many  # noqa: E402

OUT = REPO / "tests" / "fixtures"
GH = "https://api.github.com"
UA = "github-license-scanner/1.1 (license-lookup; educational)"
GH_HEADERS = {"Accept": "application/vnd.github+json", "User-Agent": UA,
              "X-GitHub-Api-Version": "2022-11-28"}
import os  # noqa: E402
if os.environ.get("GITHUB_TOKEN"):
    GH_HEADERS["Authorization"] = f"Bearer {os.environ['GITHUB_TOKEN']}"

LICENSE_CANDIDATES = ["LICENSE", "LICENSE.md", "LICENSE.txt",
                      "COPYING", "COPYING.txt", "COPYING.LIB"]

MAX_TEXT = 6000


def trim_npm(data):
    latest = (data.get("dist-tags") or {}).get("latest")
    versions = data.get("versions") or {}
    keep = {}
    if latest and latest in versions:
        v = versions[latest]
        keep[latest] = {k: v.get(k) for k in ("license", "licenses") if k in v}
    out = {"name": data.get("name"), "dist-tags": data.get("dist-tags"), "versions": keep}
    for k in ("license", "licenses"):
        if k in data:
            out[k] = data[k]
    return out


def trim_pypi(data):
    info = data.get("info") or {}
    lic = info.get("license")
    return {"info": {
        "name": info.get("name"),
        # long license bodies are truncated the same way the analyzer ignores them
        "license": (lic[:200] if isinstance(lic, str) else lic),
        "license_expression": info.get("license_expression"),
        "classifiers": [c for c in (info.get("classifiers") or [])
                        if isinstance(c, str) and c.startswith("License ::")],
    }}


def trim_crates(data):
    crate = data.get("crate") or {}
    return {
        "crate": {k: crate.get(k) for k in
                  ("name", "default_version", "max_stable_version", "newest_version")},
        "versions": [{k: v.get(k) for k in ("num", "license", "yanked")}
                     for v in (data.get("versions") or [])[:5]],
    }


def trim_packagist(data, name=None):
    packages = data.get("packages") or {}
    out = {}
    for key, entries in packages.items():
        if isinstance(entries, list) and entries:
            out[key] = [{"license": entries[0].get("license")}]
    return {"packages": out}


TRIMMERS = {"npm": trim_npm, "pypi": trim_pypi, "cargo": trim_crates,
            "composer": trim_packagist}


def record_repo(client: httpx.Client, owner: str, repo: str) -> dict:
    entries: dict[str, dict] = {}

    def get(url, headers=None, trim=None):
        r = client.get(url, headers=headers or GH_HEADERS, timeout=60,
                       follow_redirects=True)
        body = None
        if r.status_code == 200:
            try:
                body = r.json()
            except ValueError:
                body = None
            if trim and body is not None:
                body = trim(body)
        entries[url] = {"status": r.status_code, "json": body}
        print(f"  {r.status_code}  {url}")
        return r.status_code, body

    _, info = get(f"{GH}/repos/{owner}/{repo}")
    branch = info["default_branch"]

    # git tree, trimmed to paths the scanner actually inspects
    tree_url = f"{GH}/repos/{owner}/{repo}/git/trees/{branch}?recursive=1"
    r = client.get(tree_url, headers=GH_HEADERS, timeout=120, follow_redirects=True)
    tree = r.json().get("tree") or []
    kept = [i for i in tree if i.get("type") == "blob" and i.get("path")
            and (_is_dependency_path(i["path"]) or _is_docker_path(i["path"]))]
    entries[tree_url] = {"status": r.status_code,
                         "json": {"tree": [{"path": i["path"], "type": "blob"} for i in kept],
                                  "truncated": False}}
    print(f"  {r.status_code}  {tree_url}  ({len(kept)} of {len(tree)} paths kept)")

    dep_paths = sorted([i["path"] for i in kept if _is_dependency_path(i["path"])],
                       key=_prefer_root_sort_key)[:30]

    contents: dict[str, str] = {}
    for path in dep_paths:
        _, body = get(f"{GH}/repos/{owner}/{repo}/contents/{path}?ref={branch}")
        if body:
            import base64
            contents[path] = base64.b64decode(body.get("content") or "").decode(
                "utf-8", "replace")

    # license file probes (404s are recorded too — they drive the fallback order)
    for name in LICENSE_CANDIDATES:
        url = f"{GH}/repos/{owner}/{repo}/contents/{name}?ref={branch}"
        r = client.get(url, headers=GH_HEADERS, timeout=60, follow_redirects=True)
        body = None
        if r.status_code == 200:
            body = r.json()
            import base64
            text = base64.b64decode(body.get("content") or "").decode("utf-8", "replace")
            body = {"encoding": "utf-8-trimmed", "content": text[:MAX_TEXT],
                    "name": name, "size": body.get("size")}
        entries[url] = {"status": r.status_code, "json": body}
        print(f"  {r.status_code}  {url}")

    # root listing (finds oddly-named files like LICENSE-Community.txt)
    url = f"{GH}/repos/{owner}/{repo}/contents/?ref={branch}"
    r = client.get(url, headers=GH_HEADERS, timeout=60, follow_redirects=True)
    body = None
    if r.status_code == 200:
        body = [{"name": i["name"], "type": i["type"]} for i in r.json()]
    entries[url] = {"status": r.status_code, "json": body}
    print(f"  {r.status_code}  {url}  ({len(body or [])} entries)")

    # any extra license-ish root file, fetched so the fallback can read it
    for item in body or []:
        n = item["name"]
        if item["type"] != "file" or n in LICENSE_CANDIDATES:
            continue
        if not (n.upper().startswith("LICEN") or n.upper().startswith("COPYING")):
            continue
        u = f"{GH}/repos/{owner}/{repo}/contents/{n}?ref={branch}"
        r2 = client.get(u, headers=GH_HEADERS, timeout=60, follow_redirects=True)
        b2 = None
        if r2.status_code == 200:
            import base64
            raw = r2.json()
            text = base64.b64decode(raw.get("content") or "").decode("utf-8", "replace")
            b2 = {"encoding": "utf-8-trimmed", "content": text[:MAX_TEXT],
                  "name": n, "size": raw.get("size")}
        entries[u] = {"status": r2.status_code, "json": b2}
        print(f"  {r2.status_code}  {u}")

    # registry lookups for every parsed dependency
    for dep in parse_many(contents)[:80]:
        eco = dep.ecosystem
        if eco == "npm":
            u = f"https://registry.npmjs.org/{dep.name.replace('/', '%2F')}"
        elif eco == "pypi":
            u = f"https://pypi.org/pypi/{dep.name}/json"
        elif eco == "cargo":
            u = f"https://crates.io/api/v1/crates/{dep.name}"
        elif eco == "rubygems":
            u = f"https://rubygems.org/api/v1/gems/{dep.name}.json"
        elif eco == "composer" and "/" in dep.name:
            u = f"https://repo.packagist.org/p2/{dep.name}.json"
        else:
            continue
        if u in entries:
            continue
        get(u, headers={"User-Agent": UA}, trim=TRIMMERS.get(eco))

    return entries


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    targets = [("git", "git"), ("torvalds", "linux"),
               ("mongodb", "mongo"), ("psf", "requests")]
    with httpx.Client() as client:
        for owner, repo in targets:
            print(f"== {owner}/{repo}")
            entries = record_repo(client, owner, repo)
            path = OUT / f"{owner}__{repo}.json"
            path.write_text(json.dumps(entries, indent=1, sort_keys=True),
                            encoding="utf-8")
            print(f"-> {path} ({path.stat().st_size} bytes)\n")


if __name__ == "__main__":
    main()
