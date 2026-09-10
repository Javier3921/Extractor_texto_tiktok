from src.tiktok_downloader import is_tiktok_url, validate_url


class TestValidateUrl:
    def test_valid_https(self):
        assert validate_url("https://www.tiktok.com/@u/video/123")

    def test_valid_http(self):
        assert validate_url("http://tiktok.com/@u/video/123")

    def test_empty(self):
        assert not validate_url("")

    def test_none(self):
        assert not validate_url(None)  # type: ignore

    def test_not_a_url(self):
        assert not validate_url("no soy una url")

    def test_ftp_scheme(self):
        assert not validate_url("ftp://tiktok.com/x")

    def test_missing_scheme(self):
        assert not validate_url("www.tiktok.com/@u/video/123")


class TestIsTiktokUrl:
    def test_www(self):
        assert is_tiktok_url("https://www.tiktok.com/@user/video/7300000000000000000")

    def test_bare_domain(self):
        assert is_tiktok_url("https://tiktok.com/@user/video/7300000000000000000")

    def test_short_vm(self):
        assert is_tiktok_url("https://vm.tiktok.com/ZMabc123/")

    def test_short_vt(self):
        assert is_tiktok_url("https://vt.tiktok.com/ZSabc123/")

    def test_mobile(self):
        assert is_tiktok_url("https://m.tiktok.com/v/123.html")

    def test_youtube_is_not_tiktok(self):
        assert not is_tiktok_url("https://www.youtube.com/watch?v=abc")

    def test_lookalike_domain_rejected(self):
        assert not is_tiktok_url("https://tiktok.com.evil.example/@u/video/1")

    def test_instagram_rejected(self):
        assert not is_tiktok_url("https://www.instagram.com/reel/abc/")
