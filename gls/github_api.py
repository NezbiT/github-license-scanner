"""
GitHub REST API helpers.

Responsibilities:
  - Parse GitHub repository URLs into (owner, repo)
  - Fetch repository metadata (license, language, topics, default branch)
  - Walk the git tree to locate dependency manifest files
  - Download file contents for parsing

Uses httpx for all HTTP calls. Optional GITHUB_TOKEN env var raises rate limits.

Security:
  - Only the official api.github.com host is contacted (no user-controlled hosts).
  - Owner/repo are validated against a strict charset before interpolation.
"""

from __future__ import annotations

import asyncio
import base64
import re
from typing import Any

import httpx

try:
    from .config import GITHUB_TOKEN, MAX_DEPENDENCY_FILES, USER_AGENT
except Exception:  # noqa: BLE001
    import os

    GITHUB_TOKEN = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    MAX_DEPENDENCY_FILES = 30
    USER_AGENT = "github-license-scanner/1.1 (educational)"

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

GITHUB_API = "https://api.github.com"

# Reserved / non-repo path segments that must never be treated as owner/repo
_RESERVED_OWNERS = {
    "settings",
    "marketplace",
    "explore",
    "topics",
    "notifications",
    "login",
    "join",
    "features",
    "pricing",
    "about",
    "site",
    "orgs",
    "users",
    "search",
    "pulls",
    "issues",
    "codespaces",
    "sponsors",
    "customer-stories",
    "team",
    "enterprise",
    "security",
    "readme",
}

# Path patterns that identify dependency manifests.
# Each entry: (basename_regex or exact basename, preferred weight for sorting)
DEPENDENCY_BASENAMES = {
    "package.json",
    "package-lock.json",  # we skip lockfiles in scanner; listed only for detection skip
    "requirements.txt",
    "pyproject.toml",
    "setup.py",
    "Pipfile",
    "Cargo.toml",
    "go.mod",
    "Gemfile",
    "composer.json",
    "pom.xml",
    "build.gradle",
    "build.gradle.kts",
}

# requirements-dev.txt, requirements-prod.txt, etc.
REQUIREMENTS_GLOB = re.compile(r"^requirements(-[\w.-]+)?\.txt$", re.IGNORECASE)

# License files probed when GitHub's own detector returns "other"/NOASSERTION.
# Ordered: the most conventional names first.
LICENSE_FILE_CANDIDATES = (
    "LICENSE",
    "LICENSE.md",
    "LICENSE.txt",
    "COPYING",
    "COPYING.txt",
    "COPYING.LIB",
)

# Root files worth reading when none of the candidates above exist.
# mongodb/mongo, for example, ships only LICENSE-Community.txt.
_LICENSE_FILE_PREFIXES = ("LICENSE", "LICENCE", "COPYING")

# Docker-related files used by deploy_advisor signals
DOCKER_BASENAMES = {
    "Dockerfile",
    "dockerfile",
    "docker-compose.yml",
    "docker-compose.yaml",
    "compose.yml",
    "compose.yaml",
}


class GitHubAPIError(Exception):
    """Raised when GitHub API returns an error or the repo cannot be read."""

    def __init__(self, message: str, status_code: int | None = None):
        super().__init__(message)
        self.status_code = status_code


# ---------------------------------------------------------------------------
# URL parsing
# ---------------------------------------------------------------------------

_URL_PATTERNS = [
    # https://github.com/owner/repo[.git][/...]
    re.compile(
        r"(?:https?://)?(?:www\.)?github\.com/"
        r"(?P<owner>[A-Za-z0-9_.-]+)/"
        r"(?P<repo>[A-Za-z0-9_.-]+?)(?:\.git)?(?:/.*)?$",
        re.IGNORECASE,
    ),
    # git@github.com:owner/repo.git
    re.compile(
        r"git@github\.com:"
        r"(?P<owner>[A-Za-z0-9_.-]+)/"
        r"(?P<repo>[A-Za-z0-9_.-]+?)(?:\.git)?$",
        re.IGNORECASE,
    ),
    # ssh://git@github.com/owner/repo.git
    re.compile(
        r"ssh://git@github\.com/"
        r"(?P<owner>[A-Za-z0-9_.-]+)/"
        r"(?P<repo>[A-Za-z0-9_.-]+?)(?:\.git)?$",
        re.IGNORECASE,
    ),
]


def parse_github_url(url: str) -> tuple[str, str]:
    """
    Extract (owner, repo) from a GitHub URL or shorthand.

    Accepts:
      - https://github.com/owner/repo
      - https://github.com/owner/repo.git
      - https://github.com/owner/repo/tree/main/...
      - git@github.com:owner/repo.git
      - owner/repo  (shorthand)

    Raises:
        ValueError: if the URL cannot be parsed as a GitHub repository.
    """
    text = (url or "").strip()
    if not text:
        raise ValueError("Empty GitHub URL")

    # Reject URL schemes other than http(s)/git/ssh shorthand to avoid SSRF-style abuse
    if "://" in text:
        scheme = text.split("://", 1)[0].lower()
        if scheme not in {"http", "https", "ssh", "git"}:
            raise ValueError(f"Unsupported URL scheme: {scheme!r}")

    # Shorthand: owner/repo
    if re.fullmatch(r"[A-Za-z0-9_.-]+/[A-Za-z0-9_.-]+", text):
        owner, repo = text.split("/", 1)
        return _validate_owner_repo(owner, repo.removesuffix(".git"))

    for pattern in _URL_PATTERNS:
        match = pattern.match(text)
        if match:
            owner = match.group("owner")
            repo = match.group("repo").removesuffix(".git")
            return _validate_owner_repo(owner, repo)

    raise ValueError(f"Not a valid GitHub repository URL: {url!r}")


def _validate_owner_repo(owner: str, repo: str) -> tuple[str, str]:
    """Validate and normalize owner/repo identifiers."""
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", owner or ""):
        raise ValueError(f"Invalid GitHub owner: {owner!r}")
    if not re.fullmatch(r"[A-Za-z0-9_.-]+", repo or ""):
        raise ValueError(f"Invalid GitHub repository name: {repo!r}")
    if owner.lower() in _RESERVED_OWNERS:
        raise ValueError(f"Not a repository path (reserved segment): {owner!r}")
    if len(owner) > 100 or len(repo) > 100:
        raise ValueError("Owner or repository name is too long")
    return owner, repo


# ---------------------------------------------------------------------------
# HTTP client helpers
# ---------------------------------------------------------------------------

def _auth_headers() -> dict[str, str]:
    """Build default headers, attaching GITHUB_TOKEN when available."""
    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": USER_AGENT,
        "X-GitHub-Api-Version": "2022-11-28",
    }
    if GITHUB_TOKEN:
        headers["Authorization"] = f"Bearer {GITHUB_TOKEN}"
    return headers


def create_client(
    timeout: float = 30.0,
    transport: httpx.AsyncBaseTransport | None = None,
) -> httpx.AsyncClient:
    """
    Create a configured async httpx client for GitHub API calls.

    `transport` is a test seam: passing an httpx.MockTransport lets the suite
    replay recorded fixtures without network access.
    """
    return httpx.AsyncClient(
        base_url=GITHUB_API,
        headers=_auth_headers(),
        timeout=timeout,
        follow_redirects=True,
        transport=transport,
        # Never follow redirects off github.com for API paths
        # (httpx still only uses our base_url paths when we pass relative paths)
    )


async def _get_json(client: httpx.AsyncClient, path: str) -> Any:
    """
    GET a GitHub API path and return parsed JSON.

    Raises GitHubAPIError with a human-readable message on failure.
    """
    # Paths must be relative API routes — never absolute external URLs
    if path.startswith("http://") or path.startswith("https://"):
        raise GitHubAPIError("Refusing absolute URL in GitHub API client")

    response = await client.get(path)
    if response.status_code == 404:
        raise GitHubAPIError(
            "Repository not found (or private without a valid GITHUB_TOKEN).",
            status_code=404,
        )
    if response.status_code == 403:
        remaining = response.headers.get("X-RateLimit-Remaining", "?")
        reset = response.headers.get("X-RateLimit-Reset", "?")
        retry_after = response.headers.get("Retry-After", "")
        extra = f" Retry-After: {retry_after}." if retry_after else ""
        raise GitHubAPIError(
            f"GitHub API forbidden (rate limit or permissions). "
            f"Remaining: {remaining}, reset: {reset}.{extra} "
            f"Set GITHUB_TOKEN for higher limits.",
            status_code=403,
        )
    if response.status_code == 401:
        raise GitHubAPIError(
            "GitHub authentication failed. Check GITHUB_TOKEN.",
            status_code=401,
        )
    if response.status_code == 429:
        retry_after = response.headers.get("Retry-After", "?")
        raise GitHubAPIError(
            f"GitHub API rate limit exceeded. Retry-After: {retry_after}. "
            f"Set GITHUB_TOKEN or wait before scanning again.",
            status_code=429,
        )
    if response.status_code >= 400:
        # Do not echo large response bodies (may contain tokens in rare edge cases)
        body = (response.text or "")[:180].replace("\n", " ")
        raise GitHubAPIError(
            f"GitHub API error {response.status_code}: {body}",
            status_code=response.status_code,
        )
    return response.json()


# ---------------------------------------------------------------------------
# Repository metadata
# ---------------------------------------------------------------------------

async def get_repo_info(
    client: httpx.AsyncClient,
    owner: str,
    repo: str,
) -> dict[str, Any]:
    """
    Fetch repository metadata from GET /repos/{owner}/{repo}.

    Returns a normalized dict with keys:
      license_spdx, license_name, default_branch, language, description,
      topics, html_url, full_name
    """
    data = await _get_json(client, f"/repos/{owner}/{repo}")

    license_info = data.get("license") or {}
    # GitHub may return null license when LICENSE file is missing/custom
    license_spdx = license_info.get("spdx_id") if license_info else None
    # "NOASSERTION" means GitHub could not determine the license
    if license_spdx in (None, "NOASSERTION", "NONE"):
        license_spdx = None

    return {
        "owner": owner,
        "repo": repo,
        "full_name": data.get("full_name", f"{owner}/{repo}"),
        "html_url": data.get("html_url", f"https://github.com/{owner}/{repo}"),
        "description": data.get("description"),
        "default_branch": data.get("default_branch") or "main",
        "language": data.get("language"),
        "topics": data.get("topics") or [],
        "license_spdx": license_spdx,
        "license_name": license_info.get("name") if license_info else None,
        "license_url": license_info.get("url") if license_info else None,
        "private": bool(data.get("private")),
    }


# ---------------------------------------------------------------------------
# Tree walking & file download
# ---------------------------------------------------------------------------

def _is_dependency_path(path: str) -> bool:
    """Return True if the path looks like a dependency manifest we can parse."""
    name = path.rsplit("/", 1)[-1]
    # Skip lockfiles (they duplicate package.json / Cargo.lock noise)
    if name in {
        "package-lock.json",
        "yarn.lock",
        "pnpm-lock.yaml",
        "Cargo.lock",
        "poetry.lock",
        "Pipfile.lock",
        "composer.lock",
        "go.sum",
    }:
        return False
    if name in DEPENDENCY_BASENAMES:
        return True
    if REQUIREMENTS_GLOB.match(name):
        return True
    return False


def _is_docker_path(path: str) -> bool:
    """Return True if path is a Docker-related config file."""
    name = path.rsplit("/", 1)[-1]
    return name in DOCKER_BASENAMES


def _prefer_root_sort_key(path: str) -> tuple[int, int, str]:
    """
    Sort key that prefers root-level manifests over deep nested ones.

    Root files (depth 0) first, then shallower paths, then alphabetical.
    """
    depth = path.count("/")
    # Prefer well-known root names slightly
    name = path.rsplit("/", 1)[-1]
    priority = 0 if name in {
        "package.json",
        "requirements.txt",
        "pyproject.toml",
        "Cargo.toml",
        "go.mod",
        "composer.json",
        "Gemfile",
        "pom.xml",
    } else 1
    return (depth, priority, path.lower())


async def list_repo_files(
    client: httpx.AsyncClient,
    owner: str,
    repo: str,
    branch: str,
) -> list[str]:
    """
    List all file paths in the repository via the recursive git tree API.

    Returns an empty list if the tree is too large or truncated without paths.
    """
    data = await _get_json(
        client,
        f"/repos/{owner}/{repo}/git/trees/{branch}?recursive=1",
    )
    tree = data.get("tree") or []
    paths: list[str] = []
    for item in tree:
        if item.get("type") == "blob" and item.get("path"):
            paths.append(item["path"])
    return paths


async def find_dependency_files(
    client: httpx.AsyncClient,
    owner: str,
    repo: str,
    branch: str,
) -> tuple[list[str], bool]:
    """
    Discover dependency manifest paths and whether a Dockerfile exists.

    Returns:
        (dependency_paths, has_dockerfile)
    """
    try:
        all_paths = await list_repo_files(client, owner, repo, branch)
    except GitHubAPIError:
        # Fall back to probing common root files only
        return await _probe_root_manifests(client, owner, repo), False

    dep_paths = [p for p in all_paths if _is_dependency_path(p)]
    dep_paths.sort(key=_prefer_root_sort_key)
    dep_paths = dep_paths[:MAX_DEPENDENCY_FILES]

    has_docker = any(_is_docker_path(p) for p in all_paths)
    return dep_paths, has_docker


async def _probe_root_manifests(
    client: httpx.AsyncClient,
    owner: str,
    repo: str,
) -> list[str]:
    """
    Probe common root-level dependency files one by one.

    Used when the recursive tree API fails (rare / truncated trees).
    """
    candidates = [
        "package.json",
        "requirements.txt",
        "pyproject.toml",
        "setup.py",
        "Pipfile",
        "Cargo.toml",
        "go.mod",
        "Gemfile",
        "composer.json",
        "pom.xml",
        "build.gradle",
        "build.gradle.kts",
    ]
    found: list[str] = []
    for path in candidates:
        try:
            response = await client.get(f"/repos/{owner}/{repo}/contents/{path}")
            if response.status_code == 200:
                found.append(path)
        except httpx.HTTPError:
            continue
    return found


async def get_file_content(
    client: httpx.AsyncClient,
    owner: str,
    repo: str,
    path: str,
    ref: str | None = None,
) -> str:
    """
    Download a text file from the repository and return decoded UTF-8 content.

    Uses the Contents API (base64) which works for files up to 1 MB.
    """
    api_path = f"/repos/{owner}/{repo}/contents/{path}"
    if ref:
        api_path += f"?ref={ref}"

    data = await _get_json(client, api_path)

    # Directory response is a list — not a file
    if isinstance(data, list):
        raise GitHubAPIError(f"Path is a directory, not a file: {path}")

    encoding = data.get("encoding")
    content = data.get("content") or ""
    if encoding == "base64":
        try:
            raw = base64.b64decode(content)
            return raw.decode("utf-8", errors="replace")
        except Exception as exc:  # noqa: BLE001
            raise GitHubAPIError(f"Failed to decode {path}: {exc}") from exc

    # Some responses may return raw content (unlikely with default Accept)
    if isinstance(content, str):
        return content

    raise GitHubAPIError(f"Unexpected content payload for {path}")


async def _list_root_license_files(
    client: httpx.AsyncClient,
    owner: str,
    repo: str,
    ref: str | None = None,
    exclude: tuple[str, ...] = (),
) -> list[str]:
    """
    List root-level files whose name looks like a license file.

    Used only after the conventional candidate names all 404, to catch
    projects that ship e.g. LICENSE-Community.txt or COPYING-GPL.
    """
    api_path = f"/repos/{owner}/{repo}/contents/"
    if ref:
        api_path += f"?ref={ref}"
    try:
        data = await _get_json(client, api_path)
    except (GitHubAPIError, httpx.HTTPError):
        return []
    if not isinstance(data, list):
        return []

    skip = {name.upper() for name in exclude}
    found: list[str] = []
    for item in data:
        if not isinstance(item, dict) or item.get("type") != "file":
            continue
        name = item.get("name") or ""
        upper = name.upper()
        if upper in skip:
            continue
        if upper.startswith(_LICENSE_FILE_PREFIXES):
            found.append(name)
    return sorted(found)


async def fetch_license_text(
    client: httpx.AsyncClient,
    owner: str,
    repo: str,
    ref: str | None = None,
) -> tuple[str | None, str | None]:
    """
    Download the repository's license file for text-based detection.

    Called when GitHub's licensee-backed detector reports "other" or
    NOASSERTION, which it does for any LICENSE/COPYING file it cannot match
    verbatim — git's COPYING has a preamble that defeats it, for instance.

    Returns:
        (path, text) for the first readable license file, else (None, None).
    """
    for name in LICENSE_FILE_CANDIDATES:
        try:
            text = await get_file_content(client, owner, repo, name, ref=ref)
        except (GitHubAPIError, httpx.HTTPError):
            continue
        if text and text.strip():
            return name, text

    for name in await _list_root_license_files(
        client, owner, repo, ref=ref, exclude=LICENSE_FILE_CANDIDATES
    ):
        try:
            text = await get_file_content(client, owner, repo, name, ref=ref)
        except (GitHubAPIError, httpx.HTTPError):
            continue
        if text and text.strip():
            return name, text

    return None, None


async def download_dependency_files(
    client: httpx.AsyncClient,
    owner: str,
    repo: str,
    paths: list[str],
    ref: str | None = None,
) -> dict[str, str]:
    """
    Download multiple dependency files concurrently (bounded).

    Returns a mapping of path -> text content. Failed downloads are skipped
    (caller can treat missing keys as soft errors).
    """
    result: dict[str, str] = {}
    if not paths:
        return result

    semaphore = asyncio.Semaphore(6)

    async def one(path: str) -> tuple[str, str | None]:
        async with semaphore:
            try:
                content = await get_file_content(client, owner, repo, path, ref=ref)
                return path, content
            except (GitHubAPIError, httpx.HTTPError):
                return path, None

    pairs = await asyncio.gather(*(one(p) for p in paths))
    for path, content in pairs:
        if content is not None:
            result[path] = content
    return result
