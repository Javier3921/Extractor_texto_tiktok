from src.language_detector import detect_language
from src.models import LanguageInfo, Segment, Transcript
from src.txt_writer import build_txt, write_txt


def _lang(code):
    from src.language_detector import language_name
    return LanguageInfo(code=code, name=language_name(code), is_spanish=(code == "es"),
                        method="test")


class TestBuildTxt:
    def test_header_fields_present(self, english_segments):
        txt = build_txt(
            url="https://www.tiktok.com/@u/video/123", video_id="123",
            language=_lang("en"), duration=9.0, translated=True,
            original_segments=english_segments, spanish_segments=english_segments,
        )
        for field in ("INFORMACION DEL VIDEO", "URL:", "FECHA DE PROCESAMIENTO:",
                      "IDIOMA ORIGINAL:", "IDIOMA DEL REPORTE:", "TRADUCCION REALIZADA:",
                      "DURACION:", "ID DEL VIDEO:"):
            assert field in txt

    def test_translated_has_both_sections(self, english_segments, spanish_segments):
        txt = build_txt(
            url="u", video_id="123", language=_lang("en"), duration=9.0,
            translated=True, original_segments=english_segments,
            spanish_segments=spanish_segments,
        )
        assert "TRANSCRIPCION ORIGINAL" in txt
        assert "TRANSCRIPCION EN ESPANOL" in txt
        assert "TRADUCCION REALIZADA:    Si" in txt

    def test_spanish_only_one_section(self, spanish_segments):
        txt = build_txt(
            url="u", video_id="123", language=_lang("es"), duration=6.0,
            translated=False, original_segments=spanish_segments,
            spanish_segments=spanish_segments,
        )
        assert "TRANSCRIPCION ORIGINAL" not in txt
        assert "TRANSCRIPCION EN ESPANOL" in txt
        assert "TRADUCCION REALIZADA:    No" in txt

    def test_timestamp_lines(self, english_segments):
        txt = build_txt(
            url="u", video_id="123", language=_lang("en"), duration=9.0,
            translated=True, original_segments=english_segments,
            spanish_segments=english_segments,
        )
        assert "[00:00]" in txt
        assert "[00:03]" in txt


class TestWriteTxt:
    def test_writes_utf8_file(self, tmp_path, spanish_segments):
        txt = build_txt(
            url="u", video_id="7300000000000000123", language=_lang("es"),
            duration=6.0, translated=False, original_segments=spanish_segments,
            spanish_segments=spanish_segments,
        )
        path = write_txt(txt, tmp_path, "7300000000000000123")
        assert path.exists()
        assert path.name == "tiktok_7300000000000000123.txt"
        content = path.read_text(encoding="utf-8")
        assert "TRANSCRIPCION EN ESPANOL" in content

    def test_local_id_filename(self, tmp_path, spanish_segments):
        txt = build_txt(
            url="", video_id="local_demo_20260101_000000", language=_lang("es"),
            duration=6.0, translated=False, original_segments=spanish_segments,
            spanish_segments=spanish_segments,
        )
        path = write_txt(txt, tmp_path, "local_demo_20260101_000000")
        assert path.name == "local_demo_20260101_000000.txt"
