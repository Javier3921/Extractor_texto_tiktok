"""Generacion del informe tecnico en PDF (ReportLab / Platypus).

- Portada + secciones A-L (seccion 17 del prompt).
- Numeracion "Pagina X de Y", encabezado en paginas interiores.
- Fuente Unicode (Arial de Windows; si no, Helvetica) para acentos, n~, ¿ ¡ ü.
- Todo el texto en espanol.
"""
from __future__ import annotations

from datetime import datetime
from pathlib import Path

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont
from reportlab.pdfgen import canvas as _canvas
from reportlab.platypus import (BaseDocTemplate, Frame, ListFlowable, ListItem,
                                NextPageTemplate, PageBreak, PageTemplate,
                                Paragraph, Spacer, Table, TableStyle)

from src.models import AnalysisReport
from src.utils import get_logger, safe_output_path

log = get_logger()

FONT_NORMAL = "Helvetica"
FONT_BOLD = "Helvetica-Bold"
FONT_ITALIC = "Helvetica-Oblique"

_PRIMARY = colors.HexColor("#1F3A5F")
_ACCENT = colors.HexColor("#2E7D9E")
_LIGHT = colors.HexColor("#EEF3F7")
_GREY = colors.HexColor("#555555")

_FONTS_READY = False


def _register_fonts() -> None:
    """Registra Arial (Windows) para cobertura Unicode completa; si no, Helvetica."""
    global FONT_NORMAL, FONT_BOLD, FONT_ITALIC, _FONTS_READY
    if _FONTS_READY:
        return
    _FONTS_READY = True
    win = Path(r"C:\Windows\Fonts")
    try:
        if (win / "arial.ttf").exists():
            pdfmetrics.registerFont(TTFont("ArialU", str(win / "arial.ttf")))
            FONT_NORMAL = "ArialU"
            if (win / "arialbd.ttf").exists():
                pdfmetrics.registerFont(TTFont("ArialU-Bold", str(win / "arialbd.ttf")))
                FONT_BOLD = "ArialU-Bold"
            else:
                FONT_BOLD = "ArialU"
            if (win / "ariali.ttf").exists():
                pdfmetrics.registerFont(TTFont("ArialU-Italic", str(win / "ariali.ttf")))
                FONT_ITALIC = "ArialU-Italic"
            else:
                FONT_ITALIC = "ArialU"
            try:
                pdfmetrics.registerFontFamily(
                    "ArialU", normal="ArialU", bold=FONT_BOLD,
                    italic=FONT_ITALIC, boldItalic=FONT_BOLD)
            except Exception:
                pass
    except Exception as e:  # noqa: BLE001
        log.info("No se pudo registrar Arial; se usa Helvetica base-14: %s", e)


class NumberedCanvas(_canvas.Canvas):
    """Recipe estandar: bufferiza paginas para escribir 'Pagina X de Y'."""

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._saved: list[dict] = []

    def showPage(self):  # noqa: N802
        self._saved.append(dict(self.__dict__))
        self._startPage()

    def save(self):
        total = len(self._saved)
        for idx, state in enumerate(self._saved, start=1):
            self.__dict__.update(state)
            if idx > 1:  # la portada no lleva pie
                self._draw_footer(idx, total)
            super().showPage()
        super().save()

    def _draw_footer(self, page_idx: int, total: int) -> None:
        self.saveState()
        self.setFont(FONT_ITALIC, 8)
        self.setFillColor(_GREY)
        self.drawRightString(A4[0] - 2.2 * cm, 1.0 * cm,
                             f"Pagina {page_idx} de {total}")
        self.restoreState()


class _DocTemplate(BaseDocTemplate):
    def __init__(self, filename, header_title="", **kw):
        super().__init__(filename, **kw)
        self.header_title = header_title
        frame = Frame(self.leftMargin, self.bottomMargin, self.width, self.height,
                      id="main")
        self.addPageTemplates([
            PageTemplate(id="cover", frames=[frame], onPage=self._on_cover),
            PageTemplate(id="content", frames=[frame], onPage=self._on_content),
        ])

    def _on_cover(self, canvas, doc):
        canvas.saveState()
        canvas.setFillColor(_PRIMARY)
        canvas.rect(0, A4[1] - 4 * cm, A4[0], 4 * cm, fill=1, stroke=0)
        canvas.setFillColor(_ACCENT)
        canvas.rect(0, A4[1] - 4.15 * cm, A4[0], 0.15 * cm, fill=1, stroke=0)
        canvas.restoreState()

    def _on_content(self, canvas, doc):
        canvas.saveState()
        canvas.setFont(FONT_ITALIC, 8)
        canvas.setFillColor(_GREY)
        canvas.drawString(self.leftMargin, A4[1] - 1.1 * cm, self.header_title[:110])
        canvas.setStrokeColor(_LIGHT)
        canvas.line(self.leftMargin, A4[1] - 1.25 * cm,
                    A4[0] - self.rightMargin, A4[1] - 1.25 * cm)
        canvas.restoreState()


def _styles() -> dict[str, ParagraphStyle]:
    base = getSampleStyleSheet()
    s: dict[str, ParagraphStyle] = {}
    s["cover_title"] = ParagraphStyle(
        "cover_title", parent=base["Title"], fontName=FONT_BOLD, fontSize=26,
        textColor=colors.white, alignment=TA_CENTER, leading=32)
    s["cover_sub"] = ParagraphStyle(
        "cover_sub", fontName=FONT_NORMAL, fontSize=13, textColor=_PRIMARY,
        alignment=TA_CENTER, leading=18)
    s["cover_meta"] = ParagraphStyle(
        "cover_meta", fontName=FONT_NORMAL, fontSize=10.5, textColor=_GREY,
        alignment=TA_CENTER, leading=16)
    s["h1"] = ParagraphStyle(
        "h1", fontName=FONT_BOLD, fontSize=15, textColor=_PRIMARY, spaceBefore=18,
        spaceAfter=8, leading=19)
    s["body"] = ParagraphStyle(
        "body", fontName=FONT_NORMAL, fontSize=10.5, leading=15,
        alignment=TA_JUSTIFY, spaceAfter=6)
    s["bullet"] = ParagraphStyle(
        "bullet", parent=s["body"], leftIndent=6, spaceAfter=3)
    s["callout"] = ParagraphStyle(
        "callout", fontName=FONT_BOLD, fontSize=11, textColor=_PRIMARY,
        backColor=_LIGHT, borderPadding=8, leading=15, spaceBefore=6, spaceAfter=6)
    return s


def _p(text, style) -> Paragraph:
    safe = (str(text if text is not None else "")
            .replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            .replace("\n", "<br/>"))
    return Paragraph(safe or "&nbsp;", style)


def _bullets(items, style):
    clean = [str(x).strip() for x in (items or []) if str(x).strip()]
    if not clean:
        return _p("No se identifico informacion suficiente.", style)
    return ListFlowable(
        [ListItem(_p(x, style), leftIndent=12, value="\u2022") for x in clean],
        bulletType="bullet", start="\u2022", leftIndent=12,
    )


def _tech_table(technologies, styles):
    rows = [["Categoria", "Elemento"]]
    plain: list[str] = []
    for t in (technologies or []):
        if isinstance(t, dict):
            cat = str(t.get("category") or t.get("categoria") or "otro").strip()
            name = str(t.get("name") or t.get("nombre") or "").strip()
            if name:
                rows.append([cat.capitalize(), name])
        elif str(t).strip():
            plain.append(str(t).strip())
    if len(rows) > 1:
        tbl = Table(rows, colWidths=[4.5 * cm, 11.3 * cm], repeatRows=1)
        tbl.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), _PRIMARY),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), FONT_BOLD),
            ("FONTNAME", (0, 1), (-1, -1), FONT_NORMAL),
            ("FONTSIZE", (0, 0), (-1, -1), 9.5),
            ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, _LIGHT]),
            ("GRID", (0, 0), (-1, -1), 0.4, colors.HexColor("#C9D6E0")),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        return tbl
    if plain:
        return _bullets(plain, styles["bullet"])
    return _p("No se identificaron tecnologias de forma explicita.", styles["body"])


def build_pdf(report: AnalysisReport, *, pdf_dir: Path, video_id: str,
              url: str, original_language: str, translated: bool,
              provider: str, ai_model: str, duration_str: str,
              processed_at: datetime | None = None) -> Path:
    _register_fonts()
    styles = _styles()
    processed_at = processed_at or datetime.now()

    filename = (f"reporte_tiktok_{video_id}.pdf" if video_id and video_id.isdigit()
                else f"reporte_{video_id or 'video'}.pdf")
    out_path = safe_output_path(pdf_dir, filename)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    story: list = []
    story.append(Spacer(1, 1.1 * cm))
    story.append(_p("INFORME TECNICO DE VIDEO", styles["cover_title"]))
    story.append(Spacer(1, 1.6 * cm))
    story.append(_p(report.title or "Analisis de contenido tecnico", styles["cover_sub"]))
    story.append(Spacer(1, 1.2 * cm))
    for m in [
        f"URL / Origen: {url or 'Archivo de video local'}",
        f"Fecha de procesamiento: {processed_at:%Y-%m-%d %H:%M:%S}",
        f"Idioma original: {original_language}",
        f"Traduccion al espanol: {'Si' if translated else 'No (el original ya estaba en espanol)'}",
        f"Duracion del video: {duration_str}",
        f"Proveedor de IA: {provider}  |  Modelo: {ai_model}",
        f"Nivel de dificultad: {report.difficulty or 'No determinado'}",
    ]:
        story.append(_p(m, styles["cover_meta"]))
    story.append(Spacer(1, 2.4 * cm))
    story.append(_p("Documento generado automaticamente por Extractor_texto_tiktok.",
                    styles["cover_meta"]))
    if report.parse_warning:
        story.append(Spacer(1, 0.5 * cm))
        story.append(_p("Nota: " + report.parse_warning, styles["cover_meta"]))

    story.append(NextPageTemplate("content"))
    story.append(PageBreak())

    def section(title, flowables):
        story.append(_p(title, styles["h1"]))
        story.extend(flowables)

    section("A. Resumen ejecutivo", [_p(report.executive_summary, styles["body"])])
    section("B. Explicacion detallada", [_p(report.detailed_explanation, styles["body"])])
    section("C. Tecnologias utilizadas", [_tech_table(report.technologies, styles)])
    section("D. Conceptos tecnicos", [_bullets(report.technical_concepts, styles["bullet"])])
    section("E. Arquitectura", [_p(report.architecture, styles["body"])])
    section("F. Analisis de codigo", [_p(report.code_analysis, styles["body"])])
    section("G. Buenas practicas", [_bullets(report.best_practices, styles["bullet"])])
    section("H. Riesgos", [_bullets(report.risks, styles["bullet"])])
    section("I. Recomendaciones", [_bullets(report.recommendations, styles["bullet"])])
    section("J. Nivel de dificultad",
            [_p(report.difficulty or "No determinado", styles["callout"])])
    section("K. Aplicaciones", [_bullets(report.applications, styles["bullet"])])
    section("L. Conclusion", [_p(report.conclusion, styles["body"])])

    doc = _DocTemplate(
        str(out_path), header_title=report.title or "Informe tecnico",
        pagesize=A4, leftMargin=2.2 * cm, rightMargin=2.2 * cm,
        topMargin=2.0 * cm, bottomMargin=1.8 * cm,
        title=f"Informe tecnico - {(report.title or '')[:80]}",
        author="Extractor_texto_tiktok",
    )
    doc.build(story, canvasmaker=NumberedCanvas)
    log.info("PDF generado: %s", out_path)
    return out_path
