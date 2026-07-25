"""
Bilingual UI strings (Spanish / English) for the NiceGUI interface.

Usage:
    from i18n import t, normalize_lang
    label = t("scan_button", "es")
"""

from __future__ import annotations

from typing import Any

DEFAULT_LANG = "es"
SUPPORTED = ("es", "en")

# All product-facing UI strings. Keys are stable English identifiers.
TRANSLATIONS: dict[str, dict[str, str]] = {
    # Header
    "app_title": {
        "es": "GitHub License Scanner",
        "en": "GitHub License Scanner",
    },
    "app_subtitle": {
        "es": (
            "Analiza la licencia de un repositorio y de sus dependencias para estimar "
            "si puedes vender la app como software cerrado o si el copyleft obliga a abrir código."
        ),
        "en": (
            "Analyze a repository license and its dependencies to estimate whether you can "
            "sell the app as closed-source software or if copyleft requires opening the code."
        ),
    },
    "app_features": {
        "es": "Incluye historial, modo batch, aviso de copyright y recomendaciones de deploy.",
        "en": "Includes history, batch mode, copyright notice, and deploy recommendations.",
    },
    "disclaimer": {
        "es": (
            "Aviso legal: esta herramienta ofrece heurísticas automatizadas y NO constituye "
            "asesoramiento jurídico ni una opinión de compatibilidad de licencias. "
            "No garantiza no infracción. Las decisiones de cumplimiento (copyleft, SaaS/AGPL, "
            "atribución, contratos) deben revisarse con un abogado cualificado. "
            "El historial se guarda en el servidor/local de esta instancia."
        ),
        "en": (
            "Legal notice: this tool provides automated heuristics and is NOT legal advice "
            "or a license-compatibility opinion. It does not warrant non-infringement. "
            "Compliance decisions (copyleft, SaaS/AGPL, attribution, contracts) should be "
            "reviewed with a qualified attorney. Scan history is stored on this instance."
        ),
    },
    "token_hint": {
        "es": "Opcional: define la variable de entorno GITHUB_TOKEN para evitar límites de la API de GitHub.",
        "en": "Optional: set the GITHUB_TOKEN environment variable to avoid GitHub API rate limits.",
    },
    "language": {
        "es": "Idioma",
        "en": "Language",
    },
    "theme": {
        "es": "Tema",
        "en": "Theme",
    },
    "theme_dark": {
        "es": "Oscuro",
        "en": "Dark",
    },
    "theme_light": {
        "es": "Claro",
        "en": "Light",
    },
    "theme_toggle_to_light": {
        "es": "Cambiar a modo claro",
        "en": "Switch to light mode",
    },
    "theme_toggle_to_dark": {
        "es": "Cambiar a modo oscuro",
        "en": "Switch to dark mode",
    },
    "hero_badge": {
        "es": "Análisis de licencias · Copyleft · Deploy",
        "en": "License analysis · Copyleft · Deploy",
    },
    "scan_card_title": {
        "es": "Analizar repositorio",
        "en": "Analyze repository",
    },
    "scan_card_help": {
        "es": "Pega la URL de GitHub y obtén un veredicto de venta cerrada, riesgos por dependencia y dónde desplegar.",
        "en": "Paste a GitHub URL to get a closed-sale verdict, per-dependency risks, and deploy tips.",
    },
    "feature_scan": {
        "es": "Licencias del repo y paquetes",
        "en": "Repo & package licenses",
    },
    "feature_copyleft": {
        "es": "Señales GPL / AGPL",
        "en": "GPL / AGPL signals",
    },
    "feature_deploy": {
        "es": "Consejos de deploy",
        "en": "Deploy advice",
    },
    "feature_batch": {
        "es": "Modo lote e historial",
        "en": "Batch mode & history",
    },
    "try_example": {
        "es": "Probar ejemplo",
        "en": "Try an example",
    },
    "empty_title": {
        "es": "Aún no hay resultados",
        "en": "No results yet",
    },
    "empty_body": {
        "es": "Pega una URL de GitHub a la izquierda y pulsa Analizar. Verás el veredicto de venta cerrada, riesgos por paquete y recomendaciones de deploy.",
        "en": "Paste a GitHub URL on the left and click Analyze. You’ll see the closed-sale verdict, package risks, and deploy recommendations.",
    },
    "step_fetch": {
        "es": "Repositorio",
        "en": "Repository",
    },
    "step_deps": {
        "es": "Dependencias",
        "en": "Dependencies",
    },
    "step_licenses": {
        "es": "Licencias",
        "en": "Licenses",
    },
    "step_verdict": {
        "es": "Veredicto",
        "en": "Verdict",
    },
    "workspace_title": {
        "es": "Espacio de trabajo",
        "en": "Workspace",
    },
    "results_live": {
        "es": "Resultados en vivo",
        "en": "Live results",
    },
    "scroll_results": {
        "es": "Ver resultados",
        "en": "View results",
    },
    "open_repo": {
        "es": "Abrir en GitHub",
        "en": "Open on GitHub",
    },
    "risk_legend": {
        "es": "Agrupado por licencia · revisa el badge de riesgo en cada paquete",
        "en": "Grouped by license · check each package risk badge",
    },
    "how_it_works": {
        "es": "Cómo funciona",
        "en": "How it works",
    },
    "how_1": {
        "es": "1. Leemos la licencia del repo en GitHub",
        "en": "1. We read the repo license from GitHub",
    },
    "how_2": {
        "es": "2. Parseamos package.json, requirements, Cargo…",
        "en": "2. We parse package.json, requirements, Cargo…",
    },
    "how_3": {
        "es": "3. Consultamos registros (npm, PyPI, crates…)",
        "en": "3. We query registries (npm, PyPI, crates…)",
    },
    "how_4": {
        "es": "4. Calculamos riesgos y sugerimos deploy",
        "en": "4. We score risk and suggest deploy targets",
    },
    "recent_scans": {
        "es": "Escaneos recientes",
        "en": "Recent scans",
    },
    "rescan": {
        "es": "Reanalizar",
        "en": "Rescan",
    },
    # Tabs
    "tab_scan": {"es": "Escanear", "en": "Scan"},
    "tab_batch": {"es": "Batch", "en": "Batch"},
    "tab_history": {"es": "Historial", "en": "History"},
    # Scan form
    "url_label": {
        "es": "URL del repositorio GitHub",
        "en": "GitHub repository URL",
    },
    "url_placeholder": {
        "es": "https://github.com/owner/repo",
        "en": "https://github.com/owner/repo",
    },
    "scan_button": {"es": "Analizar", "en": "Analyze"},
    "scanning_status": {
        "es": "Analizando repositorio, dependencias y registros…",
        "en": "Analyzing repository, dependencies, and registries…",
    },
    "notify_paste_url": {
        "es": "Pega una URL de GitHub",
        "en": "Paste a GitHub URL",
    },
    "notify_strong_copyleft": {
        "es": "Copyleft fuerte detectado",
        "en": "Strong copyleft detected",
    },
    "notify_done": {
        "es": "Análisis completado",
        "en": "Analysis complete",
    },
    "notify_unexpected": {
        "es": "Error inesperado: {error}",
        "en": "Unexpected error: {error}",
    },
    # Batch
    "batch_help": {
        "es": "Pega varias URLs (una por línea). Se analizarán en secuencia.",
        "en": "Paste several URLs (one per line). They will be analyzed in sequence.",
    },
    "batch_urls_label": {"es": "URLs", "en": "URLs"},
    "batch_button": {"es": "Analizar lote", "en": "Analyze batch"},
    "batch_status": {
        "es": "Analizando {i}/{total}: {url}",
        "en": "Analyzing {i}/{total}: {url}",
    },
    "notify_batch_empty": {
        "es": "Añade al menos una URL",
        "en": "Add at least one URL",
    },
    "notify_batch_done": {
        "es": "Lote completado: {count} repos",
        "en": "Batch complete: {count} repos",
    },
    "notify_batch_error": {
        "es": "Error en batch: {error}",
        "en": "Batch error: {error}",
    },
    "notify_batch_too_many": {
        "es": "Lote limitado a {max} URLs (había {count}). Se procesarán las primeras.",
        "en": "Batch capped at {max} URLs (got {count}). Processing the first ones.",
    },
    "rate_limited": {
        "es": (
            "Límite de análisis alcanzado ({limit} por {window}s). "
            "Espera ~{wait}s o reduce el uso. Esto protege la API de GitHub."
        ),
        "en": (
            "Scan rate limit reached ({limit} per {window}s). "
            "Wait ~{wait}s or reduce usage. This protects the GitHub API."
        ),
    },
    # History
    "history_refresh": {
        "es": "Actualizar historial",
        "en": "Refresh history",
    },
    "history_clear": {
        "es": "Borrar historial",
        "en": "Clear history",
    },
    "history_cleared": {
        "es": "Historial borrado.",
        "en": "History cleared.",
    },
    "history_privacy_note": {
        "es": (
            "Privacidad: el historial se guarda en disco de esta instancia y es "
            "compartido entre usuarios si el servidor es multi-usuario. "
            "Puedes borrarlo aquí (borrado local)."
        ),
        "en": (
            "Privacy: history is stored on this instance’s disk and is shared across "
            "users if the server is multi-user. You can clear it here (local erasure)."
        ),
    },
    "history_empty": {
        "es": "Aún no hay historial. Analiza un repositorio para empezar.",
        "en": "No history yet. Analyze a repository to get started.",
    },
    "history_count": {
        "es": "{count} repositorio(s) en historial",
        "en": "{count} repository(ies) in history",
    },
    "link_privacy": {"es": "Privacidad", "en": "Privacy"},
    "link_terms": {"es": "Términos", "en": "Terms"},
    "link_legal": {"es": "Aviso legal", "en": "Legal notice"},
    "back_home": {"es": "← Volver al escáner", "en": "← Back to scanner"},
    "col_when": {"es": "Fecha", "en": "Date"},
    "col_repo": {"es": "Repositorio", "en": "Repository"},
    "col_license": {"es": "Licencia", "en": "License"},
    "col_pkgs": {"es": "Paquetes", "en": "Packages"},
    "col_closed": {"es": "Venta cerrada", "en": "Closed sale"},
    "col_force": {"es": "Obliga abrir", "en": "Forces open"},
    "yes": {"es": "Sí", "en": "Yes"},
    "no": {"es": "No", "en": "No"},
    # Results section
    "results": {"es": "Resultados", "en": "Results"},
    "batch_results": {
        "es": "Resultados del lote",
        "en": "Batch results",
    },
    "batch_last_detail": {
        "es": "Detalle del último escaneo del lote",
        "en": "Detail of the last scan in the batch",
    },
    # Verdict
    "verdict_bad_title": {
        "es": "Alto riesgo para software cerrado (heurística)",
        "en": "High risk for closed-source distribution (heuristic)",
    },
    "verdict_bad_sub": {
        "es": (
            "Señales de copyleft fuerte (GPL/AGPL/SSPL u otras). El resultado depende del "
            "modelo de enlace, distribución y uso en red. No es una prohibición legal automática."
        ),
        "en": (
            "Strong copyleft signals (GPL/AGPL/SSPL or similar). Outcome depends on linking, "
            "distribution, and network use. This is not an automatic legal prohibition."
        ),
    },
    "verdict_warn_title": {
        "es": "Posible venta cerrada — con precauciones",
        "en": "Closed-source sale may be possible — with caveats",
    },
    "verdict_warn_sub": {
        "es": "No hay copyleft fuerte detectado, pero hay licencias débiles o desconocidas que requieren revisión.",
        "en": "No strong copyleft detected, but weak or unknown licenses need manual review.",
    },
    "verdict_ok_title": {
        "es": "Parece viable vender como software cerrado",
        "en": "Closed-source sale appears viable",
    },
    "verdict_ok_sub": {
        "es": "No se detectó copyleft fuerte en la licencia del repo ni en las dependencias resueltas.",
        "en": "No strong copyleft found in the repo license or resolved dependencies.",
    },
    "verdict_incomplete_title": {
        "es": "Análisis incompleto",
        "en": "Incomplete analysis",
    },
    "verdict_incomplete_sub": {
        "es": "No se pudo obtener suficiente información de GitHub (rate limit, red o permisos). Configura GITHUB_TOKEN e inténtalo de nuevo.",
        "en": "Could not fetch enough data from GitHub (rate limit, network, or permissions). Set GITHUB_TOKEN and try again.",
    },
    # Meta cards
    "meta_repo_license": {
        "es": "Licencia del repositorio",
        "en": "Repository license",
    },
    "meta_language": {
        "es": "Lenguaje principal",
        "en": "Primary language",
    },
    "meta_packages": {
        "es": "Paquetes analizados",
        "en": "Packages analyzed",
    },
    "meta_forces_open": {
        "es": "¿Obliga a abrir código?",
        "en": "Forces open source?",
    },
    "meta_risk_score": {
        "es": "Score de riesgo",
        "en": "Risk score",
    },
    "meta_prod_dev": {
        "es": "Prod / Dev",
        "en": "Prod / Dev",
    },
    "scope_prod": {"es": "prod", "en": "prod"},
    "scope_dev": {"es": "dev", "en": "dev"},
    "export_markdown": {
        "es": "Exportar Markdown",
        "en": "Export Markdown",
    },
    "export_copied": {
        "es": "Reporte Markdown copiado al portapapeles",
        "en": "Markdown report copied to clipboard",
    },
    "export_download": {
        "es": "Descargar .md",
        "en": "Download .md",
    },
    "risk_label_minimal": {"es": "mínimo", "en": "minimal"},
    "risk_label_low": {"es": "bajo", "en": "low"},
    "risk_label_medium": {"es": "medio", "en": "medium"},
    "risk_label_high": {"es": "alto", "en": "high"},
    "unknown": {"es": "Desconocida", "en": "Unknown"},
    # Risk labels
    "risk_permissive": {"es": "Permisiva", "en": "Permissive"},
    "risk_strong": {"es": "Copyleft fuerte", "en": "Strong copyleft"},
    "risk_weak": {"es": "Copyleft débil", "en": "Weak copyleft"},
    "risk_unknown": {"es": "Desconocida", "en": "Unknown"},
    # Sections
    "notes_warnings": {
        "es": "Notas / advertencias",
        "en": "Notes / warnings",
    },
    "deploy_title": {
        "es": "Dónde desplegar (recomendación)",
        "en": "Where to deploy (recommendation)",
    },
    "deploy_help": {
        "es": "Sugerencias heurísticas según el stack detectado (lenguaje, dependencias, Docker).",
        "en": "Heuristic suggestions based on the detected stack (language, dependencies, Docker).",
    },
    "deploy_docs": {"es": "Documentación", "en": "Documentation"},
    "deploy_none": {
        "es": "Sin recomendaciones.",
        "en": "No recommendations.",
    },
    "copyright_title": {
        "es": "Aviso de copyright",
        "en": "Copyright notice",
    },
    "copyright_copy": {
        "es": "Copiar aviso de copyright",
        "en": "Copy copyright notice",
    },
    "copyright_copied": {
        "es": "Aviso de copyright copiado al portapapeles",
        "en": "Copyright notice copied to clipboard",
    },
    "copyright_copy_fail": {
        "es": "No se pudo copiar automáticamente. Selecciona el texto del área y copia manualmente (Ctrl+C).",
        "en": "Could not copy automatically. Select the text area and copy manually (Ctrl+C).",
    },
    "replacements_title": {
        "es": "Sugerencias de reemplazo (paquetes problemáticos)",
        "en": "Replacement suggestions (problematic packages)",
    },
    "replacements_help": {
        "es": "Alternativas heurísticas permisivas. Verifica siempre la licencia real del sustituto.",
        "en": "Heuristic permissive alternatives. Always verify the replacement's actual license.",
    },
    "packages_by_license": {
        "es": "Paquetes agrupados por licencia",
        "en": "Packages grouped by license",
    },
    "packages_none": {
        "es": "No se encontraron (o no se pudieron resolver) dependencias.",
        "en": "No dependencies found (or could not be resolved).",
    },
    "packages_count": {
        "es": "{license}  —  {count} paquete(s)",
        "en": "{license}  —  {count} package(s)",
    },
    "registry_link": {"es": "registro", "en": "registry"},
    "dep_files": {
        "es": "Archivos de dependencias analizados",
        "en": "Dependency files analyzed",
    },
    "error_prefix": {"es": "Error: {error}", "en": "Error: {error}"},
}


def normalize_lang(lang: str | None) -> str:
    """Return a supported language code (default Spanish)."""
    if not lang:
        return DEFAULT_LANG
    code = lang.lower().strip()
    if code.startswith("en"):
        return "en"
    if code.startswith("es"):
        return "es"
    return DEFAULT_LANG if code not in SUPPORTED else code


def t(key: str, lang: str = DEFAULT_LANG, **kwargs: Any) -> str:
    """
    Translate a UI key for the given language.

    Optional kwargs are applied with str.format for placeholders.
    Falls back to English, then to the key itself.
    """
    lang = normalize_lang(lang)
    entry = TRANSLATIONS.get(key) or {}
    text = entry.get(lang) or entry.get("en") or entry.get("es") or key
    if kwargs:
        try:
            return text.format(**kwargs)
        except (KeyError, ValueError):
            return text
    return text
