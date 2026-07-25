"""
NiceGUI web interface for the GitHub License Scanner.

Minimal UI: bilingual ES/EN, light/dark, quiet canvas grid,
progressive scan feedback, empty states, and polished results.

Code comments: English.

Run:
  python main.py
"""

from __future__ import annotations

import json
from typing import Any, Callable

from nicegui import app, ui

from config import (
    HOST,
    MAX_BATCH_URLS,
    PORT,
    RATE_LIMIT_SCANS,
    RATE_LIMIT_WINDOW_SECONDS,
    SHOW_BROWSER,
    STORAGE_SECRET,
)
from history_store import append_scan, clear_history, load_history
from i18n import DEFAULT_LANG, normalize_lang, t
from license_analyzer import analyze_repository, risk_color
from models import PackageLicense, ScanResult
from rate_limit import SlidingWindowRateLimiter
from report import render_markdown_report

# Per-process scan limiter (keyed by session / anonymous)
_scan_limiter = SlidingWindowRateLimiter(
    max_calls=RATE_LIMIT_SCANS,
    window_seconds=RATE_LIMIT_WINDOW_SECONDS,
)


def _client_rate_key() -> str:
    """Best-effort client key for rate limiting (session storage id)."""
    try:
        # NiceGUI user storage is cookie-backed; use a stable per-browser key
        key = app.storage.user.get("_gls_rid")
        if not key:
            import secrets

            key = secrets.token_hex(16)
            app.storage.user["_gls_rid"] = key
        return f"u:{key}"
    except Exception:  # noqa: BLE001
        return "u:anonymous"


def _check_scan_budget(n: int = 1) -> str | None:
    """
    Consume rate-limit budget for n scans.

    Returns an error message if denied, else None.
    """
    key = _client_rate_key()
    for _ in range(max(1, n)):
        if not _scan_limiter.allow(key):
            wait = int(_scan_limiter.retry_after_seconds(key)) + 1
            return t(
                "rate_limited",
                get_lang(),
                wait=wait,
                limit=RATE_LIMIT_SCANS,
                window=RATE_LIMIT_WINDOW_SECONDS,
            )
    return None

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
/* Minimal monochrome UI */
@import url('https://fonts.googleapis.com/css2?family=Inter:wght@400;500;600;700&family=JetBrains+Mono:wght@400;500&display=swap');

:root {
  --font: 'Inter', system-ui, -apple-system, 'Segoe UI', sans-serif;
  --mono: 'JetBrains Mono', ui-monospace, Menlo, Consolas, monospace;
  --r: 10px;
  --r-sm: 8px;
  --r-xs: 6px;
  --accent: #111111;
  --accent-hi: #262626;
  --accent-2: #525252;
  --ok: #171717;
  --warn: #737373;
  --bad: #404040;
  --bg: #fafafa;
  --bg-2: #f5f5f5;
  --surface: #ffffff;
  --surface-2: #f5f5f5;
  --text: #111111;
  --muted: #737373;
  --border: #e5e5e5;
  --shadow: 0 1px 2px rgba(0,0,0,.05), 0 4px 12px rgba(0,0,0,.06);
  --shadow-md: 0 2px 4px rgba(0,0,0,.05), 0 8px 20px rgba(0,0,0,.08);
  --shadow-lg: 0 4px 8px rgba(0,0,0,.04), 0 16px 40px rgba(0,0,0,.10);
  --ring: 0 0 0 2px rgba(17,17,17,.12);
  --topbar-h: 56px;
}

body.body--dark {
  --accent: #fafafa;
  --accent-hi: #e5e5e5;
  --accent-2: #a3a3a3;
  --ok: #e5e5e5;
  --warn: #a3a3a3;
  --bad: #737373;
  --bg: #0a0a0a;
  --bg-2: #111111;
  --surface: #141414;
  --surface-2: #1a1a1a;
  --text: #fafafa;
  --muted: #a3a3a3;
  --border: #262626;
  --shadow: 0 1px 2px rgba(0,0,0,.45), 0 6px 16px rgba(0,0,0,.35);
  --shadow-md: 0 2px 6px rgba(0,0,0,.4), 0 12px 28px rgba(0,0,0,.4);
  --shadow-lg: 0 8px 16px rgba(0,0,0,.4), 0 24px 48px rgba(0,0,0,.5);
  --ring: 0 0 0 2px rgba(250,250,250,.14);
}

html, body, .q-page, .nicegui-content {
  font-family: var(--font) !important;
  background: var(--bg) !important;
  color: var(--text) !important;
}
.q-page, .nicegui-content, .q-page-container {
  max-width: none !important;
  width: 100% !important;
}
.nicegui-content { padding: 0 !important; }

.gls-canvas {
  position: fixed;
  inset: 0;
  width: 100%;
  height: 100%;
  z-index: 0;
  pointer-events: none;
  display: block;
  opacity: 0.45;
}

.gls-app {
  position: relative;
  z-index: 1;
  min-height: 100vh;
  background: transparent;
  color: var(--text);
}

.gls-topbar {
  position: sticky;
  top: 0;
  z-index: 100;
  height: var(--topbar-h);
  display: flex;
  align-items: center;
  background: color-mix(in srgb, var(--surface) 88%, transparent);
  backdrop-filter: blur(10px);
  -webkit-backdrop-filter: blur(10px);
  border-bottom: 1px solid var(--border);
  box-shadow: var(--shadow);
}

.gls-topbar-inner {
  width: 100%;
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
  gap: 0.65rem;
  min-width: 0;
}

.gls-mark {
  width: 32px;
  height: 32px;
  border-radius: 8px;
  display: grid;
  place-items: center;
  font-size: 0.9rem;
  background: var(--surface);
  color: var(--text);
  border: 1px solid var(--border);
  flex-shrink: 0;
}

.gls-brand h1 {
  margin: 0;
  font-size: 0.92rem;
  font-weight: 600;
  letter-spacing: -0.02em;
  line-height: 1.15;
  white-space: nowrap;
  overflow: hidden;
  text-overflow: ellipsis;
}
.gls-brand span {
  display: block;
  font-size: 0.68rem;
  color: var(--muted);
  font-weight: 500;
  letter-spacing: 0.01em;
}

.gls-tools { display: flex; align-items: center; gap: 0.4rem; }

.gls-seg {
  display: inline-flex;
  padding: 2px;
  border-radius: 8px;
  background: var(--surface-2);
  border: 1px solid var(--border);
  gap: 2px;
}
.gls-seg button {
  border: 0 !important;
  min-height: 28px !important;
  border-radius: 6px !important;
  padding: 0 0.65rem !important;
  font-size: 0.72rem !important;
  font-weight: 600 !important;
  color: var(--muted) !important;
  background: transparent !important;
}
.gls-seg button.is-on {
  background: var(--surface) !important;
  color: var(--text) !important;
  box-shadow: var(--shadow);
}

.gls-icon-btn {
  width: 34px !important;
  height: 34px !important;
  border-radius: 8px !important;
  border: 1px solid var(--border) !important;
  background: var(--surface) !important;
  color: var(--text) !important;
  box-shadow: var(--shadow) !important;
}

.gls-wrap {
  width: 100%;
  margin: 0;
  padding: 1rem 1.25rem 2.5rem;
  box-sizing: border-box;
}
@media (min-width: 900px) { .gls-wrap { padding: 1.25rem 1.75rem 3rem; } }
@media (min-width: 1400px) { .gls-wrap { padding: 1.35rem 2.25rem 3rem; } }

.gls-grid {
  display: grid;
  grid-template-columns: 1fr;
  gap: 1rem;
  align-items: start;
  width: 100%;
}
@media (min-width: 980px) {
  .gls-grid {
    grid-template-columns: minmax(300px, 28vw) minmax(0, 1fr);
    gap: 1.25rem;
  }
  .gls-sidebar {
    position: sticky;
    top: calc(var(--topbar-h) + 1rem);
  }
  .gls-main { min-width: 0; width: 100%; }
}
@media (min-width: 1600px) {
  .gls-grid {
    grid-template-columns: minmax(340px, 400px) minmax(0, 1fr);
  }
}

.gls-card {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: var(--r);
  box-shadow: var(--shadow-md);
  padding: 1.05rem 1.1rem;
  transition: box-shadow .15s ease;
}
.gls-card:hover {
  transform: none;
  box-shadow: var(--shadow-lg);
}
.gls-card.soft {
  background: var(--surface-2);
  box-shadow: var(--shadow);
}

.gls-kicker {
  font-size: 0.68rem;
  font-weight: 600;
  letter-spacing: 0.06em;
  text-transform: uppercase;
  color: var(--muted);
  margin: 0 0 0.3rem;
}
.gls-title {
  margin: 0;
  font-size: 1.1rem;
  font-weight: 600;
  letter-spacing: -0.025em;
  line-height: 1.25;
}
.gls-lead {
  margin: 0.4rem 0 0;
  color: var(--muted);
  font-size: 0.88rem;
  line-height: 1.5;
}

.gls-field .q-field__control {
  border-radius: 8px !important;
  background: var(--surface) !important;
}
.gls-field .q-field--focused .q-field__control {
  box-shadow: var(--ring) !important;
}

.gls-examples {
  display: flex;
  flex-wrap: wrap;
  gap: 0.4rem;
  margin-top: 0.6rem;
}
.gls-chip {
  border: 1px solid var(--border) !important;
  background: var(--surface) !important;
  color: var(--text) !important;
  border-radius: 999px !important;
  min-height: 30px !important;
  font-size: 0.74rem !important;
  font-weight: 500 !important;
  padding: 0 0.7rem !important;
  box-shadow: var(--shadow) !important;
}
.gls-chip:hover {
  background: var(--surface-2) !important;
  color: var(--text) !important;
  transform: none !important;
  box-shadow: var(--shadow-md) !important;
}

.gls-cta {
  width: 100% !important;
  min-height: 42px !important;
  border-radius: 8px !important;
  font-weight: 600 !important;
  font-size: 0.9rem !important;
  letter-spacing: -0.01em;
  background: var(--accent) !important;
  color: var(--surface) !important;
  border: 1px solid var(--accent) !important;
  box-shadow: var(--shadow-md) !important;
  animation: none !important;
}
body.body--dark .gls-cta {
  color: var(--bg) !important;
}
.gls-cta:hover {
  transform: none !important;
  box-shadow: var(--shadow-lg) !important;
  filter: brightness(1.08);
}
.gls-cta:active {
  transform: none !important;
  opacity: 0.9;
}

.gls-steps {
  display: grid;
  grid-template-columns: repeat(4, 1fr);
  gap: 0.35rem;
  margin-top: 0.9rem;
}
.gls-step {
  text-align: center;
  padding: 0.45rem 0.2rem;
  border-radius: 8px;
  border: 1px solid var(--border);
  background: var(--surface-2);
  font-size: 0.66rem;
  font-weight: 600;
  color: var(--muted);
  transition: border-color .15s ease, background .15s ease, color .15s ease;
}
.gls-step.on {
  color: var(--text);
  border-color: var(--text);
  background: var(--surface);
  transform: none;
  box-shadow: none;
}
.gls-step.done {
  color: var(--text);
  border-color: var(--border);
  background: var(--surface);
}

.gls-how { margin-top: 0.85rem; display: grid; gap: 0.4rem; }
.gls-how-item {
  display: flex; gap: 0.55rem; align-items: flex-start;
  font-size: 0.82rem; color: var(--muted); line-height: 1.4;
}
.gls-how-n {
  width: 20px; height: 20px; border-radius: 6px; flex-shrink: 0;
  display: grid; place-items: center; font-size: 0.68rem; font-weight: 600;
  background: var(--surface-2); color: var(--text); border: 1px solid var(--border);
}

.gls-tabs .q-tabs__content { gap: 0.25rem; }
.gls-tabs .q-tab {
  min-height: 38px; border-radius: 8px; text-transform: none;
  font-weight: 600; font-size: 0.84rem; padding: 0 0.8rem;
}
.gls-tabs .q-tab--active {
  background: var(--surface-2);
  border: 1px solid var(--border);
  box-shadow: none;
}
.q-primary, .text-primary { color: var(--text) !important; }
.bg-primary { background: var(--accent) !important; }

.gls-results-head {
  display: flex; align-items: center; justify-content: space-between;
  gap: 0.75rem; margin-bottom: 0.75rem; flex-wrap: wrap;
}

.gls-empty {
  border: 1px dashed var(--border);
  border-radius: var(--r);
  background: var(--surface);
  padding: 2.2rem 1.4rem;
  text-align: center;
  box-shadow: var(--shadow);
}
.gls-empty-icon {
  width: 48px; height: 48px; margin: 0 auto 0.85rem; border-radius: 10px;
  display: grid; place-items: center; font-size: 1.25rem;
  background: var(--surface-2); color: var(--text); border: 1px solid var(--border);
  box-shadow: none;
  animation: none;
}
.gls-empty h3 { margin: 0; font-size: 1.05rem; font-weight: 600; letter-spacing: -0.02em; }
.gls-empty p {
  margin: 0.45rem auto 0; max-width: 42ch; color: var(--muted);
  font-size: 0.88rem; line-height: 1.5;
}

.verdict {
  border-radius: 10px; padding: 0.95rem 1rem;
  border: 1px solid var(--border);
  display: flex; gap: 0.8rem; align-items: flex-start;
  box-shadow: var(--shadow);
  background: var(--surface-2);
  animation: none;
}
.verdict.ok, .verdict.warn, .verdict.bad {
  background: var(--surface-2);
  border-color: var(--border);
}
.verdict-icon {
  width: 36px; height: 36px; border-radius: 8px;
  display: grid; place-items: center; flex-shrink: 0; font-size: 1.1rem;
  background: var(--surface); border: 1px solid var(--border);
  box-shadow: none;
}

.gls-stats {
  display: grid; grid-template-columns: 1fr 1fr; gap: 0.55rem;
  margin-top: 0.85rem; width: 100%;
}
@media (min-width: 700px) { .gls-stats { grid-template-columns: repeat(4, 1fr); } }

.gls-stat {
  background: var(--surface);
  border: 1px solid var(--border);
  border-radius: 8px;
  padding: 0.7rem 0.75rem;
  box-shadow: var(--shadow);
  transition: box-shadow .15s ease;
}
.gls-stat:hover {
  transform: none;
  box-shadow: var(--shadow-md);
  border-color: var(--border);
}
.gls-stat .lbl {
  font-size: 0.65rem; font-weight: 600; letter-spacing: 0.04em;
  text-transform: uppercase; color: var(--muted);
}
.gls-stat .val {
  margin-top: 0.2rem; font-size: 0.95rem; font-weight: 600;
  letter-spacing: -0.02em; word-break: break-word;
}

.stat-pill {
  display: inline-flex; align-items: center;
  padding: 0.22rem 0.6rem; border-radius: 999px;
  font-size: 0.74rem; font-weight: 600;
  margin: 0 0.25rem 0.25rem 0;
  border: 1px solid var(--border);
  background: var(--surface);
  color: var(--text);
}
.stat-pill:hover { transform: none; }
.pill-green, .pill-red, .pill-orange, .pill-grey {
  background: var(--surface-2);
  color: var(--text);
  border-color: var(--border);
}

.gls-legend { font-size: 0.74rem; color: var(--muted); margin-top: 0.35rem; }

.deploy-grid {
  display: grid; grid-template-columns: 1fr; gap: 0.6rem; margin-top: 0.5rem;
}
@media (min-width: 640px) { .deploy-grid { grid-template-columns: 1fr 1fr; } }
@media (min-width: 1100px) { .deploy-grid { grid-template-columns: 1fr 1fr 1fr; } }
@media (min-width: 1600px) { .deploy-grid { grid-template-columns: repeat(4, 1fr); } }

.deploy-card {
  border: 1px solid var(--border);
  border-radius: 10px;
  padding: 0.85rem;
  background: var(--surface);
  transition: border-color .15s ease, box-shadow .15s ease;
  height: 100%;
  box-shadow: var(--shadow);
}
.deploy-card:hover {
  transform: none;
  box-shadow: var(--shadow-md);
  border-color: var(--text);
  background: var(--surface);
}

.risk-green, .risk-red, .risk-orange, .risk-grey {
  border-left: 2px solid var(--text);
  background: var(--surface);
}

.pkg-card {
  border-radius: 8px; padding: 0.65rem 0.75rem; margin-bottom: 0.4rem;
  border: 1px solid var(--border);
  transition: none;
}
.pkg-card:hover {
  transform: none;
  border-color: var(--border);
}

.mono {
  font-family: var(--mono) !important;
  font-size: 0.8rem !important;
  white-space: pre-wrap;
}

.gls-section { margin-top: 1.2rem; }
.gls-section h3 {
  margin: 0 0 0.25rem; font-size: 0.98rem; font-weight: 600; letter-spacing: -0.02em;
}
.gls-muted { color: var(--muted); font-size: 0.84rem; line-height: 1.45; }

.gls-disclaimer {
  display: flex; gap: 0.55rem; align-items: flex-start;
  padding: 0.75rem 0.85rem; border-radius: 8px;
  background: var(--surface-2);
  border: 1px solid var(--border);
  box-shadow: none;
  font-size: 0.8rem; line-height: 1.45; color: var(--muted);
}

.gls-table-wrap {
  width: 100%; overflow-x: auto; border-radius: 8px;
  border: 1px solid var(--border); box-shadow: var(--shadow);
}
.gls-table-wrap .q-table { min-width: 560px; }

.gls-repo-link { font-family: var(--mono); font-size: 0.76rem; font-weight: 500; }

.gls-recent { display: flex; flex-direction: column; gap: 0.35rem; margin-top: 0.5rem; }
.gls-recent-item {
  display: flex; align-items: center; justify-content: space-between; gap: 0.5rem;
  padding: 0.55rem 0.65rem; border-radius: 8px;
  border: 1px solid var(--border); background: var(--surface);
  cursor: pointer; box-shadow: var(--shadow);
  transition: background .12s ease, box-shadow .12s ease;
}
.gls-recent-item:hover {
  transform: none;
  box-shadow: var(--shadow-md);
  background: var(--surface-2);
}

.gls-footer {
  margin-top: 1.5rem; text-align: center; color: var(--muted); font-size: 0.72rem;
  font-weight: 500;
}

.gls-scan-bar {
  height: 2px; background: transparent; overflow: hidden; position: relative; z-index: 101;
}
.gls-scan-bar .bar {
  height: 100%; width: 28%;
  background: var(--text);
  animation: gls-slide 1s ease-in-out infinite;
}
@keyframes gls-slide {
  0% { transform: translateX(-120%); }
  100% { transform: translateX(400%); }
}

.fade-in { animation: fadeIn .25s ease both; }
@keyframes fadeIn {
  from { opacity: 0; }
  to { opacity: 1; }
}

body.gls-scanning .gls-mark {
  animation: none;
  opacity: 0.7;
}
body.gls-scanning .gls-card {
  border-color: var(--border);
}
"""

CANVAS_BOOT = r"""
(() => {
  if (window.__glsCanvasBooted) return;
  window.__glsCanvasBooted = true;

  const canvas = document.getElementById('gls-bg-canvas');
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  let w = 0, h = 0, dpr = 1;

  function isDark() {
    return document.body.classList.contains('body--dark');
  }
  function bg() { return isDark() ? '#0a0a0a' : '#fafafa'; }
  function line() { return isDark() ? 'rgba(255,255,255,0.035)' : 'rgba(0,0,0,0.035)'; }
  function dot() { return isDark() ? 'rgba(255,255,255,0.08)' : 'rgba(0,0,0,0.06)'; }

  function resize() {
    dpr = Math.min(window.devicePixelRatio || 1, 2);
    w = window.innerWidth;
    h = window.innerHeight;
    canvas.width = Math.floor(w * dpr);
    canvas.height = Math.floor(h * dpr);
    canvas.style.width = w + 'px';
    canvas.style.height = h + 'px';
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    draw();
  }

  function draw() {
    ctx.clearRect(0, 0, w, h);
    ctx.fillStyle = bg();
    ctx.fillRect(0, 0, w, h);

    // Quiet grid
    const gap = 56;
    ctx.strokeStyle = line();
    ctx.lineWidth = 1;
    for (let x = 0; x <= w; x += gap) {
      ctx.beginPath(); ctx.moveTo(x, 0); ctx.lineTo(x, h); ctx.stroke();
    }
    for (let y = 0; y <= h; y += gap) {
      ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(w, y); ctx.stroke();
    }

    // Sparse dots at intersections
    ctx.fillStyle = dot();
    for (let x = 0; x <= w; x += gap) {
      for (let y = 0; y <= h; y += gap) {
        if ((x + y) % (gap * 2) === 0) {
          ctx.beginPath();
          ctx.arc(x, y, 1.2, 0, Math.PI * 2);
          ctx.fill();
        }
      }
    }
  }

  window.addEventListener('resize', resize, { passive: true });
  const mo = new MutationObserver(draw);
  mo.observe(document.body, { attributes: true, attributeFilter: ['class'] });
  resize();
})();
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

            # Verdict — incomplete scan (API/rate-limit) is not a legal "no"
            incomplete = not result.scan_complete or (
                bool(result.errors) and not result.repo_license and not result.packages
            )
            if incomplete:
                v_cls, title, sub, emoji = (
                    "warn",
                    t("verdict_incomplete_title", lang),
                    t("verdict_incomplete_sub", lang),
                    "⏳",
                )
            elif result.forces_open_source:
                v_cls, title, sub, emoji = (
                    "bad",
                    t("verdict_bad_title", lang),
                    t("verdict_bad_sub", lang),
                    "🚫",
                )
            elif (
                result.has_weak_copyleft
                or result.has_unknown_licenses
                or result.has_network_copyleft
            ):
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
            score_label_key = f"risk_label_{result.risk_score_label}"
            score_label = t(score_label_key, lang)
            if score_label == score_label_key:
                score_label = result.risk_score_label
            with ui.element("div").classes("gls-stats"):
                for label, value in (
                    (t("meta_repo_license", lang), result.repo_license or t("unknown", lang)),
                    (
                        t("meta_risk_score", lang),
                        f"{result.risk_score}/100 · {score_label}",
                    ),
                    (
                        t("meta_prod_dev", lang),
                        f"{result.prod_package_count} / {result.dev_package_count}",
                    ),
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
                                    ui.badge(str(adv.score)).props("color=grey")
                                for reason in adv.reasons[:3]:
                                    ui.label(f"• {reason}").classes("text-caption q-mt-xs")
                                ui.link(
                                    t("deploy_docs", lang), adv.docs_url, new_tab=True
                                ).classes("text-caption q-mt-sm")
                else:
                    ui.label(t("deploy_none", lang)).classes("gls-muted q-mt-sm")

            # Export Markdown
            md_report = render_markdown_report(result)
            with ui.element("div").classes("gls-section"):
                ui.html(f"<h3>{t('export_markdown', lang)}</h3>", sanitize=False)
                with ui.row().classes("gap-2 flex-wrap q-mt-sm"):
                    async def copy_markdown() -> None:
                        payload = json.dumps(md_report)
                        try:
                            await ui.run_javascript(
                                f"navigator.clipboard.writeText({payload})",
                                timeout=3.0,
                            )
                            ui.notify(t("export_copied", lang), type="positive")
                        except Exception:  # noqa: BLE001
                            ui.notify(t("copyright_copy_fail", lang), type="warning")

                    ui.button(
                        t("export_markdown", lang),
                        on_click=copy_markdown,
                        icon="content_copy",
                    ).props("outline rounded no-caps")

                    fname = (
                        f"{result.owner or 'repo'}-{result.repo or 'scan'}-license-report.md"
                    )
                    ui.button(
                        t("export_download", lang),
                        icon="download",
                        on_click=lambda: ui.download(
                            md_report.encode("utf-8"),
                            filename=fname,
                        ),
                    ).props("outline rounded no-caps")

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
                                            scope = (
                                                t("scope_dev", lang)
                                                if pkg.is_dev
                                                else t("scope_prod", lang)
                                            )
                                            ui.label(
                                                f"{pkg.ecosystem} · {scope} · {pkg.source_file}"
                                                + (
                                                    f" · {pkg.version_spec}"
                                                    if pkg.version_spec
                                                    else ""
                                                )
                                            ).classes("text-caption text-grey")
                                        with ui.row().classes("items-center gap-2"):
                                            ui.badge(scope).props("outline")
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
        '<meta name="theme-color" content="#111111">'
    )
    ui.add_css(CUSTOM_CSS)

    lang = get_lang()
    dark_pref = get_dark()
    dark = ui.dark_mode(dark_pref)
    # Cross-tab UI refresh hooks (history clear → recent list, etc.)
    ui_refreshers: list[Callable[[], None]] = []

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
                                    limited = _check_scan_budget(1)
                                    if limited:
                                        ui.notify(limited, type="warning")
                                        return
                                    url_input.value = url
                                    scan_btn.disable()
                                    scan_bar.set_visibility(True)
                                    status_label.set_text(t("scanning_status", lang))
                                    await ui.run_javascript(
                                        "document.body.classList.add('gls-scanning')",
                                        timeout=2.0,
                                    )
                                    _set_steps(step_els, 0)
                                    try:
                                        # Animate steps while awaiting the full pipeline
                                        _set_steps(step_els, 1)
                                        result = await analyze_repository(url)
                                        _set_steps(step_els, 2)
                                        if result.owner and result.scan_complete:
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
                                        try:
                                            await ui.run_javascript(
                                                "document.body.classList.remove('gls-scanning')",
                                                timeout=2.0,
                                            )
                                        except Exception:
                                            pass

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
                                ui_refreshers.append(render_recent)

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
                                    if len(urls) > MAX_BATCH_URLS:
                                        ui.notify(
                                            t(
                                                "notify_batch_too_many",
                                                lang,
                                                max=MAX_BATCH_URLS,
                                                count=len(urls),
                                            ),
                                            type="warning",
                                        )
                                        urls = urls[:MAX_BATCH_URLS]
                                    limited = _check_scan_budget(len(urls))
                                    if limited:
                                        ui.notify(limited, type="warning")
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
                                            if result.owner and result.scan_complete:
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

                                def do_clear_history() -> None:
                                    clear_history()
                                    refresh_history()
                                    for fn in ui_refreshers:
                                        try:
                                            fn()
                                        except Exception:  # noqa: BLE001
                                            pass
                                    ui.notify(t("history_cleared", lang), type="info")

                                with ui.row().classes("gap-2 flex-wrap"):
                                    ui.button(
                                        t("history_refresh", lang),
                                        on_click=refresh_history,
                                        icon="refresh",
                                    ).props("outline rounded no-caps dense")
                                    ui.button(
                                        t("history_clear", lang),
                                        on_click=do_clear_history,
                                        icon="delete_outline",
                                    ).props("outline rounded no-caps dense color=negative")
                                ui.label(t("history_privacy_note", lang)).classes(
                                    "gls-muted q-mt-sm"
                                ).style("font-size:0.75rem")
                                history_box
                                refresh_history()

                    # Disclaimer under sidebar
                    with ui.element("div").classes("gls-disclaimer q-mt-md"):
                        ui.icon("balance", size="sm")
                        ui.label(t("disclaimer", lang))
                    ui.label(t("token_hint", lang)).classes("gls-muted q-mt-sm").style(
                        "font-size:0.75rem"
                    )
                    with ui.row().classes("gap-3 q-mt-sm flex-wrap"):
                        ui.link(
                            t("link_privacy", lang),
                            "/docs/privacy",
                            new_tab=True,
                        ).classes("text-caption")
                        ui.link(
                            t("link_terms", lang),
                            "/docs/terms",
                            new_tab=True,
                        ).classes("text-caption")
                        ui.link(
                            t("link_legal", lang),
                            "/docs/legal",
                            new_tab=True,
                        ).classes("text-caption")

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


@ui.page("/docs/privacy")
def privacy_page() -> None:
    """Serve privacy policy (local markdown)."""
    _render_doc_page("PRIVACY.md", "Privacy")


@ui.page("/docs/terms")
def terms_page() -> None:
    """Serve terms of use (local markdown)."""
    _render_doc_page("TERMS.md", "Terms")


@ui.page("/docs/legal")
def legal_page() -> None:
    """Serve legal disclaimer (local markdown)."""
    _render_doc_page("LEGAL_DISCLAIMER.md", "Legal disclaimer")


def _render_doc_page(filename: str, title: str) -> None:
    from pathlib import Path

    lang = get_lang()
    path = Path(__file__).resolve().parent / "docs" / filename
    body = path.read_text(encoding="utf-8") if path.exists() else f"# {title}\n\nNot found."
    ui.add_css(CUSTOM_CSS)
    with ui.element("div").classes("gls-app"):
        with ui.element("div").classes("gls-wrap"):
            ui.link(t("back_home", lang), "/").classes("text-caption")
            ui.markdown(body).classes("gls-card q-mt-md")


def main() -> None:
    """Start the NiceGUI application server."""
    ui.run(
        title="GitHub License Scanner",
        reload=False,
        host=HOST,
        port=PORT,
        show=SHOW_BROWSER,
        favicon="⚖️",
        dark=None,
        storage_secret=STORAGE_SECRET,
    )


if __name__ in {"__main__", "__mp_main__"}:
    main()
