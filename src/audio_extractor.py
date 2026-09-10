"""Extraccion / normalizacion de audio con FFmpeg.

Whisper funciona mejor con WAV PCM 16 kHz mono. Esta funcion convierte
cualquier entrada (video local o audio ya descargado de TikTok) a ese formato.
"""
from __future__ import annotations

import subprocess
from pathlib import Path

from src.utils import (ExtractorError, ffmpeg_install_hint, get_logger,
                       resolve_ffmpeg)

log = get_logger()

TARGET_SAMPLE_RATE = 16000
TARGET_CHANNELS = 1


def ffmpeg_available() -> bool:
    return resolve_ffmpeg() is not None


def extract_audio(source: Path, workdir: Path, *, out_name: str = "audio_16k.wav") -> Path:
    """Convierte `source` a WAV 16 kHz mono dentro de `workdir`. Devuelve la ruta."""
    ffmpeg = resolve_ffmpeg()
    if not ffmpeg:
        raise ExtractorError(ffmpeg_install_hint())

    source = Path(source)
    if not source.exists():
        raise ExtractorError(f"No se encuentra el archivo de origen del audio: {source}")

    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    out_path = workdir / out_name

    cmd = [
        ffmpeg, "-y",
        "-i", str(source),
        "-vn",                       # descarta cualquier pista de video
        "-ac", str(TARGET_CHANNELS),
        "-ar", str(TARGET_SAMPLE_RATE),
        "-c:a", "pcm_s16le",
        "-loglevel", "error",
        str(out_path),
    ]
    log.info("FFmpeg: extrayendo audio de %s", source.name)
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, timeout=1800)
    except FileNotFoundError as e:
        raise ExtractorError(ffmpeg_install_hint()) from e
    except subprocess.TimeoutExpired as e:
        raise ExtractorError("FFmpeg tardo demasiado (>30 min) extrayendo el audio.") from e

    if proc.returncode != 0 or not out_path.exists():
        detail = (proc.stderr or proc.stdout or "").strip()[-800:]
        raise ExtractorError(f"FFmpeg no pudo extraer el audio.\nDetalle: {detail}")

    if out_path.stat().st_size < 1024:
        raise ExtractorError(
            "El audio extraido esta vacio. Puede que el video no tenga pista de audio."
        )
    return out_path


def probe_duration(source: Path) -> float:
    """Duracion en segundos usando ffprobe si esta disponible; 0.0 si no se puede."""
    import shutil
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        return 0.0
    try:
        out = subprocess.run(
            [ffprobe, "-v", "error", "-show_entries", "format=duration",
             "-of", "default=noprint_wrappers=1:nokey=1", str(source)],
            capture_output=True, text=True, timeout=60,
        )
        return float((out.stdout or "0").strip() or 0.0)
    except Exception:
        return 0.0
