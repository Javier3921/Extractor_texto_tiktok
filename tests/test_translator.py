from src.ai_providers.base import AIProvider
from src.ai_providers.mock_provider import MockProvider
from src.translator import translate_to_spanish


class _AlwaysFailsProvider(AIProvider):
    """Simula un proveedor cuyas llamadas de traduccion siempre fallan
    (p.ej. respuesta no-JSON persistente), para probar que el fallo se
    contabiliza en vez de quedar silencioso."""

    name = "flaky"
    max_retries = 1

    def __init__(self):
        super().__init__(api_key="n/a", model="flaky-1")

    def _complete_raw(self, system, user, want_json, max_tokens):
        raise RuntimeError("simulated provider failure")


class TestTranslateToSpanish:
    def test_spanish_input_is_not_translated(self, spanish_segments):
        res = translate_to_spanish(
            spanish_segments, source_language="Espanol",
            provider=MockProvider(), is_spanish=True,
        )
        assert res.translated is False
        assert res.spanish_segments == spanish_segments

    def test_english_input_is_translated(self, english_segments):
        res = translate_to_spanish(
            english_segments, source_language="English",
            provider=MockProvider(), is_spanish=False,
        )
        assert res.translated is True
        assert len(res.spanish_segments) == len(english_segments)

    def test_timestamps_preserved(self, english_segments):
        res = translate_to_spanish(
            english_segments, source_language="English",
            provider=MockProvider(), is_spanish=False,
        )
        for orig, es in zip(english_segments, res.spanish_segments):
            assert es.start == orig.start
            assert es.end == orig.end

    def test_segment_count_preserved_large(self):
        from src.models import Segment
        segs = [Segment(i, i + 1, f"Sentence number {i} about Docker.") for i in range(95)]
        res = translate_to_spanish(
            segs, source_language="English", provider=MockProvider(), is_spanish=False,
        )
        assert len(res.spanish_segments) == 95

    def test_technical_terms_preserved(self, english_segments):
        res = translate_to_spanish(
            english_segments, source_language="English",
            provider=MockProvider(), is_spanish=False,
        )
        joined = " ".join(s.text for s in res.spanish_segments)
        for term in ("Node.js", "Express", "Docker", "Kubernetes", "PostgreSQL", "OAuth 2.0"):
            assert term in joined

    def test_fallo_persistente_se_reporta_no_se_silencia(self, english_segments):
        res = translate_to_spanish(
            english_segments, source_language="English",
            provider=_AlwaysFailsProvider(), is_spanish=False,
        )
        assert res.failed_segments == len(english_segments)
        # se conserva el texto original en los segmentos que no se pudieron traducir
        for orig, es in zip(english_segments, res.spanish_segments):
            assert es.text == orig.text

    def test_traduccion_correcta_no_reporta_fallos(self, english_segments):
        res = translate_to_spanish(
            english_segments, source_language="English",
            provider=MockProvider(), is_spanish=False,
        )
        assert res.failed_segments == 0
