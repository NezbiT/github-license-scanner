"""
Dependency manifest parsers for multiple language ecosystems.

Each parser receives file path + text content and returns a list of Dependency
objects. The public entry point is parse_dependencies(path, content).

Uses the packaging library for robust Python requirement parsing.
"""

from __future__ import annotations

import json
import re
import tomllib
from typing import Callable

from packaging.requirements import InvalidRequirement, Requirement

from models import Dependency

# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse_dependencies(path: str, content: str) -> list[Dependency]:
    """
    Parse a dependency file and return declared packages.

    The parser is chosen from the file basename. Unknown files yield [].
    """
    basename = path.replace("\\", "/").rsplit("/", 1)[-1]
    lower = basename.lower()

    if lower == "package.json":
        return _parse_package_json(path, content)
    if lower == "pyproject.toml":
        return _parse_pyproject_toml(path, content)
    if lower == "cargo.toml":
        return _parse_cargo_toml(path, content)
    if lower == "go.mod":
        return _parse_go_mod(path, content)
    if lower == "gemfile":
        return _parse_gemfile(path, content)
    if lower == "composer.json":
        return _parse_composer_json(path, content)
    if lower == "pom.xml":
        return _parse_pom_xml(path, content)
    if lower in {"build.gradle", "build.gradle.kts"}:
        return _parse_gradle(path, content)
    if lower == "pipfile":
        return _parse_pipfile(path, content)
    if lower == "setup.py":
        return _parse_setup_py(path, content)
    if re.match(r"^requirements(-[\w.-]+)?\.txt$", lower):
        return _parse_requirements_txt(path, content)

    return []


def parse_many(files: dict[str, str]) -> list[Dependency]:
    """
    Parse multiple path -> content mappings and deduplicate by (ecosystem, name).

    First occurrence wins (prefer root files if caller sorted them that way).
    """
    seen: set[tuple[str, str]] = set()
    result: list[Dependency] = []
    for path, content in files.items():
        for dep in parse_dependencies(path, content):
            key = (dep.ecosystem, dep.name.lower())
            if key in seen:
                continue
            seen.add(key)
            result.append(dep)
    return result


# ---------------------------------------------------------------------------
# npm / package.json
# ---------------------------------------------------------------------------

def _parse_package_json(path: str, content: str) -> list[Dependency]:
    """Extract dependencies and devDependencies from package.json."""
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return []

    deps: list[Dependency] = []
    for section in ("dependencies", "devDependencies", "optionalDependencies", "peerDependencies"):
        block = data.get(section) or {}
        if not isinstance(block, dict):
            continue
        for name, version in block.items():
            if not name or name.startswith("@"):
                # Scoped packages like @scope/name are valid — keep them
                pass
            if not isinstance(name, str):
                continue
            version_spec = str(version) if version is not None else None
            # Skip workspace protocol / file: local refs for registry lookup
            if version_spec and (
                version_spec.startswith("workspace:")
                or version_spec.startswith("file:")
                or version_spec.startswith("link:")
            ):
                continue
            deps.append(
                Dependency(
                    name=name,
                    version_spec=version_spec,
                    ecosystem="npm",
                    source_file=path,
                )
            )
    return deps


# ---------------------------------------------------------------------------
# Python — requirements.txt / pyproject.toml / Pipfile / setup.py
# ---------------------------------------------------------------------------

def _parse_requirement_line(line: str) -> tuple[str, str | None] | None:
    """
    Parse a single requirements.txt-style line into (name, version_spec).

    Returns None for comments, blank lines, flags, and editable/VCS installs.
    """
    # Strip inline comments
    if "#" in line:
        line = line[: line.index("#")]
    line = line.strip()
    if not line:
        return None
    # pip options: -r, -e, --index-url, etc.
    if line.startswith("-"):
        return None
    # VCS / URL installs
    if re.match(r"^(git\+|hg\+|svn\+|bzr\+|https?://|svn\+)", line, re.I):
        return None
    if line.startswith("."):
        return None

    # Environment markers: package>=1; python_version>="3.10"
    req_part = line.split(";", 1)[0].strip()
    # Extras: package[extra]>=1.0
    try:
        req = Requirement(req_part)
        name = req.name
        version_spec = str(req.specifier) if req.specifier else None
        return name, version_spec or None
    except InvalidRequirement:
        # Fallback: crude name extraction
        m = re.match(r"^([A-Za-z0-9_.-]+)", req_part)
        if m:
            return m.group(1), None
        return None


def _parse_requirements_txt(path: str, content: str) -> list[Dependency]:
    """Parse classic pip requirements files."""
    deps: list[Dependency] = []
    for raw_line in content.splitlines():
        parsed = _parse_requirement_line(raw_line)
        if not parsed:
            continue
        name, version_spec = parsed
        deps.append(
            Dependency(
                name=name,
                version_spec=version_spec,
                ecosystem="pypi",
                source_file=path,
            )
        )
    return deps


def _parse_pyproject_toml(path: str, content: str) -> list[Dependency]:
    """
    Parse PEP 621, Poetry, and PDM dependency sections from pyproject.toml.
    """
    try:
        data = tomllib.loads(content)
    except Exception:  # noqa: BLE001 — invalid TOML
        return []

    deps: list[Dependency] = []
    seen: set[str] = set()

    def add_req_string(req_str: str) -> None:
        parsed = _parse_requirement_line(req_str)
        if not parsed:
            return
        name, version_spec = parsed
        key = name.lower()
        if key in seen:
            return
        seen.add(key)
        deps.append(
            Dependency(
                name=name,
                version_spec=version_spec,
                ecosystem="pypi",
                source_file=path,
            )
        )

    # PEP 621: [project] dependencies
    project = data.get("project") or {}
    for item in project.get("dependencies") or []:
        if isinstance(item, str):
            add_req_string(item)

    # optional-dependencies: { group: [reqs] }
    optional = project.get("optional-dependencies") or {}
    if isinstance(optional, dict):
        for group_reqs in optional.values():
            if isinstance(group_reqs, list):
                for item in group_reqs:
                    if isinstance(item, str):
                        add_req_string(item)

    # Poetry: [tool.poetry.dependencies] / group.dev
    poetry = (data.get("tool") or {}).get("poetry") or {}
    for section_name in ("dependencies", "dev-dependencies"):
        block = poetry.get(section_name) or {}
        if not isinstance(block, dict):
            continue
        for name, spec in block.items():
            if name.lower() == "python":
                continue
            key = name.lower()
            if key in seen:
                continue
            seen.add(key)
            version_spec = None
            if isinstance(spec, str):
                version_spec = spec
            elif isinstance(spec, dict):
                version_spec = str(spec.get("version") or "")
            deps.append(
                Dependency(
                    name=name,
                    version_spec=version_spec,
                    ecosystem="pypi",
                    source_file=path,
                )
            )

    # Poetry 1.2+ groups
    groups = poetry.get("group") or {}
    if isinstance(groups, dict):
        for group in groups.values():
            if not isinstance(group, dict):
                continue
            gdeps = group.get("dependencies") or {}
            if not isinstance(gdeps, dict):
                continue
            for name, spec in gdeps.items():
                key = name.lower()
                if key in seen:
                    continue
                seen.add(key)
                version_spec = spec if isinstance(spec, str) else None
                deps.append(
                    Dependency(
                        name=name,
                        version_spec=version_spec if isinstance(version_spec, str) else None,
                        ecosystem="pypi",
                        source_file=path,
                    )
                )

    return deps


def _parse_pipfile(path: str, content: str) -> list[Dependency]:
    """Parse Pipenv Pipfile [packages] and [dev-packages]."""
    try:
        data = tomllib.loads(content)
    except Exception:  # noqa: BLE001
        return []

    deps: list[Dependency] = []
    for section in ("packages", "dev-packages"):
        block = data.get(section) or {}
        if not isinstance(block, dict):
            continue
        for name, spec in block.items():
            version_spec = spec if isinstance(spec, str) else None
            deps.append(
                Dependency(
                    name=name,
                    version_spec=version_spec,
                    ecosystem="pypi",
                    source_file=path,
                )
            )
    return deps


def _parse_setup_py(path: str, content: str) -> list[Dependency]:
    """
    Best-effort extraction of install_requires from setup.py.

    Only handles simple list literals; dynamic setup() calls are skipped.
    """
    deps: list[Dependency] = []
    # install_requires=["a", "b>=1"]
    match = re.search(
        r"install_requires\s*=\s*\[(.*?)\]",
        content,
        re.DOTALL | re.IGNORECASE,
    )
    if not match:
        return deps
    body = match.group(1)
    for item in re.findall(r"['\"]([^'\"]+)['\"]", body):
        parsed = _parse_requirement_line(item)
        if parsed:
            name, version_spec = parsed
            deps.append(
                Dependency(
                    name=name,
                    version_spec=version_spec,
                    ecosystem="pypi",
                    source_file=path,
                )
            )
    return deps


# ---------------------------------------------------------------------------
# Rust — Cargo.toml
# ---------------------------------------------------------------------------

def _parse_cargo_toml(path: str, content: str) -> list[Dependency]:
    """Parse [dependencies], [dev-dependencies], [build-dependencies]."""
    try:
        data = tomllib.loads(content)
    except Exception:  # noqa: BLE001
        return []

    deps: list[Dependency] = []
    seen: set[str] = set()
    for section in ("dependencies", "dev-dependencies", "build-dependencies"):
        block = data.get(section) or {}
        if not isinstance(block, dict):
            continue
        for name, spec in block.items():
            key = name.lower()
            if key in seen:
                continue
            seen.add(key)
            version_spec = None
            if isinstance(spec, str):
                version_spec = spec
            elif isinstance(spec, dict):
                # Skip path/git only crates (not on crates.io)
                if spec.get("path") or spec.get("git"):
                    if not spec.get("version"):
                        continue
                version_spec = str(spec.get("version") or "") or None
            deps.append(
                Dependency(
                    name=name,
                    version_spec=version_spec,
                    ecosystem="cargo",
                    source_file=path,
                )
            )
    return deps


# ---------------------------------------------------------------------------
# Go — go.mod
# ---------------------------------------------------------------------------

def _parse_go_mod(path: str, content: str) -> list[Dependency]:
    """
    Parse require directives from go.mod.

    Example lines:
      require github.com/foo/bar v1.2.3
      require (
          github.com/a/b v0.1.0
          github.com/c/d v2.0.0 // indirect
      )
    """
    deps: list[Dependency] = []
    in_block = False
    for raw in content.splitlines():
        line = raw.split("//", 1)[0].strip()
        if not line:
            continue
        if line.startswith("require ("):
            in_block = True
            continue
        if in_block:
            if line == ")":
                in_block = False
                continue
            parts = line.split()
            if len(parts) >= 1:
                name = parts[0]
                version = parts[1] if len(parts) > 1 else None
                deps.append(
                    Dependency(
                        name=name,
                        version_spec=version,
                        ecosystem="go",
                        source_file=path,
                    )
                )
            continue
        if line.startswith("require "):
            rest = line[len("require ") :].strip()
            if rest.startswith("("):
                in_block = True
                continue
            parts = rest.split()
            if parts:
                deps.append(
                    Dependency(
                        name=parts[0],
                        version_spec=parts[1] if len(parts) > 1 else None,
                        ecosystem="go",
                        source_file=path,
                    )
                )
    return deps


# ---------------------------------------------------------------------------
# Ruby — Gemfile
# ---------------------------------------------------------------------------

def _parse_gemfile(path: str, content: str) -> list[Dependency]:
    """Best-effort: gem 'name', gem \"name\", version."""
    deps: list[Dependency] = []
    pattern = re.compile(
        r"""gem\s+['\"]([^'\"]+)['\"](?:\s*,\s*['\"]([^'\"]+)['\"])?""",
        re.IGNORECASE,
    )
    for match in pattern.finditer(content):
        name = match.group(1)
        version = match.group(2)
        deps.append(
            Dependency(
                name=name,
                version_spec=version,
                ecosystem="rubygems",
                source_file=path,
            )
        )
    return deps


# ---------------------------------------------------------------------------
# PHP — composer.json
# ---------------------------------------------------------------------------

def _parse_composer_json(path: str, content: str) -> list[Dependency]:
    """Parse require and require-dev from composer.json."""
    try:
        data = json.loads(content)
    except json.JSONDecodeError:
        return []

    deps: list[Dependency] = []
    for section in ("require", "require-dev"):
        block = data.get(section) or {}
        if not isinstance(block, dict):
            continue
        for name, version in block.items():
            # Skip php runtime and extensions
            if name == "php" or name.startswith("ext-"):
                continue
            deps.append(
                Dependency(
                    name=name,
                    version_spec=str(version) if version is not None else None,
                    ecosystem="composer",
                    source_file=path,
                )
            )
    return deps


# ---------------------------------------------------------------------------
# Java — pom.xml / Gradle (best-effort)
# ---------------------------------------------------------------------------

def _parse_pom_xml(path: str, content: str) -> list[Dependency]:
    """Extract groupId:artifactId pairs from a Maven pom.xml (simple regex)."""
    deps: list[Dependency] = []
    # Match dependency blocks with groupId + artifactId
    pattern = re.compile(
        r"<dependency>\s*"
        r"<groupId>([^<]+)</groupId>\s*"
        r"<artifactId>([^<]+)</artifactId>"
        r"(?:\s*<version>([^<]+)</version>)?",
        re.DOTALL | re.IGNORECASE,
    )
    for match in pattern.finditer(content):
        group_id = match.group(1).strip()
        artifact_id = match.group(2).strip()
        version = match.group(3).strip() if match.group(3) else None
        # Skip property placeholders only versions without names
        if "${" in group_id or "${" in artifact_id:
            continue
        name = f"{group_id}:{artifact_id}"
        deps.append(
            Dependency(
                name=name,
                version_spec=version,
                ecosystem="maven",
                source_file=path,
            )
        )
    return deps


def _parse_gradle(path: str, content: str) -> list[Dependency]:
    """
    Best-effort Gradle dependency extraction.

    Matches lines like:
      implementation 'com.google.guava:guava:31.0'
      implementation("org.slf4j:slf4j-api:2.0.0")
    """
    deps: list[Dependency] = []
    pattern = re.compile(
        r"""(?:implementation|api|compileOnly|runtimeOnly|testImplementation|compile|testCompile)"""
        r"""\s*[\(]?\s*['\"]([^:'\"]+):([^:'\"]+)(?::([^'\"]+))?['\"]""",
        re.IGNORECASE,
    )
    for match in pattern.finditer(content):
        group_id, artifact_id, version = match.group(1), match.group(2), match.group(3)
        name = f"{group_id}:{artifact_id}"
        deps.append(
            Dependency(
                name=name,
                version_spec=version,
                ecosystem="gradle",
                source_file=path,
            )
        )
    return deps


# Map ecosystem -> human label (for UI)
ECOSYSTEM_LABELS: dict[str, str] = {
    "npm": "npm (Node.js)",
    "pypi": "PyPI (Python)",
    "cargo": "crates.io (Rust)",
    "go": "Go modules",
    "rubygems": "RubyGems",
    "composer": "Packagist (PHP)",
    "maven": "Maven",
    "gradle": "Gradle",
}

# Type alias for custom parsers (extension point)
ParserFn = Callable[[str, str], list[Dependency]]
