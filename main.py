"""
NiceGUI web interface for the GitHub License Scanner.

Premium UI/UX: bilingual ES/EN, light/dark, responsive split layout,
progressive scan feedback, empty states, and polished results.

Code comments: English.

Run:
  python main.py
"""

from __future__ import annotations

import json
from typing import Any, Callable

from nicegui import app, ui

from history_store import append_scan, load_history
from i18n import DEFAULT_LANG, normalize_lang, t
from license_analyzer import analyze_repository, risk_color
from models import PackageLicense, ScanResult

# Example repos shown as one-click chips (public, fast to scan)
EXAMPLE_REPOS = [
    ("psf/requests", "https://github.com/psf/requests"),
    ("encode/httpx", "https://github.com/encode/httpx"),
    ("tiangolo/fastapi", "https://github.com/tiangolo/fastapi"),
]

# ---------------------------------------------------------------------------
# Design system
# ---------------------------------------------------------------------------

CUSTOM_CSS = """
/* Warm paper + ink palette (less "AI teal/purple") */
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Sans:ital,wght@0,400;0,500;0,600;0,700;1,400&family=IBM+Plex+Mono:wght@400;500&display=swap');

:root {
  --font: 'IBM Plex Sans', 'Segoe UI', system-ui, sans-serif;
  --mono: 'IBM Plex Mono', ui-monospace, Menlo, Consolas, monospace;
  --r: 14px;
  --r-sm: 10px;
  --r-xs: 8px;
  /* Ink navy + warm paper */
  --accent: #2c3e50;
  --accent-hi: #3d5166;
  --accent-2: #8b5e3c;
  --ok: #3f6f4e;
  --warn: #a16207;
  --bad: #9b2c2c;
  --bg: #f3efe6;
  --bg-2: #ebe4d7;
  --surface: #fbf8f2;
  --surface-2: #f1ebe0;
  --text: #1c1917;
  --muted: #6f675e;
  --border: rgba(28, 25, 23, 0.10);
  --shadow: 0 1px 2px rgba(28, 25, 23, 0.04), 0 8px 24px rgba(28, 25, 23, 0.05);
  --shadow-lg: 0 2px 6px rgba(28, 25, 23, 0.04), 0 16px 36px rgba(28, 25, 23, 0.08);
  --ring: 0 0 0 3px rgba(44, 62, 80, 0.18);
  --topbar-h: 58px;
}

body.body--dark {
  --accent: #c4a574;
  --accent-hi: #d4b896;
  --accent-2: #a67c52;
  --ok: #7d9b78;
  --warn: #d4a017;
  --bad: #c97b7b;
  --bg: #141210;
  --bg-2: #1a1714;
  --surface: #1e1b18;
  --surface-2: #26221e;
  --text: #efe8dc;
  --muted: #a39a8c;
  --border: rgba(239, 232, 220, 0.10);
  --shadow: 0 1px 2px rgba(0, 0, 0, 0.35), 0 12px 28px rgba(0, 0, 0, 0.28);
  --shadow-lg: 0 4px 12px rgba(0, 0, 0, 0.28), 0 20px 40px rgba(0, 0, 0, 0.35);
  --ring: 0 0 0 3px rgba(196, 165, 116, 0.22);
}

html, body, .q-page, .nicegui-content {
  font-family: var(--font) !important;
  background: var(--bg) !important;
  color: var(--text) !important;
}

/* Use full viewport width (NiceGUI defaults can feel centered/narrow) */
.q-page,
.nicegui-content,
.q-page-container {
  max-width: none !important;
  width: 100% !important;
}

.nicegui-content {
  padding: 0 !important;
}

.gls-app {
  min-height: 100vh;
  /* Flat warm wash — no neon dual-blob gradients */
  background:
    linear-gradient(180deg, var(--bg) 0%, var(--bg-2) 100%);
  color: var(--text);
}

/* ---- Top bar ---- */
.gls-topbar {
  position: sticky;
  top: 0;
  z-index: 100;
  height: var(--topbar-h);
  display: flex;
  align-items: center;
  background: color-mix(in srgb, var(--surface) 92%, transparent);
  border-bottom: 1px solid var(--border);
}

.gls-topbar-inner {
  width: 100%;
  max-width: none;
  margin: 0;
  padding: 0 1.25rem;
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
}

@media (min-width: 900px) {
  .gls-topbar-inner { padding: 0 1.75rem; }
}

.gls-brand {
  display: flex;
  align-items: center;
  gap: 0.7rem;
  min-width: 0;
}

.gls-mark {
  width: 36px;
  height: 36px;
  border-radius: 8px;
  display: grid;
  place-items: center;
  font-size: 0.95rem;
  background: var(--accent);
  color: var(--surface);
  border: 1px solid color-mix(in srgb, var(--accent) 80%, #000);
  box-shadow: none;
  flex-shrink: 0;
}

body.body--dark .gls-mark {
  color: #1a1714;
  border-color: color-mix(in srgb, var(--accent) 70%, #000);
}

.gls-brand h1 {
  margin: 0;
  font-size: 0.98rem;
  font-weight: 750;
  letter-spacing: -0.03em;
  line-height: 1.15;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.gls-brand span {
  display: block;
  font-size: 0.7rem;
  color: var(--muted);
  font-weight: 500;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}

.gls-tools {
  display: flex;
  align-items: center;
  gap: 0.4rem;
}

.gls-seg {
  display: inline-flex;
  padding: 3px;
  border-radius: 999px;
  background: var(--surface-2);
  border: 1px solid var(--border);
  gap: 2px;
}

.gls-seg button {
  border: 0 !important;
  min-height: 30px !important;
  border-radius: 999px !important;
  padding: 0 0.7rem !important;
  font-size: 0.75rem !important;
  font-weight: 700 !important;
  letter-spacing: 0.02em;
  color: var(--muted) !important;
  background: transparent !important;
}

.gls-seg button.is-on {
  background: var(--surface) !important;
  color: var(--text) !important;
  box-shadow: 0 1px 3px rgba(0,0,0,.08);
}

.gls-icon-btn {
  width: 36px !important;
  height: 36px !important;
  border-radius: 10px !important;
  border: 1px solid var(--border) !important;
  background: var(--surface) !important;
  color: var(--text) !important;
}

/* ---- Layout (full viewport width) ---- */
.gls-wrap {
  width: 100%;
  max-width: none;
  margin: 0;
  padding: 1rem 1.25rem 2.5rem;
  box-sizing: border-box;
}

@media (min-width: 900px) {
  .gls-wrap { padding: 1.25rem 1.75rem 3rem; }
}

@media (min-width: 1400px) {
  .gls-wrap { padding: 1.35rem 2.25rem 3rem; }
}

.gls-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 1rem;
  align-items: start;
  width: 100%;
}

/* Desktop: sidebar + results use the full screen */
@media (min-width: 980px) {
  .gls-grid {
    grid-template-columns: minmax(300px, 28vw) minmax(0, 1fr);
    gap: 1.35rem;
  }
  .gls-sidebar {
    position: sticky;
    top: calc(var(--topbar-h) + 1rem);
    max-width: none;
  }
  .gls-main {
    min-width: 0;
    width: 100%;
  }
}

/* Ultra-wide: keep sidebar readable, give results the rest */
@media (min-width: 1600px) {
  .gls-grid {
    grid-template-columns: minmax(360px, 420px) minmax(0, 1fr);
    gap: 1.5rem;
  }
}

/* ---- Surfaces ---- */
.gls-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--r);
  box-shadow: var(--shadow);
  padding: 1.05rem 1.1rem;
}

.gls-card.soft {
  background: var(--surface-2);
  box-shadow: none;
}

.gls-kicker {
  font-size: 0.68rem;
  font-weight: 750;
  letter-spacing: 0.08em;
  text-transform: uppercase;
  color: var(--accent);
  margin: 0 0 0.35rem;
}

.gls-title {
  margin: 0;
  font-size: 1.2rem;
  font-weight: 780;
  letter-spacing: -0.03em;
  line-height: 1.2;
}

.gls-lead {
  margin: 0.4rem 0 0;
  color: var(--muted);
  font-size: 0.9rem;
  line-height: 1.5;
}

/* ---- Scan form ---- */
.gls-field .q-field__control {
  border-radius: 12px !important;
  background: var(--surface-2) !important;
}

.gls-examples {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
  margin-top: 0.65rem;
}

.gls-chip {
  border: 1px solid var(--border) !important;
  background: var(--surface-2) !important;
  color: var(--text) !important;
  border-radius: 999px !important;
  min-height: 30px !important;
  font-size: 0.75rem !important;
  font-weight: 600 !important;
  padding: 0 0.7rem !important;
}

.gls-chip:hover {
  border-color: color-mix(in srgb, var(--accent) 45%, var(--border)) !important;
  color: var(--accent) !important;
}

.gls-cta {
  width: 100% !important;
  min-height: 44px !important;
  border-radius: 8px !important;
  font-weight: 650 !important;
  font-size: 0.92rem !important;
  letter-spacing: 0;
  background: var(--accent) !important;
  color: var(--surface) !important;
  box-shadow: none !important;
  border: 1px solid color-mix(in srgb, var(--accent) 85%, #000) !important;
}

body.body--dark .gls-cta {
  color: #1a1714 !important;
}

.gls-cta:hover {
  filter: brightness(1.06);
}

/* Progress steps */
.gls-steps {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 0.35rem;
  margin-top: 0.9rem;
}

.gls-step {
  text-align: center;
  padding: 0.45rem 0.2rem;
  border-radius: 10px;
  border: 1px solid var(--border);
  background: var(--surface-2);
  font-size: 0.68rem;
  font-weight: 700;
  color: var(--muted);
  transition: all .2s ease;
}

.gls-step.on {
  color: var(--text);
  border-color: color-mix(in srgb, var(--accent) 45%, var(--border));
  background: color-mix(in srgb, var(--accent) 8%, var(--surface));
}

.gls-step.done {
  color: var(--ok);
  border-color: color-mix(in srgb, var(--ok) 35%, var(--border));
}

/* How it works */
.gls-how {
  margin-top: 0.9rem;
  display: grid;
  gap: 0.4rem;
}

.gls-how-item {
  display: flex;
  gap: 0.55rem;
  align-items: flex-start;
  font-size: 0.82rem;
  color: var(--muted);
  line-height: 1.4;
}

.gls-how-n {
  width: 20px;
  height: 20px;
  border-radius: 6px;
  flex-shrink: 0;
  display: grid;
  place-items: center;
  font-size: 0.68rem;
  font-weight: 800;
  background: color-mix(in srgb, var(--accent) 14%, var(--surface-2));
  color: var(--accent);
}

/* Tabs */
.gls-tabs .q-tabs__content {
  gap: 0.25rem;
}

.gls-tabs .q-tab {
  min-height: 40px;
  border-radius: 10px;
  text-transform: none;
  font-weight: 700;
  font-size: 0.85rem;
  padding: 0 0.85rem;
}

.gls-tabs .q-tab--active {
  background: color-mix(in srgb, var(--accent) 8%, transparent);
}

/* Quasar primary closer to ink / brass instead of default teal */
.q-primary, .text-primary {
  color: var(--accent) !important;
}

/* Results panel */
.gls-results-head {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.75rem;
  margin-bottom: 0.75rem;
  flex-wrap: wrap;
}

.gls-empty {
  border: 1px solid var(--border);
  border-radius: var(--r);
  background: var(--surface);
  padding: 2.2rem 1.4rem;
  text-align: center;
  box-shadow: var(--shadow);
}

.gls-empty-icon {
  width: 56px;
  height: 56px;
  margin: 0 auto 0.9rem;
  border-radius: 10px;
  display: grid;
  place-items: center;
  font-size: 1.45rem;
  background: var(--surface-2);
  border: 1px solid var(--border);
}

.gls-empty h3 {
  margin: 0;
  font-size: 1.15rem;
  font-weight: 750;
  letter-spacing: -0.02em;
}

.gls-empty p {
  margin: 0.45rem auto 0;
  max-width: 42ch;
  color: var(--muted);
  font-size: 0.9rem;
  line-height: 1.5;
}

/* Verdict */
.verdict {
  border-radius: 14px;
  padding: 1rem 1.05rem;
  border: 1px solid var(--border);
  display: flex;
  gap: 0.85rem;
  align-items: flex-start;
}

.verdict.ok {
  background: color-mix(in srgb, var(--ok) 10%, var(--surface));
  border-color: color-mix(in srgb, var(--ok) 35%, var(--border));
}
.verdict.warn {
  background: color-mix(in srgb, var(--warn) 10%, var(--surface));
  border-color: color-mix(in srgb, var(--warn) 35%, var(--border));
}
.verdict.bad {
  background: color-mix(in srgb, var(--bad) 10%, var(--surface));
  border-color: color-mix(in srgb, var(--bad) 35%, var(--border));
}

.verdict-icon {
  width: 42px;
  height: 42px;
  border-radius: 12px;
  display: grid;
  place-items: center;
  flex-shrink: 0;
  font-size: 1.25rem;
  background: var(--surface);
  border: 1px solid var(--border);
}

/* Stats */
.gls-stats {
  display: grid;
  grid-template-columns: 1fr 1fr;
  gap: 0.6rem;
  margin-top: 0.85rem;
  width: 100%;
}

@media (min-width: 700px) {
  .gls-stats { grid-template-columns: repeat(4, 1fr); }
}

@media (min-width: 1600px) {
  .gls-stats { gap: 0.85rem; }
}

.gls-stat {
  background: var(--surface-2);
  border: 1px solid var(--border);
  border-radius: 12px;
  padding: 0.75rem 0.8rem;
  transition: transform .15s ease, box-shadow .15s ease;
}

.gls-stat:hover {
  border-color: color-mix(in srgb, var(--accent) 25%, var(--border));
}

.gls-stat .lbl {
  font-size: 0.68rem;
  font-weight: 700;
  letter-spacing: 0.05em;
  text-transform: uppercase;
  color: var(--muted);
}

.gls-stat .val {
  margin-top: 0.25rem;
  font-size: 1rem;
  font-weight: 750;
  letter-spacing: -0.02em;
  word-break: break-word;
}

/* Pills */
.stat-pill {
  display: inline-flex;
  align-items: center;
  padding: 0.28rem 0.7rem;
  border-radius: 999px;
  font-size: 0.76rem;
  font-weight: 700;
  margin: 0 0.3rem 0.3rem 0;
  border: 1px solid transparent;
}
.pill-green { background: color-mix(in srgb, var(--ok) 14%, var(--surface)); color: var(--ok); border-color: color-mix(in srgb, var(--ok) 25%, transparent); }
.pill-red { background: color-mix(in srgb, var(--bad) 14%, var(--surface)); color: var(--bad); border-color: color-mix(in srgb, var(--bad) 25%, transparent); }
.pill-orange { background: color-mix(in srgb, var(--warn) 14%, var(--surface)); color: var(--warn); border-color: color-mix(in srgb, var(--warn) 25%, transparent); }
.pill-grey { background: var(--surface-2); color: var(--muted); border-color: var(--border); }

.gls-legend {
  font-size: 0.75rem;
  color: var(--muted);
  margin-top: 0.35rem;
}

/* Deploy cards */
.deploy-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 0.7rem;
  margin-top: 0.55rem;
}
@media (min-width: 640px) { .deploy-grid { grid-template-columns: 1fr 1fr; } }
@media (min-width: 1100px) { .deploy-grid { grid-template-columns: 1fr 1fr 1fr; } }
@media (min-width: 1600px) { .deploy-grid { grid-template-columns: repeat(4, 1fr); } }
@media (min-width: 2000px) { .deploy-grid { grid-template-columns: repeat(5, 1fr); } }

.deploy-card {
  border: 1px solid var(--border);
  border-radius: 14px;
  padding: 0.9rem;
  background: var(--surface-2);
  transition: transform .15s ease, box-shadow .15s ease, border-color .15s ease;
  height: 100%;
}
.deploy-card:hover {
  border-color: color-mix(in srgb, var(--accent) 35%, var(--border));
}

.risk-green { border-left: 4px solid var(--ok); background: color-mix(in srgb, var(--ok) 7%, var(--surface)); }
.risk-red { border-left: 4px solid var(--bad); background: color-mix(in srgb, var(--bad) 7%, var(--surface)); }
.risk-orange { border-left: 4px solid var(--warn); background: color-mix(in srgb, var(--warn) 8%, var(--surface)); }
.risk-grey { border-left: 4px solid #94a3b8; background: var(--surface-2); }

.pkg-card {
  border-radius: 10px;
  padding: 0.65rem 0.8rem;
  margin-bottom: 0.4rem;
  border: 1px solid var(--border);
}

.mono {
  font-family: var(--mono) !important;
  font-size: 0.8rem !important;
  white-space: pre-wrap;
}

.gls-section {
  margin-top: 1.25rem;
}

.gls-section h3 {
  margin: 0 0 0.25rem;
  font-size: 1rem;
  font-weight: 750;
  letter-spacing: -0.02em;
}

.gls-muted { color: var(--muted); font-size: 0.84rem; line-height: 1.45; }

.gls-disclaimer {
  display: flex;
  gap: 0.6rem;
  align-items: flex-start;
  padding: 0.75rem 0.85rem;
  border-radius: 12px;
  background: color-mix(in srgb, var(--warn) 10%, var(--surface));
  border: 1px solid color-mix(in srgb, var(--warn) 28%, var(--border));
  font-size: 0.8rem;
  line-height: 1.45;
  color: var(--text);
}

.gls-table-wrap {
  width: 100%;
  overflow-x: auto;
  border-radius: 12px;
  border: 1px solid var(--border);
}
.gls-table-wrap .q-table { min-width: 560px; }

.gls-repo-link {
  font-family: var(--mono);
  font-size: 0.78rem;
}

.gls-recent {
  display: flex;
  flex-direction: column;
  gap: 0.4rem;
  margin-top: 0.55rem;
}

.gls-recent-item {
  display: flex;
  align-items: center;
  justify-content: space-between;
  gap: 0.5rem;
  padding: 0.55rem 0.65rem;
  border-radius: 10px;
  border: 1px solid var(--border);
  background: var(--surface);
  cursor: pointer;
  transition: border-color .15s ease, background .15s ease;
}
.gls-recent-item:hover {
  border-color: color-mix(in srgb, var(--accent) 40%, var(--border));
  background: color-mix(in srgb, var(--accent) 6%, var(--surface));
}

.gls-footer {
  margin-top: 1.75rem;
  text-align: center;
  color: var(--muted);
  font-size: 0.75rem;
}

/* Linear progress under topbar when scanning */
.gls-scan-bar {
  height: 2px;
  background: transparent;
  overflow: hidden;
}
.gls-scan-bar .bar {
  height: 100%;
  width: 35%;
  background: var(--accent);
  animation: gls-slide 1.1s ease-in-out infinite;
}
@keyframes gls-slide {
  0% { transform: translateX(-120%); }
  100% { transform: translateX(320%); }
}

.fade-in {
  animation: fadeIn .35s ease both;
}
@keyframes fadeIn {
  from { opacity: 0; transform: translateY(6px); }
  to { opacity: 1; transform: none; }
}
"""


# ---------------------------------------------------------------------------
# Storage helpers
# ---------------------------------------------------------------------------

def get_lang() -> str:
    try:
        return normalize_lang(app.storage.user.get("lang", DEFAULT_LANG))
    except Exception:  # noqa: BLE001
        return DEFAULT_LANG


def set_lang(lang: str) -> None:
    app.storage.user["lang"] = normalize_lang(lang)
    ui.navigate.reload()


def get_dark() -> bool:
    try:
        return bool(app.storage.user.get("dark", True))
    except Exception:  # noqa: BLE001
        return True


def set_dark(enabled: bool) -> None:
    app.storage.user["dark"] = bool(enabled)


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

def _risk_pill(risk: str, count: int, lang: str) -> str:
    color = {
        "permissive": "pill-green",
        "strong_copyleft": "pill-red",
        "weak_copyleft": "pill-orange",
        "unknown": "pill-orange",
    }.get(risk, "pill-grey")
    labels = {
        "permissive": t("risk_permissive", lang),
        "strong_copyleft": t("risk_strong", lang),
        "weak_copyleft": t("risk_weak", lang),
        "unknown": t("risk_unknown", lang),
    }
    return f'<span class="stat-pill {color}">{labels.get(risk, risk)}: {count}</span>'


def _worst_risk(pkgs: list[PackageLicense]) -> str:
    order = ["strong_copyleft", "weak_copyleft", "unknown", "permissive"]
    risks = {p.risk for p in pkgs}
    for r in order:
        if r in risks:
            return r
    return "unknown"


def _yn(value: bool, lang: str) -> str:
    return t("yes", lang) if value else t("no", lang)


def _badge_color(risk: str) -> str:
    if risk == "permissive":
        return "positive"
    if risk == "strong_copyleft":
        return "negative"
    return "warning"


# ---------------------------------------------------------------------------
# Result rendering
# ---------------------------------------------------------------------------

def render_empty(container: ui.element, lang: str) -> None:
    """Friendly empty state for the results column."""
    container.clear()
    with container:
        with ui.element("div").classes("gls-empty fade-in"):
            ui.label("⚖️").classes("gls-empty-icon")
            ui.html(
                f"<h3>{t('empty_title', lang)}</h3><p>{t('empty_body', lang)}</p>",
                sanitize=False,
            )


def render_result(container: ui.element, result: ScanResult, lang: str | None = None) -> None:
    """Draw a full scan result with polished hierarchy."""
    lang = normalize_lang(lang or get_lang())
    container.clear()
    with container:
        if result.errors and not result.owner:
            with ui.element("div").classes("gls-empty fade-in"):
                ui.icon("error_outline", size="lg").classes("text-negative")
                ui.label(t("error_prefix", lang, error=result.errors[0])).classes(
                    "text-negative q-mt-sm"
                )
            return

        with ui.element("div").classes("gls-card fade-in"):
            # Header
            with ui.row().classes("w-full items-start justify-between flex-wrap gap-2"):
                with ui.column().classes("gap-0"):
                    ui.label(f"{result.owner}/{result.repo}").classes(
                        "text-h5 text-weight-bolder"
                    ).style("letter-spacing:-0.03em;margin:0")
                    ui.link(
                        t("open_repo", lang),
                        result.url,
                        new_tab=True,
                    ).classes("gls-repo-link")
                ui.badge(result.scanned_at).props("outline color=grey")

            # Verdict
            if result.forces_open_source:
                v_cls, title, sub, emoji = (
                    "bad",
                    t("verdict_bad_title", lang),
                    t("verdict_bad_sub", lang),
                    "🚫",
                )
            elif result.has_weak_copyleft or result.has_unknown_licenses:
                v_cls, title, sub, emoji = (
                    "warn",
                    t("verdict_warn_title", lang),
                    t("verdict_warn_sub", lang),
                    "⚠️",
                )
            else:
                v_cls, title, sub, emoji = (
                    "ok",
                    t("verdict_ok_title", lang),
                    t("verdict_ok_sub", lang),
                    "✅",
                )

            with ui.element("div").classes(f"verdict {v_cls} q-mt-md"):
                ui.label(emoji).classes("verdict-icon")
                with ui.column().classes("gap-1"):
                    ui.label(title).classes("text-weight-bold").style("font-size:1.05rem")
                    ui.label(sub).classes("text-body2")
                    ui.label(result.verdict_summary).classes("text-caption opacity-90 q-mt-xs")

            # Stats
            counts = result.risk_counts()
            with ui.element("div").classes("gls-stats"):
                for label, value in (
                    (t("meta_repo_license", lang), result.repo_license or t("unknown", lang)),
                    (t("meta_language", lang), result.primary_language or "n/a"),
                    (t("meta_packages", lang), str(len(result.packages))),
                    (
                        t("meta_forces_open", lang),
                        t("yes", lang).upper() if result.forces_open_source else t("no", lang).upper(),
                    ),
                ):
                    with ui.element("div").classes("gls-stat"):
                        ui.label(label).classes("lbl")
                        ui.label(value).classes("val")

            with ui.element("div").classes("q-mt-md"):
                ui.html(
                    "".join(
                        _risk_pill(k, counts[k], lang)
                        for k in (
                            "permissive",
                            "weak_copyleft",
                            "strong_copyleft",
                            "unknown",
                        )
                    ),
                    sanitize=False,
                )
                ui.label(t("risk_legend", lang)).classes("gls-legend")

            if result.errors:
                with ui.expansion(t("notes_warnings", lang), icon="info").classes(
                    "w-full q-mt-sm"
                ):
                    for err in result.errors:
                        ui.label(f"• {err}").classes("text-caption")

            # Deploy
            with ui.element("div").classes("gls-section"):
                ui.html(f"<h3>{t('deploy_title', lang)}</h3>", sanitize=False)
                ui.label(t("deploy_help", lang)).classes("gls-muted")
                if result.deploy_advice:
                    with ui.element("div").classes("deploy-grid"):
                        for adv in result.deploy_advice:
                            with ui.element("div").classes("deploy-card"):
                                with ui.row().classes(
                                    "items-center justify-between w-full no-wrap"
                                ):
                                    ui.label(adv.platform).classes("text-weight-bold")
                                    ui.badge(str(adv.score)).props("color=brown")
                                for reason in adv.reasons[:3]:
                                    ui.label(f"• {reason}").classes("text-caption q-mt-xs")
                                ui.link(
                                    t("deploy_docs", lang), adv.docs_url, new_tab=True
                                ).classes("text-caption q-mt-sm")
                else:
                    ui.label(t("deploy_none", lang)).classes("gls-muted q-mt-sm")

            # Copyright
            with ui.element("div").classes("gls-section"):
                ui.html(f"<h3>{t('copyright_title', lang)}</h3>", sanitize=False)
                ui.textarea(value=result.copyright_notice).classes("w-full mono").props(
                    "outlined readonly rows=5 input-class=mono"
                )

                async def copy_notice() -> None:
                    payload = json.dumps(result.copyright_notice)
                    try:
                        await ui.run_javascript(
                            f"navigator.clipboard.writeText({payload})",
                            timeout=3.0,
                        )
                        ui.notify(t("copyright_copied", lang), type="positive")
                    except Exception:  # noqa: BLE001
                        ui.notify(t("copyright_copy_fail", lang), type="warning")

                ui.button(
                    t("copyright_copy", lang),
                    on_click=copy_notice,
                    icon="content_copy",
                ).props("color=primary unelevated rounded").classes("q-mt-sm")

            # Replacements
            if result.replacements:
                with ui.element("div").classes("gls-section"):
                    ui.html(f"<h3>{t('replacements_title', lang)}</h3>", sanitize=False)
                    ui.label(t("replacements_help", lang)).classes("gls-muted")
                    for rep in result.replacements:
                        risk_badge = _badge_color(
                            next(
                                (
                                    p.risk
                                    for p in result.packages
                                    if p.name == rep.package
                                ),
                                "weak_copyleft",
                            )
                        )
                        with ui.element("div").classes(
                            "pkg-card risk-orange q-mt-sm"
                        ):
                            with ui.row().classes("items-center gap-2 flex-wrap"):
                                ui.badge(rep.ecosystem).props("outline")
                                ui.label(rep.package).classes("text-weight-bold")
                                ui.badge(rep.license_id or "unknown").props(
                                    f"color={risk_badge}"
                                )
                            ui.label(rep.note).classes("text-caption text-grey q-mt-xs")
                            for alt in rep.alternatives:
                                ui.label(f"→ {alt}").classes("text-body2")

            # Packages
            with ui.element("div").classes("gls-section"):
                ui.html(f"<h3>{t('packages_by_license', lang)}</h3>", sanitize=False)
                if not result.packages:
                    ui.label(t("packages_none", lang)).classes("gls-muted")
                else:
                    for lic, pkgs in result.grouped.items():
                        worst = _worst_risk(pkgs)
                        color = risk_color(worst)
                        icon = {
                            "green": "check_circle",
                            "red": "dangerous",
                            "orange": "warning",
                        }.get(color, "help")
                        with ui.expansion(
                            t("packages_count", lang, license=lic, count=len(pkgs)),
                            icon=icon,
                        ).classes(f"w-full q-mt-xs risk-{color}"):
                            for pkg in sorted(pkgs, key=lambda p: p.name.lower()):
                                with ui.element("div").classes(
                                    f"pkg-card risk-{risk_color(pkg.risk)}"
                                ):
                                    with ui.row().classes(
                                        "items-center justify-between w-full flex-wrap gap-2"
                                    ):
                                        with ui.column().classes("gap-0"):
                                            ui.label(pkg.name).classes(
                                                "text-weight-medium"
                                            )
                                            ui.label(
                                                f"{pkg.ecosystem} · {pkg.source_file}"
                                                + (
                                                    f" · {pkg.version_spec}"
                                                    if pkg.version_spec
                                                    else ""
                                                )
                                            ).classes("text-caption text-grey")
                                        with ui.row().classes("items-center gap-2"):
                                            ui.badge(pkg.risk).props(
                                                f"color={_badge_color(pkg.risk)}"
                                            )
                                            if pkg.license_url:
                                                ui.link(
                                                    t("registry_link", lang),
                                                    pkg.license_url,
                                                    new_tab=True,
                                                ).classes("text-caption")

            if result.dependency_files:
                with ui.expansion(t("dep_files", lang), icon="folder").classes(
                    "w-full q-mt-md"
                ):
                    for path in result.dependency_files:
                        ui.label(f"• {path}").classes("text-caption mono")


def render_batch_summary(
    container: ui.element,
    results: list[ScanResult],
    lang: str | None = None,
) -> None:
    lang = normalize_lang(lang or get_lang())
    container.clear()
    with container:
        with ui.element("div").classes("gls-card fade-in"):
            ui.label(t("batch_results", lang)).classes("gls-title")
            columns = [
                {"name": "repo", "label": t("col_repo", lang), "field": "repo", "align": "left"},
                {
                    "name": "license",
                    "label": t("col_license", lang),
                    "field": "license",
                    "align": "left",
                },
                {"name": "pkgs", "label": t("col_pkgs", lang), "field": "pkgs", "align": "right"},
                {
                    "name": "closed",
                    "label": t("col_closed", lang),
                    "field": "closed",
                    "align": "center",
                },
                {
                    "name": "force",
                    "label": t("col_force", lang),
                    "field": "force",
                    "align": "center",
                },
            ]
            rows = [
                {
                    "repo": f"{r.owner}/{r.repo}" if r.owner else r.url,
                    "license": r.repo_license or "?",
                    "pkgs": len(r.packages),
                    "closed": _yn(r.can_sell_closed, lang),
                    "force": _yn(r.forces_open_source, lang),
                }
                for r in results
            ]
            with ui.element("div").classes("gls-table-wrap q-mt-sm"):
                ui.table(columns=columns, rows=rows, row_key="repo").classes("w-full")

        if results:
            ui.label(t("batch_last_detail", lang)).classes(
                "gls-kicker q-mt-md"
            ).style("display:block")
            detail = ui.column().classes("w-full")
            render_result(detail, results[-1], lang=lang)


def render_history(container: ui.element, lang: str | None = None) -> None:
    lang = normalize_lang(lang or get_lang())
    container.clear()
    entries = load_history()
    with container:
        if not entries:
            with ui.element("div").classes("gls-empty"):
                ui.icon("history", size="md")
                ui.label(t("history_empty", lang)).classes("q-mt-sm")
            return
        columns = [
            {"name": "when", "label": t("col_when", lang), "field": "when", "align": "left"},
            {"name": "repo", "label": t("col_repo", lang), "field": "repo", "align": "left"},
            {
                "name": "license",
                "label": t("col_license", lang),
                "field": "license",
                "align": "left",
            },
            {"name": "pkgs", "label": t("col_pkgs", lang), "field": "pkgs", "align": "right"},
            {
                "name": "closed",
                "label": t("col_closed", lang),
                "field": "closed",
                "align": "center",
            },
            {
                "name": "force",
                "label": t("col_force", lang),
                "field": "force",
                "align": "center",
            },
        ]
        rows = [
            {
                "when": e.get("scanned_at", ""),
                "repo": f"{e.get('owner', '')}/{e.get('repo', '')}",
                "license": e.get("repo_license") or "?",
                "pkgs": e.get("package_count", 0),
                "closed": _yn(bool(e.get("can_sell_closed")), lang),
                "force": _yn(bool(e.get("forces_open_source")), lang),
            }
            for e in entries
        ]
        with ui.element("div").classes("gls-table-wrap"):
            ui.table(columns=columns, rows=rows, row_key="repo").classes("w-full")
        ui.label(t("history_count", lang, count=len(entries))).classes("gls-muted q-mt-sm")


def _set_steps(step_els: list[ui.element], active: int) -> None:
    """Update visual state of progress steps (0..3 active, -1 = idle)."""
    for i, el in enumerate(step_els):
        el.classes(remove="on done")
        if active < 0:
            continue
        if i < active:
            el.classes(add="done")
        elif i == active:
            el.classes(add="on")


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------

@ui.page("/")
def index_page() -> None:
    """Main app page with split workspace UX."""
    ui.add_head_html(
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">'
        '<meta name="theme-color" content="#2c3e50">'
    )
    ui.add_css(CUSTOM_CSS)

    lang = get_lang()
    dark_pref = get_dark()
    dark = ui.dark_mode(dark_pref)

    with ui.element("div").classes("gls-app"):
        # Top bar
        with ui.element("div").classes("gls-topbar"):
            with ui.element("div").classes("gls-topbar-inner"):
                with ui.element("div").classes("gls-brand"):
                    ui.label("⚖️").classes("gls-mark")
                    with ui.column().classes("gap-0"):
                        ui.html(
                            f"<h1>{t('app_title', lang)}</h1>"
                            f"<span>{t('hero_badge', lang)}</span>",
                            sanitize=False,
                        )
                with ui.element("div").classes("gls-tools"):
                    with ui.element("div").classes("gls-seg"):
                        ui.button("ES", on_click=lambda: set_lang("es")).props(
                            "flat dense no-caps"
                        ).classes("is-on" if lang == "es" else "")
                        ui.button("EN", on_click=lambda: set_lang("en")).props(
                            "flat dense no-caps"
                        ).classes("is-on" if lang == "en" else "")

                    def toggle_theme() -> None:
                        new_value = not bool(dark.value)
                        dark.set_value(new_value)
                        set_dark(new_value)
                        theme_btn.props(
                            f'icon={"light_mode" if new_value else "dark_mode"}'
                        )

                    theme_btn = (
                        ui.button(
                            on_click=toggle_theme,
                            icon="light_mode" if dark_pref else "dark_mode",
                        )
                        .props("flat dense")
                        .classes("gls-icon-btn")
                        .tooltip(
                            t(
                                "theme_toggle_to_light"
                                if dark_pref
                                else "theme_toggle_to_dark",
                                lang,
                            )
                        )
                    )

        scan_bar = ui.element("div").classes("gls-scan-bar")
        with scan_bar:
            bar_inner = ui.element("div").classes("bar")
        scan_bar.set_visibility(False)

        with ui.element("div").classes("gls-wrap"):
            with ui.element("div").classes("gls-grid"):
                # ========== LEFT: workspace ==========
                with ui.element("div").classes("gls-sidebar"):
                    with ui.element("div").classes("gls-card"):
                        ui.label(t("workspace_title", lang)).classes("gls-kicker")
                        ui.label(t("scan_card_title", lang)).classes("gls-title")
                        ui.label(t("scan_card_help", lang)).classes("gls-lead")

                        with ui.tabs().classes("w-full gls-tabs q-mt-md") as tabs:
                            tab_scan = ui.tab(t("tab_scan", lang), icon="search")
                            tab_batch = ui.tab(t("tab_batch", lang), icon="playlist_add")
                            tab_history = ui.tab(t("tab_history", lang), icon="history")

                        with ui.tab_panels(tabs, value=tab_scan).classes("w-full").props(
                            "animated"
                        ):
                            # --- Scan ---
                            with ui.tab_panel(tab_scan):
                                url_input = (
                                    ui.input(
                                        label=t("url_label", lang),
                                        placeholder=t("url_placeholder", lang),
                                    )
                                    .classes("w-full gls-field")
                                    .props(
                                        'outlined clearable dense=false '
                                        'prepend-inner-icon=link'
                                    )
                                )

                                ui.label(t("try_example", lang)).classes(
                                    "gls-muted q-mt-sm"
                                ).style("font-size:0.75rem;font-weight:700")

                                def fill_example(url: str) -> Callable[[], None]:
                                    def _inner() -> None:
                                        url_input.value = url

                                    return _inner

                                with ui.element("div").classes("gls-examples"):
                                    for label, url in EXAMPLE_REPOS:
                                        ui.button(
                                            label,
                                            on_click=fill_example(url),
                                        ).props("flat dense no-caps").classes("gls-chip")

                                # Steps
                                step_keys = (
                                    "step_fetch",
                                    "step_deps",
                                    "step_licenses",
                                    "step_verdict",
                                )
                                step_els: list[ui.element] = []
                                with ui.element("div").classes("gls-steps"):
                                    for key in step_keys:
                                        el = ui.label(t(key, lang)).classes("gls-step")
                                        step_els.append(el)

                                status_label = ui.label("").classes(
                                    "gls-muted q-mt-sm text-center w-full"
                                )

                                async def run_scan(url_override: str | None = None) -> None:
                                    url = (url_override or url_input.value or "").strip()
                                    if not url:
                                        ui.notify(
                                            t("notify_paste_url", lang), type="warning"
                                        )
                                        return
                                    url_input.value = url
                                    scan_btn.disable()
                                    scan_bar.set_visibility(True)
                                    status_label.set_text(t("scanning_status", lang))
                                    _set_steps(step_els, 0)
                                    try:
                                        # Animate steps while awaiting the full pipeline
                                        _set_steps(step_els, 1)
                                        result = await analyze_repository(url)
                                        _set_steps(step_els, 2)
                                        if result.owner:
                                            append_scan(result)
                                        _set_steps(step_els, 3)
                                        render_result(results_box, result, lang=lang)
                                        _set_steps(step_els, 4)  # all done look
                                        for el in step_els:
                                            el.classes(remove="on")
                                            el.classes(add="done")
                                        if result.forces_open_source:
                                            ui.notify(
                                                t("notify_strong_copyleft", lang),
                                                type="negative",
                                            )
                                        elif result.errors and not result.packages:
                                            ui.notify(result.errors[0], type="warning")
                                        else:
                                            ui.notify(
                                                t("notify_done", lang), type="positive"
                                            )
                                        # Refresh recent list
                                        render_recent()
                                    except Exception as exc:  # noqa: BLE001
                                        ui.notify(
                                            t("notify_unexpected", lang, error=exc),
                                            type="negative",
                                        )
                                        results_box.clear()
                                        with results_box:
                                            with ui.element("div").classes("gls-empty"):
                                                ui.label(str(exc)).classes(
                                                    "text-negative"
                                                )
                                        _set_steps(step_els, -1)
                                    finally:
                                        scan_btn.enable()
                                        scan_bar.set_visibility(False)
                                        status_label.set_text("")

                                # Enter key submits
                                url_input.on(
                                    "keydown.enter",
                                    lambda: run_scan(),
                                )

                                scan_btn = (
                                    ui.button(
                                        t("scan_button", lang),
                                        on_click=lambda: run_scan(),
                                        icon="policy",
                                    )
                                    .props("color=primary unelevated no-caps")
                                    .classes("gls-cta q-mt-md")
                                )

                                # How it works
                                with ui.expansion(
                                    t("how_it_works", lang), icon="auto_awesome"
                                ).classes("w-full q-mt-md"):
                                    with ui.element("div").classes("gls-how"):
                                        for i, key in enumerate(
                                            ("how_1", "how_2", "how_3", "how_4"), 1
                                        ):
                                            with ui.element("div").classes(
                                                "gls-how-item"
                                            ):
                                                ui.label(str(i)).classes("gls-how-n")
                                                ui.label(t(key, lang))

                                # Recent scans quick rescan
                                recent_box = ui.column().classes("w-full q-mt-md")

                                def render_recent() -> None:
                                    recent_box.clear()
                                    entries = load_history()[:5]
                                    with recent_box:
                                        if not entries:
                                            return
                                        ui.label(t("recent_scans", lang)).classes(
                                            "gls-kicker"
                                        )
                                        with ui.element("div").classes("gls-recent"):
                                            for e in entries:
                                                repo = f"{e.get('owner', '')}/{e.get('repo', '')}"
                                                url = e.get("url") or (
                                                    f"https://github.com/{repo}"
                                                )

                                                def make_handler(u: str) -> Callable[[], Any]:
                                                    async def _h() -> None:
                                                        await run_scan(u)

                                                    return _h

                                                with ui.element("div").classes(
                                                    "gls-recent-item"
                                                ).on("click", make_handler(url)):
                                                    with ui.column().classes("gap-0"):
                                                        ui.label(repo).classes(
                                                            "text-weight-bold text-caption"
                                                        )
                                                        ui.label(
                                                            e.get("repo_license") or "?"
                                                        ).classes("text-caption text-grey")
                                                    ui.icon("replay", size="xs").classes(
                                                        "text-grey"
                                                    )

                                render_recent()

                            # --- Batch ---
                            with ui.tab_panel(tab_batch):
                                ui.label(t("batch_help", lang)).classes("gls-lead")
                                batch_input = (
                                    ui.textarea(
                                        label=t("batch_urls_label", lang),
                                        placeholder=(
                                            "https://github.com/owner/repo1\n"
                                            "https://github.com/owner/repo2"
                                        ),
                                    )
                                    .classes("w-full gls-field q-mt-sm")
                                    .props("outlined rows=8")
                                )
                                batch_status = ui.label("").classes("gls-muted q-mt-sm")

                                async def run_batch() -> None:
                                    raw = batch_input.value or ""
                                    urls = [
                                        line.strip()
                                        for line in raw.splitlines()
                                        if line.strip()
                                        and not line.strip().startswith("#")
                                    ]
                                    if not urls:
                                        ui.notify(
                                            t("notify_batch_empty", lang), type="warning"
                                        )
                                        return
                                    batch_btn.disable()
                                    scan_bar.set_visibility(True)
                                    results: list[ScanResult] = []
                                    try:
                                        for i, url in enumerate(urls, 1):
                                            batch_status.set_text(
                                                t(
                                                    "batch_status",
                                                    lang,
                                                    i=i,
                                                    total=len(urls),
                                                    url=url,
                                                )
                                            )
                                            result = await analyze_repository(url)
                                            if result.owner:
                                                append_scan(result)
                                            results.append(result)
                                        render_batch_summary(
                                            results_box, results, lang=lang
                                        )
                                        ui.notify(
                                            t(
                                                "notify_batch_done",
                                                lang,
                                                count=len(results),
                                            ),
                                            type="positive",
                                        )
                                    except Exception as exc:  # noqa: BLE001
                                        ui.notify(
                                            t("notify_batch_error", lang, error=exc),
                                            type="negative",
                                        )
                                    finally:
                                        batch_btn.enable()
                                        scan_bar.set_visibility(False)
                                        batch_status.set_text("")

                                batch_btn = (
                                    ui.button(
                                        t("batch_button", lang),
                                        on_click=run_batch,
                                        icon="play_arrow",
                                    )
                                    .props("color=secondary unelevated no-caps")
                                    .classes("gls-cta q-mt-md")
                                )

                            # --- History ---
                            with ui.tab_panel(tab_history):
                                history_box = ui.column().classes("w-full")

                                def refresh_history() -> None:
                                    render_history(history_box, lang=lang)

                                ui.button(
                                    t("history_refresh", lang),
                                    on_click=refresh_history,
                                    icon="refresh",
                                ).props("outline rounded no-caps dense")
                                history_box
                                refresh_history()

                    # Disclaimer under sidebar
                    with ui.element("div").classes("gls-disclaimer q-mt-md"):
                        ui.icon("balance", size="sm")
                        ui.label(t("disclaimer", lang))
                    ui.label(t("token_hint", lang)).classes("gls-muted q-mt-sm").style(
                        "font-size:0.75rem"
                    )

                # ========== RIGHT: results ==========
                with ui.element("div").classes("gls-main"):
                    with ui.element("div").classes("gls-results-head"):
                        with ui.column().classes("gap-0"):
                            ui.label(t("results_live", lang)).classes("gls-kicker")
                            ui.label(t("results", lang)).classes("gls-title")
                    results_box = ui.column().classes("w-full")
                    render_empty(results_box, lang)

            with ui.element("div").classes("gls-footer"):
                ui.label(
                    f"{t('app_title', lang)} · ES/EN · "
                    f"{t('theme_light', lang)}/{t('theme_dark', lang)}"
                )


def main() -> None:
    """Start the NiceGUI application server."""
    ui.run(
        title="GitHub License Scanner",
        reload=False,
        port=8080,
        show=True,
        favicon="⚖️",
        dark=None,
        storage_secret="github-license-scanner-bilingual-ui",
    )


if __name__ in {"__main__", "__mp_main__"}:
    main()
