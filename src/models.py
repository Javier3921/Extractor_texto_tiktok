"""Modelos de datos compartidos por todo el pipeline.

Se usan dataclasses simples (sin dependencias externas) para mantener las
piezas desacopladas y facilmente testeables.
"""
from __future__ import annotations

from dataclasses import dataclass, field, asdict
from typing import Any, Optional


# --------------------------------------------------------------------------
# Transcripcion
# --------------------------------------------------------------------------
@dataclass
class Segment:
    """Un fragmento de transcripcion con marca de tiempo (en segundos)."""
    start: float
    end: float
    text: str

    def clean_text(self) -> str:
        return " ".join(self.text.split()).strip()


@dataclass
class Transcript:
    """Resultado de transcribir un audio."""
    segments: list[Segment]
    language: str            # codigo ISO detectado por el transcriptor (ej. "en", "es")
    duration: float          # duracion en segundos
    source: str              # "local-whisper" | "openai-api" | "mock" ...

    @property
    def full_text(self) -> str:
        return " ".join(s.clean_text() for s in self.segments if s.clean_text())


# --------------------------------------------------------------------------
# Idioma
# --------------------------------------------------------------------------
@dataclass
class LanguageInfo:
    """Idioma original del contenido."""
    code: str                # "es", "en", "pt", ...
    name: str                # "Espanol", "English", ...
    is_spanish: bool
    method: str              # como se determino ("whisper", "whisper+langdetect", ...)
    secondary_code: Optional[str] = None   # resultado del verificador de texto, si se ejecuto


# --------------------------------------------------------------------------
# Analisis tecnico (espejo del JSON de la seccion 18 del prompt)
# --------------------------------------------------------------------------
@dataclass
class AnalysisReport:
    title: str = ""
    original_language: str = ""
    translated_to_spanish: bool = False
    executive_summary: str = ""
    detailed_explanation: str = ""
    technologies: list[Any] = field(default_factory=list)
    technical_concepts: list[Any] = field(default_factory=list)
    architecture: str = ""
    code_analysis: str = ""
    best_practices: list[Any] = field(default_factory=list)
    risks: list[Any] = field(default_factory=list)
    recommendations: list[Any] = field(default_factory=list)
    difficulty: str = ""
    applications: list[Any] = field(default_factory=list)
    conclusion: str = ""
    # Metadatos internos (no forman parte del esquema pedido a la IA)
    parse_warning: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


# --------------------------------------------------------------------------
# Entrada del pipeline
# --------------------------------------------------------------------------
@dataclass
class MediaSource:
    """Describe de donde sale el audio a procesar."""
    kind: str                       # "url" | "file"
    ref: str                        # la URL o la ruta del archivo
    audio_path: Optional[str] = None
    video_id: str = ""
    title: str = ""
    duration: float = 0.0
    uploader: str = ""
    webpage_url: str = ""


# --------------------------------------------------------------------------
# Resultado del pipeline
# --------------------------------------------------------------------------
@dataclass
class ProcessingResult:
    video_id: str
    source_kind: str
    source_ref: str
    ok: bool = False
    original_language: str = ""
    translated: bool = False
    txt_path: Optional[str] = None
    html_path: Optional[str] = None
    duration: float = 0.0
    provider: str = ""
    ai_model: str = ""
    whisper_model: str = ""
    error: Optional[str] = None
    elapsed_seconds: float = 0.0
