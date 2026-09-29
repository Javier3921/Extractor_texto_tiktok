"""Generacion del informe tecnico en Markdown, pensado para que otra IA (o un
humano) lo lea con facilidad: metadatos en un bloque YAML (front matter) y
secciones con encabezados estables, sin estilos ni graficos.

Mismo contenido y mismas secciones A-L que el HTML (`html_generator.py`).

El contenido viene en ultima instancia de la transcripcion de un video de un
tercero, asi que se neutraliza lo que podria alterar la ESTRUCTURA del
documento (falsos encabezados, cierre del front matter, celdas de tabla) o
colarse como HTML crudo en un visor Markdown: los valores del front matter
se serializan como cadenas JSON (validas en YAML) y el texto pasa por `_md()`.
"""
from __future__ import annotations

import json
import re
from datetime import datetime
from pathlib import Path
from typing import Iterable

from src.models import AnalysisReport
from src.utils import get_logger, safe_output_path

log = get_logger()

_NO_INFO = "_No se identificó información suficiente._"
# Lineas que Markdown interpretaria como estructura (encabezado, cita, regla
# horizontal/subrayado de encabezado setext) si llegan al inicio de linea.
_BLOCK_START = re.compile(r"^(\s*)(#|>|-{3,}\s*$|={3,}\s*$|\*{3,}\s*$)")


def _md(text) -> str:
    """Texto seguro para insertar como parrafo Markdown."""
    text = str(text if text is not None else "").replace("<", "&lt;")
    return "\n".join(_BLOCK_START.sub(r"\1\\\2", line) for line in text.splitlines())


def _inline(text) -> str:
    """Texto en una sola linea (items de lista, celdas de tabla)."""
    return _md(" ".join(str(text if text is not None else "").split()))


def _yaml(value) -> str:
    return json.dumps(value, ensure_ascii=False)


def _paragraph(text: str) -> str:
    text = (text or "").strip()
    if not text:
        return _NO_INFO
    return "\n\n".join(_md(line.strip()) for line in text.splitlines() if line.strip())


def _list(items: Iterable) -> str:
    clean = [str(x).strip() for x in (items or []) if str(x).strip()]
    if not clean:
        return _NO_INFO
    return "\n".join(f"- {_inline(x)}" for x in clean)


def _cell(text: str) -> str:
    return _inline(text).replace("|", "\\|")


def _tech_section(technologies) -> str:
    rows: list[tuple[str, str]] = []
    plain: list[str] = []
    for t in (technologies or []):
        if isinstance(t, dict):
            cat = str(t.get("category") or t.get("categoria") or "otro").strip() or "otro"
            name = str(t.get("name") or t.get("nombre") or "").strip()
            if name:
                rows.append((cat.capitalize(), name))
        elif str(t).strip():
            plain.append(str(t).strip())

    if not rows:
        if plain:
            return _list(plain)
        return "_No se identificaron tecnologías de forma explícita._"

    lines = ["| Categoría | Elemento |", "| --- | --- |"]
    lines += [f"| {_cell(cat)} | {_cell(name)} |" for cat, name in rows]
    return "\n".join(lines)


def build_markdown(report: AnalysisReport, *, md_dir: Path, video_id: str,
                   url: str, original_language: str, translated: bool,
                   provider: str, ai_model: str, duration_str: str,
                   processed_at: datetime | None = None) -> Path:
    processed_at = processed_at or datetime.now()

    filename = (f"reporte_tiktok_{video_id}.md" if video_id and video_id.isdigit()
                else f"reporte_{video_id or 'video'}.md")
    out_path = safe_output_path(md_dir, filename)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    title = report.title or "Informe tecnico del video"
    front_matter = [
        "---",
        "tipo: informe_tecnico_video",
        f"titulo: {_yaml(title)}",
        f"origen: {_yaml(url or 'Archivo de video local')}",
        f"video_id: {_yaml(video_id)}",
        f"fecha_procesamiento: {_yaml(f'{processed_at:%Y-%m-%d %H:%M:%S}')}",
        f"idioma_original: {_yaml(original_language)}",
        f"traducido_al_espanol: {'true' if translated else 'false'}",
        f"duracion: {_yaml(duration_str)}",
        f"proveedor_ia: {_yaml(provider)}",
        f"modelo_ia: {_yaml(ai_model)}",
        f"dificultad: {_yaml(report.difficulty or 'No determinado')}",
        "generador: Extractor_texto_tiktok",
        "---",
    ]

    sections = [
        ("A", "Resumen ejecutivo", _paragraph(report.executive_summary)),
        ("B", "Explicación detallada", _paragraph(report.detailed_explanation)),
        ("C", "Tecnologías utilizadas", _tech_section(report.technologies)),
        ("D", "Conceptos técnicos", _list(report.technical_concepts)),
        ("E", "Arquitectura", _paragraph(report.architecture)),
        ("F", "Análisis de código", _paragraph(report.code_analysis)),
        ("G", "Buenas prácticas", _list(report.best_practices)),
        ("H", "Riesgos", _list(report.risks)),
        ("I", "Recomendaciones", _list(report.recommendations)),
        ("J", "Nivel de dificultad", _paragraph(report.difficulty or "No determinado")),
        ("K", "Aplicaciones", _list(report.applications)),
        ("L", "Conclusión", _paragraph(report.conclusion)),
    ]

    parts = ["\n".join(front_matter), "", f"# {_inline(title)}", ""]
    if report.parse_warning:
        parts += [f"> **Nota:** {_inline(report.parse_warning)}", ""]
    for letter, name, body in sections:
        parts += [f"## {letter}. {name}", "", body, ""]
    parts.append("---\n\n_Documento generado automáticamente por Extractor_texto_tiktok._\n")

    out_path.write_text("\n".join(parts), encoding="utf-8")
    log.info("Markdown generado: %s", out_path)
    return out_path
