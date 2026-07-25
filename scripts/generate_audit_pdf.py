"""
Generate docs/AUDIT_REPORT.pdf — architecture, security, legal review and changes.

Run:  python scripts/generate_audit_pdf.py
"""

from __future__ import annotations

import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm, mm
    from reportlab.platypus import (
        ListFlowable,
        ListItem,
        PageBreak,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )
except ImportError:
    print("Installing reportlab…")
    import subprocess

    subprocess.check_call([sys.executable, "-m", "pip", "install", "reportlab>=4.0.0"])
    from reportlab.lib import colors
    from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
    from reportlab.lib.units import cm, mm
    from reportlab.platypus import (
        ListFlowable,
        ListItem,
        PageBreak,
        Paragraph,
        SimpleDocTemplate,
        Spacer,
        Table,
        TableStyle,
    )


OUT = ROOT / "docs" / "AUDIT_REPORT.pdf"


def styles():
    base = getSampleStyleSheet()
    return {
        "title": ParagraphStyle(
            "T",
            parent=base["Title"],
            fontSize=18,
            leading=22,
            spaceAfter=8,
            textColor=colors.HexColor("#111111"),
            alignment=TA_CENTER,
        ),
        "sub": ParagraphStyle(
            "S",
            parent=base["Normal"],
            fontSize=10,
            leading=13,
            textColor=colors.HexColor("#525252"),
            alignment=TA_CENTER,
            spaceAfter=16,
        ),
        "h1": ParagraphStyle(
            "H1",
            parent=base["Heading1"],
            fontSize=14,
            leading=18,
            spaceBefore=14,
            spaceAfter=8,
            textColor=colors.HexColor("#111111"),
        ),
        "h2": ParagraphStyle(
            "H2",
            parent=base["Heading2"],
            fontSize=11,
            leading=14,
            spaceBefore=10,
            spaceAfter=6,
            textColor=colors.HexColor("#262626"),
        ),
        "body": ParagraphStyle(
            "B",
            parent=base["Normal"],
            fontSize=9,
            leading=12,
            alignment=TA_JUSTIFY,
            spaceAfter=6,
        ),
        "bullet": ParagraphStyle(
            "Bu",
            parent=base["Normal"],
            fontSize=9,
            leading=12,
            leftIndent=4,
        ),
        "meta": ParagraphStyle(
            "M",
            parent=base["Normal"],
            fontSize=8,
            leading=10,
            textColor=colors.HexColor("#737373"),
            alignment=TA_CENTER,
        ),
        "crit": ParagraphStyle(
            "C",
            parent=base["Normal"],
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#7f1d1d"),
            spaceAfter=4,
        ),
        "ok": ParagraphStyle(
            "O",
            parent=base["Normal"],
            fontSize=9,
            leading=12,
            textColor=colors.HexColor("#14532d"),
            spaceAfter=4,
        ),
        "cell": ParagraphStyle(
            "Cell",
            parent=base["Normal"],
            fontSize=8,
            leading=10,
        ),
    }


def bullets(items: list[str], st) -> ListFlowable:
    return ListFlowable(
        [ListItem(Paragraph(i, st["bullet"]), leftIndent=8, value="•") for i in items],
        bulletType="bullet",
        start="•",
        leftIndent=12,
        spaceBefore=2,
        spaceAfter=8,
    )


def severity_table(rows: list[tuple[str, str, str]], st) -> Table:
    header = [
        Paragraph("<b>ID</b>", st["cell"]),
        Paragraph("<b>Severity</b>", st["cell"]),
        Paragraph("<b>Finding</b>", st["cell"]),
    ]
    data = [header]
    for rid, sev, text in rows:
        data.append(
            [
                Paragraph(rid, st["cell"]),
                Paragraph(sev, st["cell"]),
                Paragraph(text, st["cell"]),
            ]
        )
    t = Table(data, colWidths=[1.4 * cm, 2.2 * cm, 13.5 * cm])
    t.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e5e5e5")),
                ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#a3a3a3")),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
                ("TOPPADDING", (0, 0), (-1, -1), 3),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
            ]
        )
    )
    return t


def build() -> Path:
    st = styles()
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    story: list = []

    story.append(Paragraph("GitHub License Scanner", st["title"]))
    story.append(
        Paragraph(
            "Informe de auditoría técnica, de seguridad y cumplimiento normativo/legal",
            st["sub"],
        )
    )
    story.append(
        Paragraph(
            f"Fecha del informe: {now}<br/>"
            "Rol: Ingeniero de Software Senior + Abogado especialista en tecnología<br/>"
            "Alcance: arquitectura, APIs, flujos de datos, seguridad, escalabilidad, "
            "privacidad (GDPR/CCPA), propiedad intelectual y contratos",
            st["meta"],
        )
    )
    story.append(Spacer(1, 8 * mm))

    # 1 Executive summary
    story.append(Paragraph("1. Resumen ejecutivo", st["h1"]))
    story.append(
        Paragraph(
            "La aplicación es un escáner de licencias de repositorios GitHub (UI NiceGUI + CLI) "
            "que clasifica licencias de repositorio y dependencias, emite un veredicto heurístico "
            "sobre venta de software cerrado y sugiere plataformas de deploy. "
            "La auditoría identificó <b>fallos críticos de seguridad y riesgo legal material</b> "
            "(secreto de sesión hardcodeado, historial compartido sin aviso de privacidad suficiente, "
            "plantilla de copyright engañosa, veredictos binarios sobre-simplificados). "
            "Todos los puntos críticos listados en la sección 3 han sido <b>corregidos en código</b> "
            "en este mismo cambio, junto con documentación legal (disclaimer, privacy, terms).",
            st["body"],
        )
    )

    # 2 Architecture
    story.append(Paragraph("2. Arquitectura y flujos de datos", st["h1"]))
    story.append(Paragraph("2.1 Componentes", st["h2"]))
    story.append(
        bullets(
            [
                "<b>main.py</b> — UI NiceGUI (scan / batch / history), i18n ES/EN, export Markdown.",
                "<b>cli.py</b> — CLI con códigos de salida 0/1/2 para CI.",
                "<b>github_api.py</b> — parseo de URL, metadata y manifests vía api.github.com.",
                "<b>dependency_scanner.py</b> — parsers multi-ecosistema (npm, PyPI, Cargo, Go, …).",
                "<b>license_analyzer.py</b> — lookup de registros, clasificación, veredicto, score.",
                "<b>history_store.py</b> — persistencia JSON local con retención.",
                "<b>config.py / rate_limit.py</b> — configuración por entorno y anti-abuso (nuevo).",
            ],
            st,
        )
    )
    story.append(Paragraph("2.2 Flujo de datos", st["h2"]))
    story.append(
        Paragraph(
            "Usuario → URL GitHub → parse (owner/repo) → GitHub REST (repo + tree + contents) → "
            "parsers de manifests → registros (npm/PyPI/crates/…) → clasificación SPDX-heurística → "
            "veredicto / score / replacements / deploy → UI o CLI → opcional history.json. "
            "Preferencias de UI viven en cookie firmada (NiceGUI user storage).",
            st["body"],
        )
    )
    story.append(Paragraph("2.3 Puntos de fallo (pre-fix)", st["h2"]))
    story.append(
        bullets(
            [
                "Rate limit / 401 / 403 de GitHub sin token (mitigado: mensaje + exit 2 + incomplete).",
                "Descargas de manifests secuenciales (mitigado: concurrencia acotada).",
                "Caché de licencias sin TTL (mitigado: TTL + max entries).",
                "Escritura de history sin atomicidad / lock (mitigado: write atómico + lock de proceso).",
                "Batch ilimitado y sin rate limit (mitigado: caps + sliding window).",
                "Ecosistemas Go/Maven/Gradle sin lookup de licencia (riesgo residual: unknown).",
            ],
            st,
        )
    )

    # 3 Findings
    story.append(Paragraph("3. Hallazgos (antes del remediado)", st["h1"]))
    findings = [
        (
            "C-01",
            "CRÍTICO",
            "storage_secret hardcodeado en main.py: forja de cookies de sesión en deploys públicos.",
        ),
        (
            "C-02",
            "CRÍTICO",
            "Plantilla de copyright atribuía ownership al owner de GitHub (riesgo de uso engañoso / IP).",
        ),
        (
            "C-03",
            "ALTO",
            "Historial global en disco sin política de privacidad, borrado UX ni retención por edad.",
        ),
        (
            "C-04",
            "ALTO",
            "Sin rate limit ni cap de batch: abuso de GITHUB_TOKEN del servidor y DoS de API.",
        ),
        (
            "C-05",
            "ALTO",
            "Veredictos “can_sell_closed / forces_open” presentados de forma binaria sin matizar AGPL/SaaS, "
            "linking ni scan incompleto en el modelo de datos.",
        ),
        (
            "C-06",
            "MEDIO",
            "Bind por defecto y secreto de desarrollo sin .env.example; riesgo de exposición en LAN.",
        ),
        (
            "C-07",
            "MEDIO",
            "Gradle testImplementation no marcado como dev; falsos positivos de copyleft fuerte.",
        ),
        (
            "C-08",
            "MEDIO",
            "Ausencia de PRIVACY / TERMS / disclaimer extendido para despliegue multi-usuario (GDPR/CCPA).",
        ),
        (
            "C-09",
            "BAJO",
            "verify_app desalineado con compute_verdict de 6+ campos; tests frágiles.",
        ),
        (
            "C-10",
            "BAJO",
            "Clasificación de licencias por heurística (no SPDX expression engine completa).",
        ),
    ]
    story.append(severity_table(findings, st))
    story.append(Spacer(1, 4 * mm))

    # 4 Legal
    story.append(Paragraph("4. Análisis legal y de cumplimiento", st["h1"]))
    story.append(Paragraph("4.1 Propiedad intelectual y open source", st["h2"]))
    story.append(
        Paragraph(
            "El Tool clasifica licencias de terceros pero <b>no sustituye</b> un análisis de "
            "compatibilidad ni due diligence de IP. Especialmente: linking estático/dinámico (GPL), "
            "uso en red (AGPL §13, SSPL), dual licensing, permisos adicionales, CLA/DCO y NOTICE "
            "de Apache-2.0. La plantilla de copyright anterior era jurídicamente peligrosa porque "
            "sugería un titular de derechos sin verificación. Ahora es un template con disclaimer.",
            st["body"],
        )
    )
    story.append(Paragraph("4.2 Privacidad (GDPR / CCPA)", st["h2"]))
    story.append(
        Paragraph(
            "Datos típicos: URLs escaneadas, resultados compactos, preferencias de UI. No se piden "
            "PII sensibles, pero un deploy multi-usuario sin auth expone historial compartido "
            "(posible “dato personal” si el usuario se identifica por repos privados). "
            "Mitigaciones: política de privacidad, clear history (derecho de supresión local), "
            "retención por edad/máximo de entradas, truncado de verdict_summary en history, "
            "bind localhost por defecto. El operador del self-host es el responsable del tratamiento.",
            st["body"],
        )
    )
    story.append(Paragraph("4.3 Contratos y disclaimers", st["h2"]))
    story.append(
        Paragraph(
            "Se añadieron TERMS.md, LEGAL_DISCLAIMER.md y refuerzo del disclaimer en UI/export. "
            "Se aclara que no hay relación abogado-cliente ni garantía de no infracción. "
            "La licencia MIT del Tool no modifica las licencias de los repos escaneados.",
            st["body"],
        )
    )
    story.append(Paragraph("4.4 Uso aceptable y GitHub ToS", st["h2"]))
    story.append(
        Paragraph(
            "El usuario debe estar autorizado a acceder a los repos; el rate limit reduce riesgo de "
            "violación de límites de API. Solo se contacta api.github.com (sin hosts arbitrarios).",
            st["body"],
        )
    )

    # 5 Changes
    story.append(PageBreak())
    story.append(Paragraph("5. Cambios implementados en este remediado", st["h1"]))
    changes = [
        "<b>config.py</b> — configuración por entorno (host, port, secrets, límites, retención).",
        "<b>rate_limit.py</b> — sliding window por cliente para scans.",
        "<b>.env.example</b> — plantilla de secretos y límites (sin valores reales).",
        "<b>main.py</b> — storage_secret desde env; host 127.0.0.1; rate limit; cap batch; "
        "clear history; páginas /docs/privacy|terms|legal; veredicto incomplete vía scan_complete.",
        "<b>github_api.py</b> — validación owner/repo; rechazo de schemes raros; 429; "
        "descargas concurrentes; token desde config.",
        "<b>license_analyzer.py</b> — caché con TTL; notice template legal; AGPL/SSPL network flag; "
        "veredicto 7-tupla; scan_complete; EUPL/LGPL variants.",
        "<b>history_store.py</b> — write atómico, lock, prune por edad, no guardar incompletos.",
        "<b>models.py</b> — scan_complete, has_network_copyleft; history truncado.",
        "<b>dependency_scanner.py</b> — Gradle test*/compileOnly como is_dev.",
        "<b>report.py / cli.py / i18n.py / README</b> — disclaimers y UX de cumplimiento.",
        "<b>docs/PRIVACY.md, TERMS.md, LEGAL_DISCLAIMER.md</b> — base normativa.",
        "<b>scripts/verify_app.py</b> — tests alineados con nuevo veredicto y notice.",
    ]
    story.append(bullets(changes, st))

    story.append(Paragraph("5.1 Mapa hallazgo → fix", st["h2"]))
    map_rows = [
        ("C-01", "FIXED", "GLS_STORAGE_SECRET + warning/ephemeral en bind público"),
        ("C-02", "FIXED", "build_copyright_notice como TEMPLATE con warning de ownership"),
        ("C-03", "FIXED", "PRIVACY + clear history + max age + truncado"),
        ("C-04", "FIXED", "SlidingWindowRateLimiter + MAX_BATCH_URLS"),
        ("C-05", "FIXED", "scan_complete, network copyleft, lenguaje de veredicto matizado"),
        ("C-06", "FIXED", "Host default 127.0.0.1 + .env.example"),
        ("C-07", "FIXED", "Gradle is_dev para configs de test"),
        ("C-08", "FIXED", "docs legales + enlaces en UI"),
        ("C-09", "FIXED", "verify_app actualizado"),
        ("C-10", "OPEN", "Riesgo residual: seguir sin motor SPDX completo"),
    ]
    story.append(
        severity_table([(a, b, c) for a, b, c in map_rows], st)
    )

    # 6 Residual
    story.append(Paragraph("6. Riesgos residuales y mejoras futuras", st["h1"]))
    story.append(
        bullets(
            [
                "Sin autenticación multi-usuario ni historial por usuario (añadir auth + DB si SaaS).",
                "Sin reverse-proxy TLS / WAF (operador debe poner nginx/Caddy/Cloudflare).",
                "Lookups incompletos: Go, Maven Central, Gradle; lockfiles no resueltos del todo.",
                "No modela grafo de linking ni SBOM completo (CycloneDX/SPDX export sería ideal).",
                "Rate limit in-process no se comparte entre workers; usar Redis en multi-proceso.",
                "Clasificador de licencias sigue siendo heurístico (integrar package license-expression).",
                "Tests de integración dependen de red y de GitHub rate limits.",
            ],
            st,
        )
    )

    # 7 Scalability / security posture
    story.append(Paragraph("7. Postura de seguridad y escalabilidad", st["h1"]))
    story.append(
        Paragraph(
            "La arquitectura es <b>single-process / in-memory</b>, adecuada para uso local o "
            "equipo pequeño. Para escala: cola de trabajos, caché compartida, límites en edge, "
            "auth, y no compartir GITHUB_TOKEN de alta privilegio. SSRF está mitigado al fijar "
            "el host de API a GitHub y validar owner/repo. No se ejecuta código de repos de terceros "
            "(solo lectura de manifests de texto), lo cual es positivo desde un punto de vista de seguridad.",
            st["body"],
        )
    )

    # 8 Conclusion
    story.append(Paragraph("8. Conclusión", st["h1"]))
    story.append(
        Paragraph(
            "Tras el remediado, la aplicación presenta una postura sustancialmente más segura y "
            "jurídicamente defendible para uso local y auto-hospedado: secretos configurables, "
            "límites de abuso, historial con controles de privacidad, disclaimers y documentos "
            "normativos, y veredictos que no simulan ser dictámenes legales. "
            "El riesgo residual principal es la <b>sobreconfianza del usuario</b> en heurísticas "
            "automáticas y la incompleción de metadatos de algunos ecosistemas. "
            "Se recomienda mantener el disclaimer visible y no comercializar el output como "
            "asesoría legal sin revisión humana cualificada.",
            st["body"],
        )
    )
    story.append(Spacer(1, 10 * mm))
    story.append(
        Paragraph(
            "Documento generado automáticamente como parte del remediado de código. "
            "No constituye asesoramiento jurídico vinculante.",
            st["meta"],
        )
    )

    OUT.parent.mkdir(parents=True, exist_ok=True)
    doc = SimpleDocTemplate(
        str(OUT),
        pagesize=A4,
        leftMargin=1.8 * cm,
        rightMargin=1.8 * cm,
        topMargin=1.5 * cm,
        bottomMargin=1.5 * cm,
        title="GitHub License Scanner — Audit Report",
        author="GitHub License Scanner Audit",
    )
    doc.build(story)
    return OUT


if __name__ == "__main__":
    path = build()
    print(f"Wrote {path}")
