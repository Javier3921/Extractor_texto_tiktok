"""Generacion del archivo .txt por video (formato de la seccion 14 del prompt)."""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from src.models import LanguageInfo, Segment
from src.utils import format_timestamp, safe_output_path

SEP = "=" * 50


def _titled(title: str) -> str:
    return f"{SEP}\n{title}\n{'=' * len(title)}\n"


def _segment_lines(segments: list[Segment]) -> str:
    if not segments:
        return "(sin contenido)\n"
    out = []
    for s in segments:
        text = s.clean_text()
        if not text:
            continue
        out.append(f"[{format_timestamp(s.start)}] {text}")
    return "\n".join(out) + "\n"


def build_txt(*, url: str, video_id: str, language: LanguageInfo,
              duration: float, translated: bool,
              original_segments: list[Segment],
              spanish_segments: list[Segment],
              processed_at: datetime | None = None) -> str:
    processed_at = processed_at or datetime.now()

    lines = [
        _titled("INFORMACION DEL VIDEO"),
        f"URL:                     {url or '(no aplica - archivo local)'}",
        f"FECHA DE PROCESAMIENTO:  {processed_at:%Y-%m-%d %H:%M:%S}",
        f"IDIOMA ORIGINAL:         {language.name} ({language.code})",
        f"IDIOMA DEL REPORTE:      Espanol",
        f"TRADUCCION REALIZADA:    {'Si' if translated else 'No'}",
        f"DURACION:                {format_timestamp(duration)}",
        f"ID DEL VIDEO:            {video_id}",
        "",
    ]

    if translated:
        lines.append(_titled("TRANSCRIPCION ORIGINAL"))
        lines.append(_segment_lines(original_segments))
        lines.append("")
        lines.append(_titled("TRANSCRIPCION EN ESPANOL"))
        lines.append(_segment_lines(spanish_segments))
    else:
        lines.append(_titled("TRANSCRIPCION EN ESPANOL"))
        lines.append(_segment_lines(spanish_segments))

    return "\n".join(lines).rstrip() + "\n"


def write_txt(content: str, txt_dir: Path, video_id: str) -> Path:
    filename = f"tiktok_{video_id}.txt" if video_id and video_id.isdigit() \
        else f"{video_id or 'video'}.txt"
    path = safe_output_path(txt_dir, filename)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(content, encoding="utf-8")
    return path
