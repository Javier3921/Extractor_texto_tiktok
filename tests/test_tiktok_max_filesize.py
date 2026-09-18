"""Comprueba que MAX_VIDEO_MB tambien se aplica a la descarga de audio de
TikTok (antes solo se aplicaba a --file), pasando max_filesize a yt-dlp."""
from __future__ import annotations

import sys
import types

import pytest

from src.tiktok_downloader import fetch_audio


class _FakeYDL:
    captured_opts: dict = {}

    def __init__(self, opts):
        _FakeYDL.captured_opts = opts

    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False

    def extract_info(self, url, download=True):
        return {"id": "123", "title": "t", "duration": 1.0, "uploader": "u",
                "webpage_url": url}

    def sanitize_info(self, info):
        return info

    def prepare_filename(self, info):
        # simula que yt-dlp ya escribio el archivo
        path = self._workdir / "audio_123.m4a"
        path.write_bytes(b"fake")
        return str(path)


class _FakeUtils:
    class DownloadError(Exception):
        pass

    class ExtractorError(Exception):
        pass


@pytest.fixture
def fake_yt_dlp(monkeypatch, tmp_path):
    _FakeYDL._workdir = tmp_path
    fake_module = types.ModuleType("yt_dlp")
    fake_module.YoutubeDL = _FakeYDL
    fake_module.utils = _FakeUtils
    monkeypatch.setitem(sys.modules, "yt_dlp", fake_module)
    return fake_module


class TestMaxFilesize:
    def test_max_mb_se_traduce_a_max_filesize_en_bytes(self, fake_yt_dlp, tmp_path):
        fetch_audio("https://www.tiktok.com/@u/video/123", tmp_path, max_mb=50)
        assert _FakeYDL.captured_opts["max_filesize"] == 50 * 1024 * 1024

    def test_sin_max_mb_no_se_limita(self, fake_yt_dlp, tmp_path):
        fetch_audio("https://www.tiktok.com/@u/video/123", tmp_path, max_mb=0)
        assert "max_filesize" not in _FakeYDL.captured_opts
