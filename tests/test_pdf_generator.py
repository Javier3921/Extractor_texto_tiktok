import pytest

pytest.importorskip("reportlab")

from src.ai_analyzer import _coerce_report
from src.models import AnalysisReport
from src.pdf_generator import build_pdf


class TestBuildPdf:
    def test_generates_valid_pdf(self, tmp_path, sample_report_dict):
        report = _coerce_report(sample_report_dict, "English", True, "Titulo")
        out = build_pdf(
            report, pdf_dir=tmp_path, video_id="7300000000000000123",
            url="https://www.tiktok.com/@u/video/7300000000000000123",
            original_language="English", translated=True, provider="mock",
            ai_model="mock-1", duration_str="00:30",
        )
        assert out.exists()
        assert out.name == "reporte_tiktok_7300000000000000123.pdf"
        data = out.read_bytes()
        assert data[:4] == b"%PDF"
        assert len(data) > 2000

    def test_handles_accents_and_special_chars(self, tmp_path):
        report = AnalysisReport(
            title="Análisis técnico: ¿cómo funciona la señal?",
            executive_summary="Configuración con ñ, á, é, í, ó, ú, ü y signos ¿ ¡.",
            detailed_explanation="Programación en Python. Diseño de la API. Versión 2.",
            architecture="Cliente → Servidor → Base de datos.",
            code_analysis="La función devuelve un número.",
            difficulty="Intermedio",
            conclusion="解 mixed scripts fallback. Está todo correcto.",
            technologies=[{"category": "lenguaje", "name": "Python"}],
            best_practices=["Usar entornos virtuales"],
            risks=["Inyección SQL si no se sanea la entrada"],
            recommendations=["Añadir tests"],
            technical_concepts=["REST", "JSON"],
            applications=["Backends web"],
        )
        out = build_pdf(
            report, pdf_dir=tmp_path, video_id="local_demo",
            url="", original_language="Español", translated=False,
            provider="mock", ai_model="mock-1", duration_str="01:02",
        )
        assert out.exists()
        assert out.read_bytes()[:4] == b"%PDF"

    def test_empty_report_still_produces_pdf(self, tmp_path):
        out = build_pdf(
            AnalysisReport(), pdf_dir=tmp_path, video_id="x",
            url="", original_language="Desconocido", translated=False,
            provider="mock", ai_model="mock-1", duration_str="00:00",
        )
        assert out.exists()
        assert out.read_bytes()[:4] == b"%PDF"

    def test_plain_string_technologies(self, tmp_path):
        rep = AnalysisReport(title="T", technologies=["Python", "Docker"])
        out = build_pdf(
            rep, pdf_dir=tmp_path, video_id="y", url="", original_language="es",
            translated=False, provider="mock", ai_model="m", duration_str="00:10",
        )
        assert out.read_bytes()[:4] == b"%PDF"
