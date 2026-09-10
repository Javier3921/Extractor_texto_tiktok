"""Validacion de archivos de video locales (modo --file, fallback de TikTok)."""
from __future__ import annotations

from pathlib import Path

from src.utils import ExtractorError

SUPPORTED_EXTENSIONS = {".mp4", ".mov", ".mkv", ".webm", ".avi", ".m4v", ".flv"}
# tambien aceptamos audio suelto por comodidad
SUPPORTED_AUDIO = {".mp3", ".wav", ".m4a", ".aac", ".ogg", ".flac"}


def validate_local_media(path: str, max_mb: int = 0) -> Path:
    """Comprueba que el archivo existe y tiene una extension soportada."""
    if not path:
        raise ExtractorError("No se indico ninguna ruta de archivo.")
    p = Path(path).expanduser()
    if not p.exists():
        raise ExtractorError(f"El archivo no existe: {p}")
    if not p.is_file():
        raise ExtractorError(f"La ruta no es un archivo: {p}")

    ext = p.suffix.lower()
    if ext not in SUPPORTED_EXTENSIONS and ext not in SUPPORTED_AUDIO:
        allowed = ", ".join(sorted(SUPPORTED_EXTENSIONS | SUPPORTED_AUDIO))
        raise ExtractorError(
            f"Extension no soportada: {ext!r}.\nFormatos aceptados: {allowed}"
        )

    if max_mb:
        size_mb = p.stat().st_size / (1024 * 1024)
        if size_mb > max_mb:
            raise ExtractorError(
                f"El archivo pesa {size_mb:.0f} MB y supera el limite de {max_mb} MB "
                f"(ajusta MAX_VIDEO_MB en .env si es intencionado)."
            )
    return p.resolve()


def is_audio_only(path: Path) -> bool:
    return Path(path).suffix.lower() in SUPPORTED_AUDIO
