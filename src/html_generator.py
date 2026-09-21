"""Generacion del informe tecnico en HTML: un unico archivo autonomo
(CSS inline, sin JavaScript, sin peticiones externas) mas ligero que un PDF
y que permite graficos/diagramas reales (SVG) en vez de solo texto y tablas.

Todo el contenido que viene del analisis de IA (y en ultima instancia de la
transcripcion de un video de un tercero) se escapa con `html.escape()` antes
de insertarse: no hay <script> en la plantilla, asi que no hay forma de que
ese contenido se ejecute como codigo en el navegador.
"""
from __future__ import annotations

import html as html_lib
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Iterable

from src.models import AnalysisReport
from src.utils import get_logger, safe_output_path

log = get_logger()

_DIFFICULTY_LEVELS = ["Basico", "Intermedio", "Avanzado", "Experto"]
_DIFFICULTY_COLORS = {
    "Basico": "#2e7d32", "Intermedio": "#2E7D9E",
    "Avanzado": "#e08a1e", "Experto": "#b23b3b",
}


def _esc(text) -> str:
    return html_lib.escape(str(text if text is not None else ""), quote=True)


def _paragraph(text: str) -> str:
    text = (text or "").strip()
    if not text:
        return '<p class="muted">No se identifico informacion suficiente.</p>'
    return f"<p>{_esc(text).replace(chr(10), '<br>')}</p>"


def _list(items: Iterable) -> str:
    clean = [str(x).strip() for x in (items or []) if str(x).strip()]
    if not clean:
        return '<p class="muted">No se identifico informacion suficiente.</p>'
    return "<ul>" + "".join(f"<li>{_esc(x)}</li>" for x in clean) + "</ul>"


def _bar_chart(counts: "Counter[str]") -> str:
    """Grafico de barras horizontal en SVG (sin dependencias externas)."""
    if len(counts) < 2:
        return ""
    ordered = sorted(counts.items(), key=lambda kv: -kv[1])
    max_count = max(c for _, c in ordered)
    row_h, bar_max, left = 26, 260, 140
    height = row_h * len(ordered) + 8
    width = left + bar_max + 50
    bars = []
    for i, (label, count) in enumerate(ordered):
        y = i * row_h
        w = max(6, round(bar_max * count / max_count))
        bars.append(
            f'<text x="0" y="{y + row_h - 9}" class="chart-label">{_esc(label)}</text>'
            f'<rect x="{left}" y="{y + 3}" width="{w}" height="15" rx="3" class="chart-bar" />'
            f'<text x="{left + w + 6}" y="{y + row_h - 9}" class="chart-value">{count}</text>'
        )
    svg = (
        f'<svg viewBox="0 0 {width} {height}" class="chart" role="img" '
        f'aria-label="Tecnologias por categoria">{"".join(bars)}</svg>'
    )
    return f'<div class="chart-wrap">{svg}</div>'


def _tech_section(technologies) -> str:
    rows: list[tuple[str, str]] = []
    plain: list[str] = []
    categories: Counter[str] = Counter()
    for t in (technologies or []):
        if isinstance(t, dict):
            cat = str(t.get("category") or t.get("categoria") or "otro").strip() or "otro"
            name = str(t.get("name") or t.get("nombre") or "").strip()
            if name:
                rows.append((cat.capitalize(), name))
                categories[cat.capitalize()] += 1
        elif str(t).strip():
            plain.append(str(t).strip())

    if not rows:
        if plain:
            return _list(plain)
        return '<p class="muted">No se identificaron tecnologias de forma explicita.</p>'

    table_rows = "".join(
        f"<tr><td>{_esc(cat)}</td><td>{_esc(name)}</td></tr>" for cat, name in rows
    )
    table = (
        '<table class="tech-table"><thead><tr><th>Categoria</th><th>Elemento</th></tr>'
        f"</thead><tbody>{table_rows}</tbody></table>"
    )
    return _bar_chart(categories) + table


def _difficulty_block(level: str) -> str:
    norm = (level or "").strip()
    color = _DIFFICULTY_COLORS.get(norm, "#555555")
    steps = "".join(
        f'<span class="diff-step{" active" if d == norm else ""}" '
        f'style="--c:{_DIFFICULTY_COLORS.get(d, "#555555")}">{_esc(d)}</span>'
        for d in _DIFFICULTY_LEVELS
    )
    label = _esc(norm or "No determinado")
    return (
        f'<div class="diff-badge" style="--c:{color}">{label}</div>'
        f'<div class="diff-steps">{steps}</div>'
    )


_CSS = """
:root{--primary:#1F3A5F;--accent:#2E7D9E;--light:#EEF3F7;--grey:#555;--border:#C9D6E0;}
*{box-sizing:border-box;}
body{margin:0;font-family:-apple-system,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
  color:#1a1a1a;background:#f4f6fa;line-height:1.6;}
.hero{background:linear-gradient(135deg,var(--primary),var(--accent));color:#fff;
  padding:2.4rem 1.5rem 2rem;text-align:center;}
.hero .eyebrow{letter-spacing:2px;font-size:.78rem;opacity:.85;margin:0 0 .5rem;}
.hero h1{margin:0 0 1.1rem;font-size:1.7rem;line-height:1.3;}
.meta-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(220px,1fr));
  gap:.45rem 1.5rem;max-width:900px;margin:0 auto;text-align:left;
  background:rgba(255,255,255,.14);border-radius:10px;padding:1rem 1.2rem;}
.meta-row{display:flex;justify-content:space-between;gap:.6rem;font-size:.84rem;}
.meta-k{opacity:.82;}
.meta-v{font-weight:600;text-align:right;}
.warning{max-width:900px;margin:1rem auto 0;background:#fff3cd;color:#664d03;
  border:1px solid #ffe69c;border-radius:8px;padding:.8rem 1rem;font-size:.88rem;}
main{max-width:900px;margin:1.5rem auto 3rem;padding:0 1rem;display:grid;gap:1rem;}
.card{background:#fff;border:1px solid var(--border);border-radius:10px;
  padding:1.15rem 1.35rem;box-shadow:0 1px 3px rgba(0,0,0,.05);}
.card h2{margin:0 0 .7rem;font-size:1.02rem;color:var(--primary);
  display:flex;gap:.55rem;align-items:center;}
.letter{display:inline-flex;align-items:center;justify-content:center;flex:none;
  width:1.55rem;height:1.55rem;border-radius:50%;background:var(--light);
  color:var(--accent);font-size:.82rem;font-weight:700;}
.card p{margin:0 0 .6rem;font-size:.93rem;}
.card p:last-child{margin-bottom:0;}
.muted{color:var(--grey);font-style:italic;}
ul{margin:0;padding-left:1.25rem;}
li{margin-bottom:.35rem;font-size:.93rem;}
.tech-table{width:100%;border-collapse:collapse;font-size:.88rem;margin-top:.6rem;}
.tech-table th,.tech-table td{border:1px solid var(--border);padding:.4rem .6rem;text-align:left;}
.tech-table th{background:var(--primary);color:#fff;}
.tech-table tr:nth-child(even) td{background:var(--light);}
.chart-wrap{margin-bottom:.6rem;overflow-x:auto;}
.chart{width:100%;height:auto;min-width:320px;}
.chart-bar{fill:var(--accent);}
.chart-label{font-size:11px;fill:#1a1a1a;}
.chart-value{font-size:11px;fill:var(--grey);}
.diff-badge{display:inline-block;padding:.32rem .85rem;border-radius:999px;color:#fff;
  background:var(--c);font-weight:700;font-size:.88rem;margin-bottom:.6rem;}
.diff-steps{display:flex;gap:.4rem;flex-wrap:wrap;}
.diff-step{flex:1 1 80px;text-align:center;padding:.32rem .3rem;border-radius:6px;
  font-size:.76rem;background:var(--light);color:var(--grey);}
.diff-step.active{background:var(--c);color:#fff;font-weight:700;}
footer{text-align:center;color:var(--grey);font-size:.78rem;padding:1rem 0 2rem;}
@media print{
  body{background:#fff;}
  .hero{-webkit-print-color-adjust:exact;print-color-adjust:exact;}
  .card{box-shadow:none;border-color:#ddd;break-inside:avoid;}
  main{max-width:100%;}
}
"""


def build_html(report: AnalysisReport, *, html_dir: Path, video_id: str,
               url: str, original_language: str, translated: bool,
               provider: str, ai_model: str, duration_str: str,
               processed_at: datetime | None = None) -> Path:
    processed_at = processed_at or datetime.now()

    filename = (f"reporte_tiktok_{video_id}.html" if video_id and video_id.isdigit()
                else f"reporte_{video_id or 'video'}.html")
    out_path = safe_output_path(html_dir, filename)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    meta_pairs = [
        ("URL / Origen", url or "Archivo de video local"),
        ("Fecha de procesamiento", f"{processed_at:%Y-%m-%d %H:%M:%S}"),
        ("Idioma original", original_language),
        ("Traduccion al espanol",
         "Si" if translated else "No (el original ya estaba en espanol)"),
        ("Duracion del video", duration_str),
        ("Proveedor de IA", f"{provider} ({ai_model})"),
    ]
    meta_html = "".join(
        f'<div class="meta-row"><span class="meta-k">{_esc(k)}</span>'
        f'<span class="meta-v">{_esc(v)}</span></div>'
        for k, v in meta_pairs
    )
    warning_html = (
        f'<div class="warning">Nota: {_esc(report.parse_warning)}</div>'
        if report.parse_warning else ""
    )

    sections = [
        ("A", "Resumen ejecutivo", _paragraph(report.executive_summary)),
        ("B", "Explicacion detallada", _paragraph(report.detailed_explanation)),
        ("C", "Tecnologias utilizadas", _tech_section(report.technologies)),
        ("D", "Conceptos tecnicos", _list(report.technical_concepts)),
        ("E", "Arquitectura", _paragraph(report.architecture)),
        ("F", "Analisis de codigo", _paragraph(report.code_analysis)),
        ("G", "Buenas practicas", _list(report.best_practices)),
        ("H", "Riesgos", _list(report.risks)),
        ("I", "Recomendaciones", _list(report.recommendations)),
        ("J", "Nivel de dificultad", _difficulty_block(report.difficulty)),
        ("K", "Aplicaciones", _list(report.applications)),
        ("L", "Conclusion", _paragraph(report.conclusion)),
    ]
    sections_html = "".join(
        f'<section class="card"><h2><span class="letter">{letter}</span> '
        f"{_esc(name)}</h2>{body}</section>"
        for letter, name, body in sections
    )

    title = report.title or "Informe tecnico del video"
    doc = (
        '<!DOCTYPE html><html lang="es"><head><meta charset="UTF-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1.0">'
        f"<title>{_esc(title)}</title><style>{_CSS}</style></head><body>"
        '<header class="hero"><p class="eyebrow">INFORME TECNICO DE VIDEO</p>'
        f"<h1>{_esc(title)}</h1>"
        f'<div class="meta-grid">{meta_html}</div></header>'
        f"{warning_html}"
        f"<main>{sections_html}</main>"
        "<footer><p>Documento generado automaticamente por "
        "Extractor_texto_tiktok.</p></footer></body></html>"
    )
    out_path.write_text(doc, encoding="utf-8")
    log.info("HTML generado: %s", out_path)
    return out_path
