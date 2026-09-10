import pytest

from src.utils import (ExtractorError, extract_video_id, fallback_id_from_text,
                       format_timestamp, safe_output_path, sanitize_filename)


class TestSanitizeFilename:
    def test_basic(self):
        assert sanitize_filename("hola mundo.txt") == "hola mundo.txt"

    def test_strips_path_separators(self):
        out = sanitize_filename("a/b\\c.txt")
        assert "/" not in out and "\\" not in out

    def test_removes_parent_refs(self):
        out = sanitize_filename("../../etc/passwd")
        assert ".." not in out

    def test_unicode_accents_removed_or_replaced(self):
        out = sanitize_filename("informe_técnico_ñ.pdf")
        assert out and "/" not in out

    def test_empty_returns_default(self):
        assert sanitize_filename("") == "archivo"

    def test_length_capped(self):
        assert len(sanitize_filename("x" * 500)) <= 120


class TestSafeOutputPath:
    def test_inside_base(self, tmp_path):
        p = safe_output_path(tmp_path, "reporte.pdf")
        assert str(p).startswith(str(tmp_path.resolve()))

    def test_traversal_blocked(self, tmp_path):
        # sanitize ya neutraliza '..'; el resultado sigue dentro de base
        p = safe_output_path(tmp_path, "../../secreto.txt")
        assert str(p).startswith(str(tmp_path.resolve()))

    def test_absolute_escape_blocked(self, tmp_path):
        p = safe_output_path(tmp_path, "C:\\Windows\\System32\\evil.txt")
        assert str(p).startswith(str(tmp_path.resolve()))


class TestExtractVideoId:
    def test_standard_url(self):
        assert extract_video_id(
            "https://www.tiktok.com/@user/video/7300000000000000123"
        ) == "7300000000000000123"

    def test_photo_url(self):
        assert extract_video_id(
            "https://www.tiktok.com/@user/photo/7300000000000000123"
        ) == "7300000000000000123"

    def test_no_id(self):
        assert extract_video_id("https://vm.tiktok.com/ZMabc/") is None

    def test_fallback_is_stable(self):
        a = fallback_id_from_text("https://x/y")
        b = fallback_id_from_text("https://x/y")
        assert a == b and len(a) == 12


class TestFormatTimestamp:
    @pytest.mark.parametrize("seconds,expected", [
        (0, "00:00"),
        (5, "00:05"),
        (65, "01:05"),
        (3661, "1:01:01"),
        (599, "09:59"),
    ])
    def test_values(self, seconds, expected):
        assert format_timestamp(seconds) == expected

    def test_none_is_zero(self):
        assert format_timestamp(None) == "00:00"
