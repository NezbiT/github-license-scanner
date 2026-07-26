# GitHub License Scanner

<p align="center">
  <img src="https://raw.githubusercontent.com/NezbiT/github-license-scanner/main/docs/images/hero.jpg" alt="GitHub License Scanner hero banner" width="100%" />
</p>

<p align="center">
  <strong>Analyze GitHub repo licenses + dependencies</strong><br/>
  Know if you can sell closed-source — or if copyleft (GPL / AGPL) forces open source.<br/>
  <em>NiceGUI web UI · CLI · bilingual ES/EN · light &amp; dark mode</em>
</p>

<p align="center">
  <a href="https://nezbit.github.io/github-license-scanner/"><img src="https://img.shields.io/badge/Site-GitHub%20Pages-2c3e50?style=flat-square" alt="GitHub Pages" /></a>
  <a href="#quick-start"><img src="https://img.shields.io/badge/Python-3.11%2B-2c3e50?style=flat-square" alt="Python" /></a>
  <a href="https://pypi.org/project/github-license-scanner/"><img src="https://img.shields.io/badge/PyPI-github--license--scanner-8b5e3c?style=flat-square" alt="PyPI" /></a>
  <a href="#cli"><img src="https://img.shields.io/badge/CLI-gls-3f6f4e?style=flat-square" alt="CLI" /></a>
  <a href="#disclaimer"><img src="https://img.shields.io/badge/Not-legal%20advice-9b2c2c?style=flat-square" alt="Disclaimer" /></a>
  <a href="https://github.com/NezbiT/github-license-scanner/blob/main/LICENSE"><img src="https://img.shields.io/badge/License-MIT-2c3e50?style=flat-square" alt="MIT License" /></a>
</p>

<p align="center">
  <strong>Website:</strong>
  <a href="https://nezbit.github.io/github-license-scanner/">nezbit.github.io/github-license-scanner</a>
  · install with <code>pipx</code> or clone from GitHub
</p>

---

## Screenshots

### Light workspace (full-width layout)

<p align="center">
  <img src="https://raw.githubusercontent.com/NezbiT/github-license-scanner/main/docs/images/ui-light.jpg" alt="Light mode UI — scan workspace and results" width="100%" />
</p>

### Dark mode

<p align="center">
  <img src="https://raw.githubusercontent.com/NezbiT/github-license-scanner/main/docs/images/ui-dark.jpg" alt="Dark mode UI — copyleft warning and package groups" width="100%" />
</p>

### How it works

<p align="center">
  <img src="https://raw.githubusercontent.com/NezbiT/github-license-scanner/main/docs/images/flow.jpg" alt="Flow: URL → fetch → registries → verdict → deploy" width="100%" />
</p>

| Step | What happens |
|------|----------------|
| 1 | Paste a GitHub URL (`owner/repo`) |
| 2 | Read repo license + dependency manifests |
| 3 | Look up package licenses on npm, PyPI, crates.io, … |
| 4 | Verdict: closed sale OK vs strong copyleft |
| 5 | Deploy tips + copyright notice to copy |

---

## Features

- **Repo license** via GitHub REST API  
- **Dependency scan** for `package.json`, `requirements.txt`, `pyproject.toml`, `Cargo.toml`, `go.mod`, `Gemfile`, `composer.json`, Maven/Gradle (best-effort)  
- **Registry license lookup** (npm, PyPI, crates.io, RubyGems, Packagist)  
- **Risk colors**: green (permissive) · orange (weak/unknown) · red (strong copyleft)  
- **Closed-source sellability** signal + GPL/AGPL force-open flag  
- **Permissive replacement** suggestions for problematic packages  
- **Batch mode** (many URLs) + **scan history**  
- **Copy copyright notice** button  
- **Deploy advisor** (Vercel, Railway, Render, Fly.io, …)  
- **ES / EN** UI · **light / dark** theme · **full-width** responsive layout  

---

## Website (GitHub Pages)

Static landing (install / clone links only — the scanner runs **on your machine**):

**https://nezbit.github.io/github-license-scanner/**

---

## Quick start

```bash
pipx install github-license-scanner
gls scan psf/requests
```

The web interface is an optional extra, so the CLI stays light:

```bash
pipx install 'github-license-scanner[ui]'
gls ui
```

Optional configuration (recommended):

```bash
# PowerShell example
$env:GITHUB_TOKEN = "ghp_..."
$env:GLS_STORAGE_SECRET = "long-random-string"
```

Environment variables are the source of truth. A `.env` file is only a local
convenience: one is read from the current directory or from your user config
directory if present, and real environment variables always win.

| Variable | Purpose |
|----------|---------|
| `GITHUB_TOKEN` | Higher GitHub API rate limits / private repos |
| `GLS_STORAGE_SECRET` | Signs session cookies (**required** for public deploys) |
| `GLS_HOST` / `GLS_PORT` | Bind address (default `127.0.0.1:8080`) |
| `GLS_MAX_BATCH_URLS` | Cap batch scans (default 15) |
| `GLS_RATE_LIMIT_SCANS` | Scans per window per client (default 20/hour) |
| `GLS_AUTH_ENABLED` | Require web login (`1` / `true`) |
| `GLS_USERS_FILE` | JSON users DB (default: `users.json` in the data dir) |
| `GLS_DATA_DIR` | Override where history and users are stored |

See [`.env.example`](https://github.com/NezbiT/github-license-scanner/blob/main/.env.example) for the full list.

History and users live in your per-user data directory, never inside the
installed package:

| OS | Path |
|----|------|
| Windows | `%LOCALAPPDATA%\NezbiT\github-license-scanner` |
| macOS | `~/Library/Application Support/github-license-scanner` |
| Linux | `~/.local/share/github-license-scanner` |

### Multi-user auth + private history

```bash
gls user-add alice          # interactive password (≥8 chars)

export GLS_AUTH_ENABLED=1
export GLS_STORAGE_SECRET=long-random-string
```

Each user gets `history/<username>.json` in that data directory. Without auth,
history stays in a single `history.json`.

---

## Web UI

```bash
pipx install 'github-license-scanner[ui]'
gls ui                       # or: gls ui --host 0.0.0.0 --port 9000
```

Open **[http://127.0.0.1:8080](http://127.0.0.1:8080)** (binds to localhost by default)

- Switch **ES | EN** in the top bar  
- Toggle **light / dark** with the sun/moon button  
- Try example chips (`psf/requests`, `encode/httpx`, …)  

---

## CLI

```bash
# Single repository
gls scan https://github.com/psf/requests

# Shorthand
gls scan psf/requests

# Batch (one URL per line)
gls batch urls.example.txt

# History
gls history

# Markdown + SBOM export
gls scan psf/requests --markdown report.md --sbom bom.cdx.json
gls scan psf/requests --sbom bom.spdx.json --sbom-format spdx
```

`github-license-scanner` is available as a longer alias for `gls`.

| Exit code | Meaning |
|-----------|---------|
| `0` | No strong copyleft force-open signal |
| `1` | Strong copyleft detected |
| `2` | Hard failure (bad URL, API error, …) |

---

## Project layout

```text
github-license-scanner/
├── pyproject.toml          # Packaging (hatchling)
├── gls/
│   ├── __init__.py         # __version__
│   ├── cli.py              # Command-line mode + entry point
│   ├── webui.py            # NiceGUI interface (optional [ui] extra)
│   ├── config.py           # Env-based configuration + data paths
│   ├── rate_limit.py       # Scan rate limiter
│   ├── auth.py             # Optional multi-user auth (PBKDF2)
│   ├── spdx_engine.py      # SPDX expression parser + risk
│   ├── sbom_export.py      # CycloneDX 1.5 + SPDX 2.3 JSON
│   ├── github_api.py       # URL parse + GitHub REST
│   ├── dependency_scanner.py  # Manifest parsers
│   ├── license_analyzer.py    # Registry licenses + verdict
│   ├── deploy_advisor.py   # Deploy recommendations
│   ├── history_store.py    # JSON history (shared or per-user)
│   ├── models.py           # Dataclasses
│   ├── i18n.py             # ES/EN strings
│   ├── report.py           # Markdown export
│   └── docs/               # Legal pages served by the web UI
│       ├── LEGAL_DISCLAIMER.md
│       ├── PRIVACY.md
│       └── TERMS.md
├── scripts/                # Dev smoke tests / audit tooling
├── .env.example
├── urls.example.txt
└── docs/
    ├── AUDIT_REPORT.pdf
    └── images/             # README screenshots
```

---

## License risk legend

| Color | Risk | Examples |
|-------|------|----------|
| Green | Permissive | MIT, Apache-2.0, BSD, ISC |
| Orange | Weak copyleft / unknown | LGPL, MPL, EUPL, missing metadata |
| Red | Strong copyleft | GPL, AGPL, SSPL |

---

## Security & privacy notes

- Default bind is **localhost only** (`GLS_HOST=127.0.0.1`).
- Set a strong **`GLS_STORAGE_SECRET`** before exposing the UI.
- Scan history is **instance-local** and shared if multi-user — use **Clear history** or prune via config.
- Rate limits and batch caps reduce GitHub API abuse.
- Docs: [Privacy](https://github.com/NezbiT/github-license-scanner/blob/main/gls/docs/PRIVACY.md) · [Terms](https://github.com/NezbiT/github-license-scanner/blob/main/gls/docs/TERMS.md) · [Legal disclaimer](https://github.com/NezbiT/github-license-scanner/blob/main/gls/docs/LEGAL_DISCLAIMER.md)

---

## Disclaimer

This tool provides **automated heuristics only**. It is **not legal advice** and not a  
license-compatibility opinion. Dual-licensing, linking models, SaaS (AGPL/SSPL),  
attribution duties, and contracts can change obligations.  
Always review with a qualified attorney before commercial closed-source distribution.  
See [gls/docs/LEGAL_DISCLAIMER.md](https://github.com/NezbiT/github-license-scanner/blob/main/gls/docs/LEGAL_DISCLAIMER.md).

---

## Development

```bash
git clone https://github.com/NezbiT/github-license-scanner.git
cd github-license-scanner

python -m venv .venv
.venv\Scripts\activate          # macOS / Linux: source .venv/bin/activate

pip install -e '.[ui]'
python -m gls.cli scan psf/requests
```

Build and check a release locally before tagging:

```bash
pip install build twine
python -m build
twine check dist/*
```

Releases are published to PyPI by [`.github/workflows/publish.yml`](https://github.com/NezbiT/github-license-scanner/blob/main/.github/workflows/publish.yml)
using Trusted Publishing (OIDC) — no API tokens are stored anywhere.

---

## License

Released under the **[MIT License](https://github.com/NezbiT/github-license-scanner/blob/main/LICENSE)**.

You may use, modify, and redistribute this project commercially or privately,  
as long as you keep the copyright and license notice. See `LICENSE` for full text.

> The MIT license applies to **this tool’s source code**.  
> It does **not** change the licenses of the GitHub repositories or packages you scan.

---

<p align="center">
  Made with NiceGUI · httpx · packaging
</p>
