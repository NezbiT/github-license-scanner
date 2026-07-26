(() => {
  const STR = {
    es: {
      badge: "Licencias · Copyleft · CLI",
      kicker: "Open source · gratis · se ejecuta en tu máquina",
      hero_title:
        "¿Puedes vender tu app en cerrado… o el copyleft te obliga a abrir código?",
      hero_lead:
        "Analiza la licencia del repositorio GitHub y de sus dependencias. Señal heurística de riesgo GPL/AGPL, export Markdown/SBOM y UI local opcional. No es asesoramiento jurídico.",
      cta_install: "Instalar con pipx",
      cta_repo: "Ver en GitHub",
      cta_clone: "Clonar el repo",
      hero_fine:
        "Esta página es solo documentación estática (GitHub Pages). La herramienta corre en tu PC — sin SaaS y sin enviar tu código a terceros.",
      f1_t: "Repo + dependencias",
      f1_d: "npm, PyPI, Cargo, Go, RubyGems, Composer, Maven/Gradle (best-effort) y licencia del repo vía API de GitHub.",
      f2_t: "Copyleft / venta cerrada",
      f2_d: "Clasifica permisivas, copyleft débil/fuerte y señales AGPL/SSPL (SaaS). Score 0–100 y veredicto con disclaimers.",
      f3_t: "CLI, UI, SBOM",
      f3_d: "Comando gls, UI NiceGUI opcional, export Markdown, CycloneDX y SPDX. ES/EN y tema claro/oscuro.",
      install_title: "Instalar (recomendado)",
      install_sub: "Python 3.11+. pipx aísla la herramienta del resto de tu entorno.",
      install_cli: "Solo CLI",
      install_ui: "CLI + interfaz web local",
      install_ui_note:
        "Luego abre http://127.0.0.1:8080 en tu navegador (solo en tu máquina).",
      install_pip: "Con pip (venv)",
      pypi_link: "Paquete en PyPI:",
      clone_title: "Clonar desde GitHub",
      clone_sub: "Ideal si quieres contribuir o ejecutar la versión de desarrollo.",
      open_repo: "Abrir repositorio",
      download_zip: "Descargar ZIP",
      usage_title: "Uso rápido",
      token_hint:
        "Opcional: define GITHUB_TOKEN para más cuota de la API de GitHub y repos privados autorizados.",
      disc_title: "Aviso legal",
      disc_body:
        "Esta herramienta ofrece heurísticas automatizadas para desarrolladores. No es asesoramiento jurídico, ni una opinión de compatibilidad de licencias, ni una garantía de no infracción. Dual-licensing, linking, SaaS (AGPL/SSPL) y contratos pueden cambiar las obligaciones. Consulta a un abogado cualificado antes de distribuir software cerrado comercialmente.",
      link_legal: "Disclaimer",
      link_privacy: "Privacidad",
      link_terms: "Términos",
      footer: "Hecho con Python · MIT ·",
      copy: "Copiar",
      copied: "Copiado",
    },
    en: {
      badge: "Licenses · Copyleft · CLI",
      kicker: "Open source · free · runs on your machine",
      hero_title:
        "Can you sell closed-source… or does copyleft force you open?",
      hero_lead:
        "Analyze a GitHub repository license and its dependencies. Heuristic GPL/AGPL risk signals, Markdown/SBOM export, and an optional local UI. Not legal advice.",
      cta_install: "Install with pipx",
      cta_repo: "View on GitHub",
      cta_clone: "Clone the repo",
      hero_fine:
        "This page is static documentation only (GitHub Pages). The tool runs on your PC — no SaaS and no uploading your code to third parties.",
      f1_t: "Repo + dependencies",
      f1_d: "npm, PyPI, Cargo, Go, RubyGems, Composer, Maven/Gradle (best-effort) plus the repo license via the GitHub API.",
      f2_t: "Copyleft / closed sale",
      f2_d: "Classifies permissive, weak/strong copyleft, and AGPL/SSPL (SaaS) signals. 0–100 score and a disclaimer-heavy verdict.",
      f3_t: "CLI, UI, SBOM",
      f3_d: "gls command, optional NiceGUI UI, Markdown export, CycloneDX and SPDX. ES/EN and light/dark theme.",
      install_title: "Install (recommended)",
      install_sub:
        "Python 3.11+. pipx keeps the tool isolated from the rest of your environment.",
      install_cli: "CLI only",
      install_ui: "CLI + local web UI",
      install_ui_note:
        "Then open http://127.0.0.1:8080 in your browser (on your machine only).",
      install_pip: "With pip (venv)",
      pypi_link: "Package on PyPI:",
      clone_title: "Clone from GitHub",
      clone_sub: "Best if you want to contribute or run the development version.",
      open_repo: "Open repository",
      download_zip: "Download ZIP",
      usage_title: "Quick usage",
      token_hint:
        "Optional: set GITHUB_TOKEN for higher GitHub API limits and authorized private repos.",
      disc_title: "Legal notice",
      disc_body:
        "This tool provides automated heuristics for developers. It is not legal advice, not a license-compatibility opinion, and not a warranty of non-infringement. Dual-licensing, linking, SaaS (AGPL/SSPL), and contracts can change obligations. Consult a qualified attorney before commercial closed-source distribution.",
      link_legal: "Disclaimer",
      link_privacy: "Privacy",
      link_terms: "Terms",
      footer: "Built with Python · MIT ·",
      copy: "Copy",
      copied: "Copied",
    },
  };

  function lang() {
    const saved = localStorage.getItem("gls-pages-lang");
    if (saved === "en" || saved === "es") return saved;
    return (navigator.language || "es").toLowerCase().startsWith("en")
      ? "en"
      : "es";
  }

  function apply(l) {
    const table = STR[l] || STR.es;
    document.documentElement.lang = l;
    document.querySelectorAll("[data-i18n]").forEach((el) => {
      const key = el.getAttribute("data-i18n");
      if (key && table[key] != null) el.textContent = table[key];
    });
    document.querySelectorAll(".seg button").forEach((btn) => {
      btn.classList.toggle("is-on", btn.getAttribute("data-lang") === l);
    });
    localStorage.setItem("gls-pages-lang", l);
  }

  document.querySelectorAll(".seg button").forEach((btn) => {
    btn.addEventListener("click", () => apply(btn.getAttribute("data-lang")));
  });

  const toast = document.getElementById("toast");
  function flash(msg) {
    if (!toast) return;
    toast.hidden = false;
    toast.textContent = msg;
    clearTimeout(flash._t);
    flash._t = setTimeout(() => {
      toast.hidden = true;
    }, 1400);
  }

  document.querySelectorAll("[data-copy]").forEach((btn) => {
    btn.addEventListener("click", async () => {
      const id = btn.getAttribute("data-copy");
      const pre = document.getElementById(id);
      const text = pre ? pre.innerText : "";
      try {
        await navigator.clipboard.writeText(text);
        const l = localStorage.getItem("gls-pages-lang") || "es";
        flash((STR[l] || STR.es).copied);
      } catch {
        flash("…");
      }
    });
  });

  apply(lang());
})();
