from src.ai_analyzer import _coerce_report
from src.html_generator import build_html
from src.models import AnalysisReport


class TestBuildHtml:
    def test_generates_valid_html(self, tmp_path, sample_report_dict):
        report = _coerce_report(sample_report_dict, "English", True, "Titulo")
        out = build_html(
            report, html_dir=tmp_path, video_id="7300000000000000123",
            url="https://www.tiktok.com/@u/video/7300000000000000123",
            original_language="English", translated=True, provider="mock",
            ai_model="mock-1", duration_str="00:30",
        )
        assert out.exists()
        assert out.name == "reporte_tiktok_7300000000000000123.html"
        text = out.read_text(encoding="utf-8")
        assert text.startswith("<!DOCTYPE html>")
        assert "<html lang=\"es\">" in text
        assert "Construir una REST API con Node.js" in text

    def test_escapes_html_in_ai_content(self, tmp_path):
        """El contenido viene en ultima instancia de un video de un tercero:
        si intenta inyectar markup/JS, debe quedar escapado, no ejecutable."""
        report = AnalysisReport(
            title="<script>alert(1)</script>",
            executive_summary="<img src=x onerror=alert(1)>",
            technologies=[{"category": "<b>x</b>", "name": "<script>evil()</script>"}],
        )
        out = build_html(
            report, html_dir=tmp_path, video_id="x", url="",
            original_language="es", translated=False, provider="mock",
            ai_model="m", duration_str="00:00",
        )
        text = out.read_text(encoding="utf-8")
        assert "<script>" not in text
        assert "<img" not in text  # la etiqueta viva no debe existir sin escapar
        assert "&lt;script&gt;" in text
        assert "&lt;img" in text  # pero el texto (inofensivo) si debe verse, escapado

    def test_handles_accents_and_special_chars(self, tmp_path):
        report = AnalysisReport(
            title="Análisis técnico: ¿cómo funciona la señal?",
            executive_summary="Configuración con ñ, á, é, í, ó, ú, ü y signos ¿ ¡.",
            detailed_explanation="Programación en Python. Diseño de la API. Versión 2.",
            architecture="Cliente → Servidor → Base de datos.",
            code_analysis="La función devuelve un número.",
            difficulty="Intermedio",
            conclusion="mezcla de escritura y acentos. Está todo correcto.",
            technologies=[{"category": "lenguaje", "name": "Python"}],
            best_practices=["Usar entornos virtuales"],
            risks=["Inyección SQL si no se sanea la entrada"],
            recommendations=["Añadir tests"],
            technical_concepts=["REST", "JSON"],
            applications=["Backends web"],
        )
        out = build_html(
            report, html_dir=tmp_path, video_id="local_demo",
            url="", original_language="Español", translated=False,
            provider="mock", ai_model="mock-1", duration_str="01:02",
        )
        text = out.read_text(encoding="utf-8")
        assert "Análisis técnico" in text
        assert "señal" in text

    def test_empty_report_still_produces_html(self, tmp_path):
        out = build_html(
            AnalysisReport(), html_dir=tmp_path, video_id="x",
            url="", original_language="Desconocido", translated=False,
            provider="mock", ai_model="mock-1", duration_str="00:00",
        )
        assert out.exists()
        assert out.read_text(encoding="utf-8").startswith("<!DOCTYPE html>")

    def test_plain_string_technologies(self, tmp_path):
        rep = AnalysisReport(title="T", technologies=["Python", "Docker"])
        out = build_html(
            rep, html_dir=tmp_path, video_id="y", url="", original_language="es",
            translated=False, provider="mock", ai_model="m", duration_str="00:10",
        )
        text = out.read_text(encoding="utf-8")
        assert "Python" in text and "Docker" in text

    def test_multiple_tech_categories_render_bar_chart(self, tmp_path):
        rep = AnalysisReport(
            title="T",
            technologies=[
                {"category": "lenguaje", "name": "Python"},
                {"category": "framework", "name": "Django"},
                {"category": "base de datos", "name": "PostgreSQL"},
            ],
        )
        out = build_html(
            rep, html_dir=tmp_path, video_id="z", url="", original_language="es",
            translated=False, provider="mock", ai_model="m", duration_str="00:10",
        )
        text = out.read_text(encoding="utf-8")
        assert "<svg" in text
        assert "chart-bar" in text

    def test_single_tech_category_no_bar_chart(self, tmp_path):
        rep = AnalysisReport(
            title="T", technologies=[{"category": "lenguaje", "name": "Python"}],
        )
        out = build_html(
            rep, html_dir=tmp_path, video_id="w", url="", original_language="es",
            translated=False, provider="mock", ai_model="m", duration_str="00:10",
        )
        text = out.read_text(encoding="utf-8")
        assert "<svg" not in text

    def test_difficulty_badge_rendered(self, tmp_path):
        rep = AnalysisReport(title="T", difficulty="Avanzado")
        out = build_html(
            rep, html_dir=tmp_path, video_id="d", url="", original_language="es",
            translated=False, provider="mock", ai_model="m", duration_str="00:10",
        )
        text = out.read_text(encoding="utf-8")
        assert "diff-badge" in text
        assert "Avanzado" in text

    def test_no_javascript_in_output(self, tmp_path, sample_report_dict):
        report = _coerce_report(sample_report_dict, "English", True, "Titulo")
        out = build_html(
            report, html_dir=tmp_path, video_id="noscript", url="",
            original_language="English", translated=True, provider="mock",
            ai_model="mock-1", duration_str="00:30",
        )
        text = out.read_text(encoding="utf-8")
        assert "<script" not in text.lower()
