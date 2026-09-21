import pytest

from config import Config, DEFAULT_AI_MODELS
from src.utils import ExtractorError

ENV_VARS = [
    "AI_PROVIDER", "AI_MODEL", "OPENAI_API_KEY", "GEMINI_API_KEY",
    "DEEPSEEK_API_KEY", "TRANSCRIPTION_BACKEND", "TRANSCRIPTION_MODEL",
    "OUTPUT_DIRECTORY", "TEMP_DIRECTORY", "LOGS_DIRECTORY", "NETWORK_TIMEOUT",
    "MAX_VIDEO_MB", "ALLOW_MOCK_FALLBACK", "KEEP_TEMP_ON_ERROR",
]


@pytest.fixture
def clean_env(monkeypatch, tmp_path):
    for v in ENV_VARS:
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setenv("OUTPUT_DIRECTORY", str(tmp_path / "output"))
    monkeypatch.setenv("TEMP_DIRECTORY", str(tmp_path / "temp"))
    monkeypatch.setenv("LOGS_DIRECTORY", str(tmp_path / "logs"))
    return tmp_path


def _load(tmp_path):
    # apunta a un .env inexistente para no leer el real del proyecto
    return Config.load(env_file=tmp_path / "no_such.env")


class TestDefaults:
    def test_defaults(self, clean_env, tmp_path):
        cfg = _load(tmp_path)
        assert cfg.ai_provider == "gemini"
        assert cfg.transcription_backend == "local"
        assert cfg.transcription_model == "small"

    def test_dirs_created(self, clean_env, tmp_path):
        cfg = _load(tmp_path)
        assert cfg.txt_dir.exists()
        assert cfg.html_dir.exists()
        assert cfg.temp_dir.exists()
        assert cfg.logs_dir.exists()

    def test_effective_model_fallback(self, clean_env, tmp_path):
        cfg = _load(tmp_path)
        assert cfg.effective_ai_model() == DEFAULT_AI_MODELS["gemini"]


class TestValidation:
    def test_bad_provider(self, clean_env, tmp_path, monkeypatch):
        monkeypatch.setenv("AI_PROVIDER", "chatgpt")
        with pytest.raises(ExtractorError):
            _load(tmp_path)

    def test_bad_whisper_model(self, clean_env, tmp_path, monkeypatch):
        monkeypatch.setenv("TRANSCRIPTION_MODEL", "huge")
        with pytest.raises(ExtractorError):
            _load(tmp_path)

    def test_bad_backend(self, clean_env, tmp_path, monkeypatch):
        monkeypatch.setenv("TRANSCRIPTION_BACKEND", "whispercpp")
        with pytest.raises(ExtractorError):
            _load(tmp_path)


class TestKeysAndProviders:
    def test_masked_keys_hidden(self, clean_env, tmp_path, monkeypatch):
        monkeypatch.setenv("GEMINI_API_KEY", "AIzaSuperSecretValue123456")
        cfg = _load(tmp_path)
        masked = cfg.masked_keys()["GEMINI_API_KEY"]
        assert "SuperSecret" not in masked
        assert masked.startswith("AIza") and masked.endswith("3456")

    def test_resolved_provider_without_key_no_fallback(self, clean_env, tmp_path, monkeypatch):
        monkeypatch.setenv("AI_PROVIDER", "openai")
        monkeypatch.setenv("ALLOW_MOCK_FALLBACK", "false")
        cfg = _load(tmp_path)
        assert cfg.resolved_provider() == "openai"

    def test_resolved_provider_without_key_with_fallback(self, clean_env, tmp_path, monkeypatch):
        monkeypatch.setenv("AI_PROVIDER", "openai")
        monkeypatch.setenv("ALLOW_MOCK_FALLBACK", "true")
        cfg = _load(tmp_path)
        assert cfg.resolved_provider() == "mock"

    def test_mock_always_has_key(self, clean_env, tmp_path, monkeypatch):
        monkeypatch.setenv("AI_PROVIDER", "mock")
        cfg = _load(tmp_path)
        assert cfg.has_key_for("mock")
        assert cfg.resolved_provider() == "mock"
