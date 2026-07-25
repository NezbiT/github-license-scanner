"""
Deploy platform recommender.

Inspects repository language, dependency names, and Dockerfile presence
to suggest where the application is easiest to host (Vercel, Railway, etc.).

This is heuristic guidance for developers — not a production capacity plan.
"""

from __future__ import annotations

from .models import Dependency, DeployAdvice

# ---------------------------------------------------------------------------
# Platform catalog
# ---------------------------------------------------------------------------

PLATFORMS: dict[str, dict[str, str]] = {
    "Vercel": {
        "docs_url": "https://vercel.com/docs",
        "blurb": "Frontend and serverless-first hosting",
    },
    "Cloudflare Pages": {
        "docs_url": "https://developers.cloudflare.com/pages/",
        "blurb": "Static sites and Pages Functions at the edge",
    },
    "Netlify": {
        "docs_url": "https://docs.netlify.com/",
        "blurb": "JAMstack and static site hosting",
    },
    "Railway": {
        "docs_url": "https://docs.railway.app/",
        "blurb": "Simple full-stack deploys from Git",
    },
    "Render": {
        "docs_url": "https://render.com/docs",
        "blurb": "Web services, workers, and static sites",
    },
    "Fly.io": {
        "docs_url": "https://fly.io/docs/",
        "blurb": "Global app VMs close to users",
    },
    "Google Cloud Run": {
        "docs_url": "https://cloud.google.com/run/docs",
        "blurb": "Containerized services that scale to zero",
    },
    "GitHub Pages": {
        "docs_url": "https://docs.github.com/pages",
        "blurb": "Free static hosting from the repo",
    },
    "Hugging Face / RunPod / GPU VPS": {
        "docs_url": "https://huggingface.co/docs/hub/spaces-sdks-docker",
        "blurb": "GPU-oriented hosts for ML workloads",
    },
    "Any VPS (Docker)": {
        "docs_url": "https://docs.docker.com/get-started/",
        "blurb": "Full control with Docker on a VPS",
    },
}

# Frontend framework package names (lowercase)
FRONTEND_FRAMEWORKS = {
    "next": "Next.js",
    "nuxt": "Nuxt",
    "vite": "Vite",
    "react": "React",
    "react-dom": "React",
    "vue": "Vue",
    "@angular/core": "Angular",
    "svelte": "Svelte",
    "astro": "Astro",
    "gatsby": "Gatsby",
    "@remix-run/react": "Remix",
}

# Backend / full-stack Python & similar
BACKEND_PYTHON = {
    "fastapi",
    "flask",
    "django",
    "nicegui",
    "starlette",
    "uvicorn",
    "gunicorn",
    "streamlit",
    "gradio",
    "dash",
    "tornado",
    "sanic",
    "aiohttp",
}

BACKEND_NODE = {
    "express",
    "fastify",
    "koa",
    "nestjs",
    "@nestjs/core",
    "hono",
    "hapi",
}

ML_HEAVY = {
    "torch",
    "pytorch",
    "tensorflow",
    "keras",
    "transformers",
    "diffusers",
    "langchain",
    "scikit-learn",
    "sklearn",
    "xgboost",
    "opencv-python",
    "opencv-python-headless",
}


def recommend_deploy(
    *,
    primary_language: str | None,
    topics: list[str] | None,
    dependencies: list[Dependency],
    dependency_files: list[str] | None = None,
    has_dockerfile: bool = False,
    description: str | None = None,
) -> list[DeployAdvice]:
    """
    Score deploy platforms and return them sorted by score (descending).

    Only platforms with score > 0 are returned (plus a sensible default if none).
    """
    scores: dict[str, int] = {name: 0 for name in PLATFORMS}
    reasons: dict[str, list[str]] = {name: [] for name in PLATFORMS}

    dep_names = {d.name.lower() for d in dependencies}
    ecosystems = {d.ecosystem for d in dependencies}
    files = [f.replace("\\", "/").lower() for f in (dependency_files or [])]
    lang = (primary_language or "").lower()
    topic_set = {t.lower() for t in (topics or [])}
    desc = (description or "").lower()

    def bump(platform: str, points: int, reason: str) -> None:
        scores[platform] += points
        if reason not in reasons[platform]:
            reasons[platform].append(reason)

    # --- Dockerfile signal ---
    if has_dockerfile:
        bump("Fly.io", 25, "Dockerfile detected — container-friendly hosts fit well")
        bump("Railway", 22, "Dockerfile detected — Railway deploys containers easily")
        bump("Render", 20, "Dockerfile detected — Render supports Docker web services")
        bump("Google Cloud Run", 22, "Dockerfile detected — Cloud Run is container-native")
        bump("Any VPS (Docker)", 18, "Dockerfile present — any Docker host works")

    # --- Frontend frameworks ---
    found_fe: list[str] = []
    for pkg, label in FRONTEND_FRAMEWORKS.items():
        if pkg in dep_names:
            found_fe.append(label)
    if found_fe:
        labels = ", ".join(sorted(set(found_fe)))
        bump("Vercel", 35, f"Frontend stack detected ({labels})")
        bump("Netlify", 28, f"Frontend stack detected ({labels})")
        bump("Cloudflare Pages", 26, f"Frontend stack detected ({labels})")
        if "next" in dep_names or "Next.js" in found_fe:
            bump("Vercel", 15, "Next.js is first-class on Vercel")
        if "nuxt" in dep_names:
            bump("Vercel", 10, "Nuxt deploys cleanly on Vercel / Node hosts")
            bump("Railway", 8, "Nuxt can run as a Node service on Railway")

    # --- Backend Python ---
    py_hits = sorted(BACKEND_PYTHON & dep_names)
    if py_hits:
        bump("Railway", 32, f"Python backend packages: {', '.join(py_hits)}")
        bump("Render", 30, f"Python backend packages: {', '.join(py_hits)}")
        bump("Fly.io", 24, f"Python backend packages: {', '.join(py_hits)}")
        if "nicegui" in dep_names:
            bump("Railway", 8, "NiceGUI needs a long-running Python process (not pure static hosts)")
            bump("Render", 8, "NiceGUI needs a long-running Python process")
        if "streamlit" in dep_names or "gradio" in dep_names:
            bump("Railway", 6, "Streamlit/Gradio apps need a process host")
            bump("Hugging Face / RunPod / GPU VPS", 10, "ML demo UIs often ship on HF Spaces")

    # --- Backend Node ---
    node_hits = sorted(BACKEND_NODE & dep_names)
    if node_hits:
        bump("Railway", 28, f"Node backend packages: {', '.join(node_hits)}")
        bump("Render", 26, f"Node backend packages: {', '.join(node_hits)}")
        bump("Fly.io", 22, f"Node backend packages: {', '.join(node_hits)}")
        bump("Vercel", 12, "API routes / serverless Node can run on Vercel")

    # --- ML heavy ---
    ml_hits = sorted(ML_HEAVY & dep_names)
    if ml_hits:
        bump(
            "Hugging Face / RunPod / GPU VPS",
            40,
            f"Heavy ML libraries detected: {', '.join(ml_hits)}",
        )
        bump("Any VPS (Docker)", 15, "ML stacks often need custom GPU/CPU sizing")
        bump("Google Cloud Run", 8, "Possible if containerized and within memory limits")

    # --- Ecosystem files ---
    if any(f.endswith("go.mod") for f in files) or "go" in ecosystems:
        bump("Fly.io", 30, "Go module project — Fly.io is excellent for Go binaries")
        bump("Google Cloud Run", 26, "Go services containerize well for Cloud Run")
        bump("Railway", 18, "Go apps deploy on Railway")

    if any(f.endswith("cargo.toml") for f in files) or "cargo" in ecosystems:
        bump("Fly.io", 28, "Rust (Cargo) project — compile to a binary on Fly.io")
        bump("Railway", 20, "Rust projects can build on Railway")
        bump("Any VPS (Docker)", 16, "Rust binaries run well on a VPS")

    if any("composer.json" in f for f in files) or "composer" in ecosystems:
        bump("Railway", 20, "PHP (Composer) project")
        bump("Render", 18, "PHP (Composer) project")
        bump("Any VPS (Docker)", 15, "Classic PHP stack on VPS")

    if any(f.endswith("gemfile") for f in files) or "rubygems" in ecosystems:
        bump("Railway", 22, "Ruby (Bundler) project")
        bump("Render", 22, "Ruby (Bundler) project")
        bump("Fly.io", 16, "Ruby app on Fly.io")

    if any(f.endswith("pom.xml") or "build.gradle" in f for f in files):
        bump("Google Cloud Run", 22, "JVM project — containerize and run on Cloud Run")
        bump("Railway", 18, "JVM project")
        bump("Render", 18, "JVM project")
        bump("Any VPS (Docker)", 16, "JVM services commonly run via Docker on a VPS")

    # --- Language fallback signals ---
    if lang in {"javascript", "typescript"}:
        bump("Vercel", 12, f"Primary language is {primary_language}")
        bump("Cloudflare Pages", 10, f"Primary language is {primary_language}")
        bump("Netlify", 10, f"Primary language is {primary_language}")
    elif lang == "python":
        bump("Railway", 14, "Primary language is Python")
        bump("Render", 12, "Primary language is Python")
    elif lang == "go":
        bump("Fly.io", 14, "Primary language is Go")
        bump("Google Cloud Run", 12, "Primary language is Go")
    elif lang in {"html", "css"}:
        bump("GitHub Pages", 25, "Looks like a static site (HTML)")
        bump("Cloudflare Pages", 22, "Looks like a static site (HTML)")
        bump("Netlify", 20, "Looks like a static site (HTML)")
    elif lang == "rust":
        bump("Fly.io", 14, "Primary language is Rust")

    # Topics / description hints
    if topic_set & {"static-site", "documentation", "docs", "github-pages"}:
        bump("GitHub Pages", 20, "Topics suggest a documentation / static site")
        bump("Cloudflare Pages", 15, "Topics suggest a static site")
    if "docker" in topic_set or "docker" in desc:
        bump("Fly.io", 8, "Docker mentioned in topics/description")
        bump("Google Cloud Run", 8, "Docker mentioned in topics/description")

    # Pure static: only package.json missing backend, or no deps at all
    has_backend = bool(py_hits or node_hits or ml_hits)
    has_frontend = bool(found_fe)
    if has_frontend and not has_backend and not has_dockerfile:
        bump("Cloudflare Pages", 10, "Frontend-heavy with no clear backend process")
        bump("Netlify", 8, "Frontend-heavy with no clear backend process")

    # Default polyglot fallback so we always return something useful
    if max(scores.values(), default=0) == 0:
        bump("Railway", 10, "General-purpose Git deploy (no strong stack signals)")
        bump("Render", 9, "General-purpose Git deploy (no strong stack signals)")
        bump("Fly.io", 8, "General-purpose container/VM host")

    # Build sorted advice list
    advice: list[DeployAdvice] = []
    for platform, score in sorted(scores.items(), key=lambda x: (-x[1], x[0])):
        if score <= 0:
            continue
        meta = PLATFORMS[platform]
        advice.append(
            DeployAdvice(
                platform=platform,
                score=score,
                reasons=reasons[platform] or [meta["blurb"]],
                docs_url=meta["docs_url"],
            )
        )

    # Cap to top 5 recommendations for UI clarity
    return advice[:5]
