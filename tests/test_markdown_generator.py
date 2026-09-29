from src.ai_analyzer import _coerce_report
from src.markdown_generator import build_markdown
from src.models import AnalysisReport


def _build(report, tmp_path, video_id="x", **kw):
    args = dict(md_dir=tmp_path, video_id=video_id, url="", original_language="es",
                translated=False, provider="mock", ai_model="mock-1", duration_str="00:10")
    args.update(kw)
    return build_markdown(report, **args)


class TestBuildMarkdown:
    def test_generates_front_matter_and_sections(self, tmp_path, sample_report_dict):
        report = _coerce_report(sample_report_dict, "English", True, "Titulo")
        out = _build(report, tmp_path, video_id="7300000000000000123",
                     url="https://www.tiktok.com/@u/video/7300000000000000123",
                     original_language="English", translated=True)
        assert out.name == "reporte_tiktok_7300000000000000123.md"
        text = out.read_text(encoding="utf-8")
        assert text.startswith("---\ntipo: informe_tecnico_video\n")
        assert 'titulo: "Construir una REST API con Node.js"' in text
        assert "traducido_al_espanol: true" in text
        assert "# Construir una REST API con Node.js" in text
        for heading in ("## A. Resumen ejecutivo", "## C. Tecnologías utilizadas",
                        "## L. Conclusión"):
            assert heading in text
        assert "| Framework | Express |" in text
        assert "- REST" in text

    def test_untrusted_content_cannot_alter_structure(self, tmp_path):
        """El texto viene de un video de un tercero: no debe poder cerrar el
        front matter, fabricar encabezados, romper la tabla ni colar HTML."""
        report = AnalysisReport(
            title='Titulo"\nfalso: true',
            executive_summary="linea normal\n# Encabezado falso\n---\n<script>x()</script>",
            technologies=[{"category": "a|b", "name": "c\nd"}],
        )
        text = _build(report, tmp_path).read_text(encoding="utf-8")
        front = text.split("\n---\n", 1)[0]
        assert "\nfalso: true" not in front          # el titulo quedo como cadena JSON
        assert "\n# Encabezado falso" not in text
        assert "\\# Encabezado falso" in text
        assert "\n\\---" in text
        assert "<script>" not in text and "&lt;script>" in text
        assert "| A\\|b | c d |" in text

    def test_empty_report_still_produces_markdown(self, tmp_path):
        text = _build(AnalysisReport(), tmp_path).read_text(encoding="utf-8")
        assert "## A. Resumen ejecutivo" in text
        assert "No se identificó información suficiente" in text

    def test_parse_warning_shown_as_note(self, tmp_path):
        text = _build(AnalysisReport(parse_warning="algo fallo"), tmp_path).read_text(
            encoding="utf-8")
        assert "> **Nota:** algo fallo" in text
