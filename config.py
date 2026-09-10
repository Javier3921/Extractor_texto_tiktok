"""Carga y validacion de la configuracion desde .env / variables de entorno."""
from __future__ import annotations

import os
from dataclasses import dataclass, field
from pathlib import Path

try:
    from dotenv import load_dotenv
except ImportError:  # pragma: no cover - dotenv siempre esta en requirements
    def load_dotenv(*_a, **_k):  # type: ignore
        return False

from src.utils import ExtractorError

PROJECT_ROOT = Path(__file__).resolve().parent

VALID_PROVIDERS = ("openai", "gemini", "deepseek", "mock")
VALID_BACKENDS = ("local", "openai_api")
VALID_WHISPER_MODELS = ("tiny", "base", "small", "medium", "large", "large-v2", "large-v3")

# Modelos por defecto de cada proveedor. OJO: los proveedores retiran modelos
# con el tiempo; si uno deja de existir, define AI_MODEL en .env con el nuevo
# nombre (el proveedor Gemini ademas intenta autocorregir el modelo si la API
# indica el sustituto en el error 404).
DEFAULT_AI_MODELS = {
    "openai": "gpt-4o-mini",
    "gemini": "gemini-3.6-flash",
    "deepseek": "deepseek-chat",
    "mock": "mock-1",
}


def _get(name: str, default: str = "") -> str:
    return (os.environ.get(name) or default).strip()


def _get_bool(name: str, default: bool = False) -> bool:
    val = _get(name, "").lower()
    if not val:
        return default
    return val in ("1", "true", "yes", "y", "si", "s", "on")


def _get_int(name: str, default: int) -> int:
    try:
        return int(_get(name, str(default)))
    except ValueError:
        return default


@dataclass
class Config:
    ai_provider: str = "gemini"
    ai_model: str = ""
    openai_api_key: str = ""
    gemini_api_key: str = ""
    deepseek_api_key: str = ""

    transcription_backend: str = "local"
    transcription_model: str = "small"

    output_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "output")
    temp_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "temp")
    logs_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "logs")
    input_dir: Path = field(default_factory=lambda: PROJECT_ROOT / "input")

    network_timeout: int = 30
    max_video_mb: int = 200
    allow_mock_fallback: bool = False
    keep_temp_on_error: bool = True

    # ---------------------------------------------------------------- build
    @classmethod
    def load(cls, env_file: Path | None = None) -> "Config":
        load_dotenv(env_file or (PROJECT_ROOT / ".env"))

        def _dir(var: str, fallback: str) -> Path:
            raw = _get(var, fallback)
            p = Path(raw)
            if not p.is_absolute():
                p = PROJECT_ROOT / p
            return p

        cfg = cls(
            ai_provider=_get("AI_PROVIDER", "gemini").lower(),
            ai_model=_get("AI_MODEL", ""),
            openai_api_key=_get("OPENAI_API_KEY"),
            gemini_api_key=_get("GEMINI_API_KEY"),
            deepseek_api_key=_get("DEEPSEEK_API_KEY"),
            transcription_backend=_get("TRANSCRIPTION_BACKEND", "local").lower(),
            transcription_model=_get("TRANSCRIPTION_MODEL", "small").lower(),
            output_dir=_dir("OUTPUT_DIRECTORY", "output"),
            temp_dir=_dir("TEMP_DIRECTORY", "temp"),
            logs_dir=_dir("LOGS_DIRECTORY", "logs"),
            network_timeout=_get_int("NETWORK_TIMEOUT", 30),
            max_video_mb=_get_int("MAX_VIDEO_MB", 200),
            allow_mock_fallback=_get_bool("ALLOW_MOCK_FALLBACK", False),
            keep_temp_on_error=_get_bool("KEEP_TEMP_ON_ERROR", True),
        )
        cfg.validate()
        cfg.ensure_dirs()
        return cfg

    # ---------------------------------------------------------------- checks
    def validate(self) -> None:
        if self.ai_provider not in VALID_PROVIDERS:
            raise ExtractorError(
                f"AI_PROVIDER invalido: {self.ai_provider!r}. "
                f"Valores: {', '.join(VALID_PROVIDERS)}"
            )
        if self.transcription_backend not in VALID_BACKENDS:
            raise ExtractorError(
                f"TRANSCRIPTION_BACKEND invalido: {self.transcription_backend!r}. "
                f"Valores: {', '.join(VALID_BACKENDS)}"
            )
        if self.transcription_model not in VALID_WHISPER_MODELS:
            raise ExtractorError(
                f"TRANSCRIPTION_MODEL invalido: {self.transcription_model!r}. "
                f"Valores: {', '.join(VALID_WHISPER_MODELS)}"
            )

    def ensure_dirs(self) -> None:
        for d in (self.output_dir, self.output_dir / "txt", self.output_dir / "pdf",
                  self.temp_dir, self.logs_dir, self.input_dir):
            Path(d).mkdir(parents=True, exist_ok=True)

    # ---------------------------------------------------------------- helpers
    @property
    def txt_dir(self) -> Path:
        return self.output_dir / "txt"

    @property
    def pdf_dir(self) -> Path:
        return self.output_dir / "pdf"

    def effective_ai_model(self) -> str:
        return self.ai_model or DEFAULT_AI_MODELS.get(self.ai_provider, "")

    def api_key_for(self, provider: str) -> str:
        return {
            "openai": self.openai_api_key,
            "gemini": self.gemini_api_key,
            "deepseek": self.deepseek_api_key,
            "mock": "n/a",
        }.get(provider, "")

    def has_key_for(self, provider: str) -> bool:
        return provider == "mock" or bool(self.api_key_for(provider))

    def resolved_provider(self) -> str:
        """Proveedor que se usara realmente (aplica el fallback a mock si procede)."""
        if self.has_key_for(self.ai_provider):
            return self.ai_provider
        if self.allow_mock_fallback:
            return "mock"
        return self.ai_provider  # se usara y fallara con mensaje claro

    def masked_keys(self) -> dict[str, str]:
        def mask(v: str) -> str:
            if not v:
                return "(no configurada)"
            if len(v) <= 8:
                return "****"
            return f"{v[:4]}...{v[-4:]}"
        return {
            "OPENAI_API_KEY": mask(self.openai_api_key),
            "GEMINI_API_KEY": mask(self.gemini_api_key),
            "DEEPSEEK_API_KEY": mask(self.deepseek_api_key),
        }

    def summary_lines(self) -> list[str]:
        return [
            f"Proveedor de IA .......... {self.ai_provider}"
            + ("" if self.has_key_for(self.ai_provider) else "  [SIN CLAVE]"),
            f"Modelo de IA ............. {self.effective_ai_model()}",
            f"Backend transcripcion .... {self.transcription_backend}",
            f"Modelo Whisper ........... {self.transcription_model}",
            f"Carpeta de salida ........ {self.output_dir}",
            f"Carpeta temporal ......... {self.temp_dir}",
            f"Carpeta de logs .......... {self.logs_dir}",
            f"Timeout de red ........... {self.network_timeout}s",
            f"Tam. maximo de medio ..... {self.max_video_mb} MB",
            f"Fallback a mock .......... {'si' if self.allow_mock_fallback else 'no'}",
            *[f"{k} .. {v}" for k, v in self.masked_keys().items()],
        ]
