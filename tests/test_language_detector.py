from src.language_detector import detect_language, language_name
from src.models import Segment, Transcript


def _t(segments, language):
    return Transcript(segments=segments, language=language, duration=segments[-1].end,
                      source="test")


class TestDetectLanguage:
    def test_spanish_from_whisper(self, spanish_segments):
        info = detect_language(_t(spanish_segments, "es"))
        assert info.code == "es"
        assert info.is_spanish is True
        assert info.name == "Espanol"

    def test_english_from_whisper(self, english_segments):
        info = detect_language(_t(english_segments, "en"))
        assert info.code == "en"
        assert info.is_spanish is False
        assert info.name == "English"

    def test_whisper_wins_on_disagreement(self, english_segments):
        # Whisper dice 'en' aunque el verificador de texto opine distinto
        info = detect_language(_t(english_segments, "en"))
        assert info.code == "en"

    def test_unknown_language_falls_back_to_text(self):
        segs = [Segment(0, 4, "This is clearly written in the English language for testing.")]
        info = detect_language(_t(segs, ""))
        # sin idioma de whisper, se apoya en langdetect (si esta instalado)
        assert info.code in ("en", "unknown")

    def test_portuguese_name(self, english_segments):
        info = detect_language(_t(english_segments, "pt"))
        assert info.name == "Portugues"
        assert info.is_spanish is False


class TestLanguageName:
    def test_known(self):
        assert language_name("es") == "Espanol"
        assert language_name("EN") == "English"

    def test_with_region(self):
        assert language_name("es-ES") == "Espanol"

    def test_unknown_returns_upper(self):
        assert language_name("xx") == "XX"
