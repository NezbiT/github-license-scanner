# GitHub License Scanner

<p align="center">
  <img src="docs/images/hero.jpg" alt="GitHub License Scanner hero banner" width="100%" />
</p>

<p align="center">
  <strong>Analyze GitHub repo licenses + dependencies</strong><br/>
  Know if you can sell closed-source — or if copyleft (GPL / AGPL) forces open source.<br/>
  <em>NiceGUI web UI · CLI · bilingual ES/EN · light &amp; dark mode</em>
</p>

<p align="center">
  <a href="#quick-start"><img src="https://img.shields.io/badge/Python-3.11%2B-2c3e50?style=flat-square" alt="Python" /></a>
  <a href="#web-ui"><img src="https://img.shields.io/badge/UI-NiceGUI-8b5e3c?style=flat-square" alt="NiceGUI" /></a>
  <a href="#cli"><img src="https://img.shields.io/badge/CLI-supported-3f6f4e?style=flat-square" alt="CLI" /></a>
  <a href="#disclaimer"><img src="https://img.shields.io/badge/Not-legal%20advice-9b2c2c?style=flat-square" alt="Disclaimer" /></a>
</p>

---

## Screenshots

### Light workspace (full-width layout)

<p align="center">
  <img src="docs/images/ui-light.jpg" alt="Light mode UI — scan workspace and results" width="100%" />
</p>

### Dark mode

<p align="center">
  <img src="docs/images/ui-dark.jpg" alt="Dark mode UI — copyleft warning and package groups" width="100%" />
</p>

### How it works

<p align="center">
  <img src="docs/images/flow.jpg" alt="Flow: URL → fetch → registries → verdict → deploy" width="100%" />
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

## Quick start

```bash
git clone https://github.com/NezbiT/github-license-scanner.git
cd github-license-scanner

python -m venv .venv

# Windows
.venv\Scripts\activate

# macOS / Linux
# source .venv/bin/activate

pip install -r requirements.txt
```

Optional (higher GitHub API rate limits):

```bash
# PowerShell
$env:GITHUB_TOKEN = "ghp_..."

# bash
export GITHUB_TOKEN=ghp_...
```

---

## Web UI

```bash
python main.py
```

Open **[http://127.0.0.1:8080](http://127.0.0.1:8080)**

- Switch **ES | EN** in the top bar  
- Toggle **light / dark** with the sun/moon button  
- Try example chips (`psf/requests`, `encode/httpx`, …)  

---

## CLI

```bash
# Single repository
python cli.py scan https://github.com/psf/requests

# Shorthand
python cli.py scan psf/requests

# Batch (one URL per line)
python cli.py batch urls.example.txt

# History
python cli.py history
```

| Exit code | Meaning |
|-----------|---------|
| `0` | No strong copyleft force-open signal |
| `1` | Strong copyleft detected |
| `2` | Hard failure (bad URL, API error, …) |

---

## Project layout

```text
github-license-scanner/
├── main.py                 # NiceGUI interface
├── cli.py                  # Command-line mode
├── github_api.py           # URL parse + GitHub REST
├── dependency_scanner.py   # Manifest parsers
├── license_analyzer.py     # Registry licenses + verdict
├── deploy_advisor.py       # Deploy recommendations
├── history_store.py        # JSON history
├── models.py               # Dataclasses
├── i18n.py                 # ES/EN strings
├── requirements.txt
├── urls.example.txt
└── docs/images/            # README screenshots
```

---

## License risk legend

| Color | Risk | Examples |
|-------|------|----------|
| Green | Permissive | MIT, Apache-2.0, BSD, ISC |
| Orange | Weak copyleft / unknown | LGPL, MPL, missing metadata |
| Red | Strong copyleft | GPL, AGPL, SSPL |

---

## Disclaimer

This tool provides **automated heuristics only**. It is **not legal advice**.  
Dual-licensing, linking models, SaaS (AGPL), and distribution choices can change obligations.  
Always review with a qualified attorney before commercial closed-source distribution.

---

## License

This project source is provided for educational and developer productivity use.  
Add a formal `LICENSE` file of your choice if you redistribute.

---

<p align="center">
  Made with NiceGUI · httpx · packaging
</p>
