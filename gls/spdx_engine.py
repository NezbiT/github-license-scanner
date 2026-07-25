"""
SPDX license-expression parser and risk classifier.

Implements a practical subset of SPDX 2.x expressions:
  - LicenseIds and LicenseRefs
  - AND / OR (case-insensitive)
  - WITH exception
  - Parentheses for grouping

Risk composition rules (conservative for closed-source sale heuristics):
  - OR  → best (lowest risk) among alternatives  [choice of license]
  - AND → worst among conjuncts                  [all apply]
  - WITH → risk of the base license              [exception does not lower risk]

This is NOT a full SPDX validation suite and is NOT legal advice.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from enum import Enum
from typing import Iterable


class Risk(str, Enum):
    PERMISSIVE = "permissive"
    WEAK_COPYLEFT = "weak_copyleft"
    STRONG_COPYLEFT = "strong_copyleft"
    UNKNOWN = "unknown"

    @property
    def rank(self) -> int:
        """Higher = more restrictive / concerning for closed-source sale."""
        return {
            Risk.PERMISSIVE: 0,
            Risk.WEAK_COPYLEFT: 1,
            Risk.UNKNOWN: 2,
            Risk.STRONG_COPYLEFT: 3,
        }[self]


# Canonical-ish license id → risk (lowercase keys, hyphenated)
_PERMISSIVE = {
    "mit",
    "apache-2.0",
    "apache-1.0",
    "apache-1.1",
    "bsd-2-clause",
    "bsd-3-clause",
    "bsd-1-clause",
    "bsd-3-clause-clear",
    "0bsd",
    "isc",
    "unlicense",
    "cc0-1.0",
    "zlib",
    "bsl-1.0",
    "python-2.0",
    "psf-2.0",
    "blueoak-1.0.0",
    "artistic-2.0",
    "wtfpl",
    "postgresql",
    "openssl",
    "x11",
    "hpnd",
    "ncsa",
    "ms-pl",  # Microsoft Public is OSI permissive-ish; treat as weak if unsure — keep permissive
    "afl-3.0",
}

_WEAK = {
    "lgpl-2.0",
    "lgpl-2.0-only",
    "lgpl-2.0-or-later",
    "lgpl-2.1",
    "lgpl-2.1-only",
    "lgpl-2.1-or-later",
    "lgpl-3.0",
    "lgpl-3.0-only",
    "lgpl-3.0-or-later",
    "mpl-1.1",
    "mpl-2.0",
    "epl-1.0",
    "epl-2.0",
    "cpl-1.0",
    "cddl-1.0",
    "cddl-1.1",
    "eupl-1.1",
    "eupl-1.2",
    "osl-3.0",  # often treated stronger; keep weak only if already in strong map elsewhere
}

_STRONG = {
    "gpl-1.0",
    "gpl-1.0-only",
    "gpl-1.0-or-later",
    "gpl-2.0",
    "gpl-2.0-only",
    "gpl-2.0-or-later",
    "gpl-3.0",
    "gpl-3.0-only",
    "gpl-3.0-or-later",
    "agpl-1.0",
    "agpl-1.0-only",
    "agpl-1.0-or-later",
    "agpl-3.0",
    "agpl-3.0-only",
    "agpl-3.0-or-later",
    "sspl-1.0",
    "sleepycat",
    "osl-3.0",
    "cecill-2.1",
    "gfdl-1.3",
}

# Aliases → canonical SPDX-ish id
_ALIASES = {
    "apache": "apache-2.0",
    "apache2": "apache-2.0",
    "apache-2": "apache-2.0",
    "apache 2.0": "apache-2.0",
    "bsd": "bsd-3-clause",
    "bsd2": "bsd-2-clause",
    "bsd3": "bsd-3-clause",
    "gpl": "gpl-3.0",
    "gpl2": "gpl-2.0",
    "gpl3": "gpl-3.0",
    "gplv2": "gpl-2.0",
    "gplv3": "gpl-3.0",
    "lgpl": "lgpl-3.0",
    "lgplv2": "lgpl-2.1",
    "lgplv3": "lgpl-3.0",
    "agpl": "agpl-3.0",
    "agplv3": "agpl-3.0",
    "mpl": "mpl-2.0",
    "mpl2": "mpl-2.0",
    "cc0": "cc0-1.0",
    "boost": "bsl-1.0",
    "bsl": "bsl-1.0",
    "psf": "psf-2.0",
    "python": "python-2.0",
    "unlicensed": "unlicensed",  # proprietary marker
    "proprietary": "proprietary",
    "commercial": "proprietary",
}


class TokenKind(str, Enum):
    LPAREN = "("
    RPAREN = ")"
    AND = "AND"
    OR = "OR"
    WITH = "WITH"
    ID = "ID"
    EOF = "EOF"


@dataclass(frozen=True)
class Token:
    kind: TokenKind
    value: str
    pos: int


_ID_RE = re.compile(
    r"""
    (?:
        DocumentRef-[A-Za-z0-9\-.]+:
    )?
    (?:
        LicenseRef-[A-Za-z0-9\-.]+
      | [A-Za-z0-9][A-Za-z0-9.+_-]*
    )
    """,
    re.VERBOSE,
)


def tokenize(expression: str) -> list[Token]:
    """Lex an SPDX expression into tokens."""
    s = expression.strip()
    # Normalize common non-SPDX separators from registries
    s = s.replace("||", " OR ").replace("&&", " AND ")
    # npm sometimes uses "/" as OR
    if " OR " not in s.upper() and " AND " not in s.upper() and "/" in s and "(" not in s:
        # only for simple "MIT/Apache-2.0" style — not paths
        if re.fullmatch(r"[A-Za-z0-9.+_\-]+(?:\s*/\s*[A-Za-z0-9.+_\-]+)+", s.strip()):
            s = re.sub(r"\s*/\s*", " OR ", s)

    tokens: list[Token] = []
    i = 0
    n = len(s)
    while i < n:
        ch = s[i]
        if ch.isspace():
            i += 1
            continue
        if ch == "(":
            tokens.append(Token(TokenKind.LPAREN, "(", i))
            i += 1
            continue
        if ch == ")":
            tokens.append(Token(TokenKind.RPAREN, ")", i))
            i += 1
            continue
        # Word / id
        m = _ID_RE.match(s, i)
        if not m:
            raise ValueError(f"Unexpected character at {i}: {s[i]!r}")
        word = m.group(0)
        upper = word.upper()
        if upper == "AND":
            tokens.append(Token(TokenKind.AND, "AND", i))
        elif upper == "OR":
            tokens.append(Token(TokenKind.OR, "OR", i))
        elif upper == "WITH":
            tokens.append(Token(TokenKind.WITH, "WITH", i))
        else:
            tokens.append(Token(TokenKind.ID, word, i))
        i = m.end()
    tokens.append(Token(TokenKind.EOF, "", n))
    return tokens


@dataclass
class ExprNode:
    """AST node for SPDX expressions."""

    op: str  # 'id' | 'and' | 'or' | 'with'
    value: str | None = None
    children: list[ExprNode] | None = None

    def license_ids(self) -> list[str]:
        if self.op == "id":
            return [self.value or ""]
        if self.op == "with":
            return (self.children or [])[0].license_ids() if self.children else []
        out: list[str] = []
        for c in self.children or []:
            out.extend(c.license_ids())
        return out


class _Parser:
    def __init__(self, tokens: list[Token]) -> None:
        self.tokens = tokens
        self.i = 0

    def _cur(self) -> Token:
        return self.tokens[self.i]

    def _eat(self, kind: TokenKind) -> Token:
        tok = self._cur()
        if tok.kind != kind:
            raise ValueError(f"Expected {kind}, got {tok.kind} ({tok.value!r}) at {tok.pos}")
        self.i += 1
        return tok

    def parse(self) -> ExprNode:
        node = self._parse_or()
        if self._cur().kind != TokenKind.EOF:
            raise ValueError(f"Trailing tokens at {self._cur().pos}")
        return node

    def _parse_or(self) -> ExprNode:
        left = self._parse_and()
        nodes = [left]
        while self._cur().kind == TokenKind.OR:
            self._eat(TokenKind.OR)
            nodes.append(self._parse_and())
        if len(nodes) == 1:
            return nodes[0]
        return ExprNode(op="or", children=nodes)

    def _parse_and(self) -> ExprNode:
        left = self._parse_with()
        nodes = [left]
        while self._cur().kind == TokenKind.AND:
            self._eat(TokenKind.AND)
            nodes.append(self._parse_with())
        if len(nodes) == 1:
            return nodes[0]
        return ExprNode(op="and", children=nodes)

    def _parse_with(self) -> ExprNode:
        base = self._parse_primary()
        if self._cur().kind == TokenKind.WITH:
            self._eat(TokenKind.WITH)
            exc = self._eat(TokenKind.ID)
            return ExprNode(
                op="with",
                value=exc.value,
                children=[base],
            )
        return base

    def _parse_primary(self) -> ExprNode:
        tok = self._cur()
        if tok.kind == TokenKind.LPAREN:
            self._eat(TokenKind.LPAREN)
            node = self._parse_or()
            self._eat(TokenKind.RPAREN)
            return node
        if tok.kind == TokenKind.ID:
            self._eat(TokenKind.ID)
            return ExprNode(op="id", value=tok.value)
        raise ValueError(f"Unexpected token {tok.kind} at {tok.pos}")


def parse_expression(text: str) -> ExprNode:
    """Parse SPDX expression text into an AST."""
    return _Parser(tokenize(text)).parse()


def normalize_license_token(raw: str) -> str:
    """Normalize a single license id token for lookup."""
    t = raw.strip().strip("()")
    # Drop trailing + (or-later shorthand in some registries)
    plus = t.endswith("+")
    if plus:
        t = t[:-1]
    t = t.lower().replace(" ", "-").replace("_", "-")
    t = t.replace("gnu-", "").replace("licence", "license")
    if t in _ALIASES:
        t = _ALIASES[t]
    if plus and not t.endswith("-or-later") and not t.endswith("+"):
        # map gpl-2.0+ → gpl-2.0-or-later when possible
        if re.match(r"^(agpl|gpl|lgpl)-\d+(\.\d+)?$", t):
            t = f"{t}-or-later"
    return t


def classify_id(license_id: str) -> Risk:
    """Classify a single license identifier."""
    t = normalize_license_token(license_id)
    if t in {"unlicensed", "proprietary", "commercial", "none", "noassertion"}:
        return Risk.UNKNOWN
    if t.startswith("licenseref-"):
        return Risk.UNKNOWN
    if t in _PERMISSIVE:
        return Risk.PERMISSIVE
    if t in _WEAK:
        return Risk.WEAK_COPYLEFT
    if t in _STRONG:
        return Risk.STRONG_COPYLEFT

    # Substring heuristics for versioned / odd ids
    if "agpl" in t or "sspl" in t:
        return Risk.STRONG_COPYLEFT
    if re.search(r"(^|-)gpl", t) and "lgpl" not in t:
        return Risk.STRONG_COPYLEFT
    if "lgpl" in t or "mpl" in t or t.startswith("epl") or "eupl" in t or "cddl" in t:
        return Risk.WEAK_COPYLEFT
    if any(p in t for p in ("mit", "apache", "bsd", "isc", "unlicense", "zlib", "boost", "cc0")):
        return Risk.PERMISSIVE
    return Risk.UNKNOWN


def _worst(risks: Iterable[Risk]) -> Risk:
    return max(risks, key=lambda r: r.rank, default=Risk.UNKNOWN)


def _best(risks: Iterable[Risk]) -> Risk:
    return min(risks, key=lambda r: r.rank, default=Risk.UNKNOWN)


def classify_node(node: ExprNode) -> Risk:
    """Classify an AST node."""
    if node.op == "id":
        return classify_id(node.value or "")
    if node.op == "with":
        # Exception does not reduce base risk for our closed-sale heuristic
        kids = node.children or []
        return classify_node(kids[0]) if kids else Risk.UNKNOWN
    if node.op == "or":
        return _best(classify_node(c) for c in (node.children or []))
    if node.op == "and":
        return _worst(classify_node(c) for c in (node.children or []))
    return Risk.UNKNOWN


def classify_expression(text: str | None) -> tuple[str, ExprNode | None, str | None]:
    """
    Classify a license string / SPDX expression.

    Returns:
        (risk_bucket, ast_or_none, error_or_none)
        risk_bucket is one of: permissive | weak_copyleft | strong_copyleft | unknown
    """
    if not text or not str(text).strip():
        return Risk.UNKNOWN.value, None, None

    raw = str(text).strip()
    # Strip wrapping quotes
    if (raw.startswith('"') and raw.endswith('"')) or (raw.startswith("'") and raw.endswith("'")):
        raw = raw[1:-1].strip()

    # Quick proprietary markers
    if raw.upper() in {"UNLICENSED", "PROPRIETARY", "COMMERCIAL", "NONE", "NOASSERTION"}:
        return Risk.UNKNOWN.value, None, None

    # Try full expression parse
    try:
        # Prefer parenthesized / multi-token forms; also simple ids
        node = parse_expression(raw)
        risk = classify_node(node)
        return risk.value, node, None
    except ValueError as exc:
        # Fallback: single-token classify
        risk = classify_id(raw)
        return risk.value, None, str(exc)


def is_network_copyleft_expression(text: str | None) -> bool:
    """True if any license id in the expression is AGPL/SSPL-class."""
    if not text:
        return False
    risk, node, _ = classify_expression(text)
    if node is not None:
        ids = node.license_ids()
    else:
        ids = [text]
    for lid in ids:
        n = normalize_license_token(lid)
        if "agpl" in n or "sspl" in n:
            return True
    # Also if whole string matches
    lower = text.lower()
    return "agpl" in lower or "sspl" in lower


def expression_to_spdx_ids(text: str | None) -> list[str]:
    """Extract license ids from an expression (best effort)."""
    if not text:
        return []
    _, node, _ = classify_expression(text)
    if node is None:
        return [normalize_license_token(text)]
    return [normalize_license_token(x) for x in node.license_ids() if x]
