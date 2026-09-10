"""Transcripcion de audio.

Backends:
  * "local"      -> openai-whisper ejecutandose en la maquina (offline, gratis).
  * "openai_api" -> API de OpenAI (whisper-1). De pago; limite de 25 MB por archivo.

El import de whisper/torch es PEREZOSO para que los tests no necesiten esas
dependencias pesadas.
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional

from src.models import Segment, Transcript
from src.utils import ExtractorError, get_logger

log = get_logger()

# Cache del modelo local para no recargarlo en cada elemento de un lote.
_local_model_cache: dict[str, object] = {}


def transcribe(audio_path: Path, *, backend: str = "local", model: str = "small",
               api_key: str = "", language_hint: Optional[str] = None) -> Transcript:
    audio_path = Path(audio_path)
    if not audio_path.exists():
        raise ExtractorError(f"No se encuentra el audio a transcribir: {audio_path}")

    if backend == "local":
        return _transcribe_local(audio_path, model, language_hint)
    if backend == "openai_api":
        return _transcribe_openai_api(audio_path, api_key, language_hint)
    raise ExtractorError(f"Backend de transcripcion desconocido: {backend!r}")


# --------------------------------------------------------------------------
# Backend local: openai-whisper
# --------------------------------------------------------------------------
def _load_local_model(model_name: str):
    if model_name in _local_model_cache:
        return _local_model_cache[model_name]
    try:
        import whisper  # openai-whisper
    except ImportError as e:  # pragma: no cover
        raise ExtractorError(
            "Falta 'openai-whisper'. Instala las dependencias:\n"
            "  pip install -r requirements.txt\n"
            "(o cambia TRANSCRIPTION_BACKEND=openai_api en .env para usar la API)."
        ) from e
    log.info("Cargando modelo Whisper local '%s' (puede descargarlo la 1a vez)...", model_name)
    try:
        mdl = whisper.load_model(model_name)
    except Exception as e:  # noqa: BLE001
        raise ExtractorError(f"No se pudo cargar el modelo Whisper '{model_name}': {e}") from e
    _local_model_cache[model_name] = mdl
    return mdl


def _load_wav_mono16k(path: Path):
    """Lee un WAV PCM (el que produce audio_extractor: 16 kHz mono s16) a
    un ndarray float32 en [-1, 1]. Evita que whisper tenga que invocar ffmpeg
    (cuyo binario embebido no se llama 'ffmpeg.exe')."""
    import wave

    import numpy as np

    with wave.open(str(path), "rb") as wf:
        n_channels = wf.getnchannels()
        sampwidth = wf.getsampwidth()
        framerate = wf.getframerate()
        frames = wf.readframes(wf.getnframes())

    if sampwidth != 2:
        raise ExtractorError(
            f"Formato WAV inesperado (sampwidth={sampwidth}); se esperaba PCM 16-bit."
        )
    audio = np.frombuffer(frames, dtype=np.int16).astype(np.float32) / 32768.0
    if n_channels > 1:
        audio = audio.reshape(-1, n_channels).mean(axis=1)
    if framerate != 16000:
        # remuestreo lineal simple (audio_extractor ya entrega 16 kHz;
        # esto es solo una red de seguridad)
        import math
        new_len = int(math.floor(len(audio) * 16000 / framerate))
        if new_len > 0:
            xp = np.linspace(0, 1, num=len(audio), endpoint=False)
            x = np.linspace(0, 1, num=new_len, endpoint=False)
            audio = np.interp(x, xp, audio).astype(np.float32)
    return np.ascontiguousarray(audio)


def _transcribe_local(audio_path: Path, model_name: str,
                      language_hint: Optional[str]) -> Transcript:
    mdl = _load_local_model(model_name)
    kwargs = {"task": "transcribe", "verbose": False, "fp16": False}
    if language_hint:
        kwargs["language"] = language_hint
    try:
        audio = _load_wav_mono16k(audio_path)
        result = mdl.transcribe(audio, **kwargs)
    except ExtractorError:
        raise
    except Exception as e:  # noqa: BLE001
        raise ExtractorError(f"Whisper fallo durante la transcripcion: {e}") from e

    segments = _segments_from_whisper(result.get("segments") or [])
    if not segments:
        text = (result.get("text") or "").strip()
        if text:
            segments = [Segment(0.0, 0.0, text)]
    if not segments:
        raise ExtractorError(
            "La transcripcion salio vacia. Puede que el audio no contenga voz."
        )
    duration = segments[-1].end or _fallback_duration(audio_path)
    return Transcript(
        segments=segments,
        language=(result.get("language") or "").lower() or "unknown",
        duration=duration,
        source=f"local-whisper:{model_name}",
    )


def _segments_from_whisper(raw_segments: list) -> list[Segment]:
    out: list[Segment] = []
    for s in raw_segments:
        text = (s.get("text") or "").strip()
        if not text:
            continue
        out.append(Segment(
            start=float(s.get("start") or 0.0),
            end=float(s.get("end") or 0.0),
            text=text,
        ))
    return out


# --------------------------------------------------------------------------
# Backend API: OpenAI whisper-1
# --------------------------------------------------------------------------
def _transcribe_openai_api(audio_path: Path, api_key: str,
                           language_hint: Optional[str]) -> Transcript:
    if not api_key:
        raise ExtractorError(
            "TRANSCRIPTION_BACKEND=openai_api requiere OPENAI_API_KEY en .env."
        )
    size_mb = audio_path.stat().st_size / (1024 * 1024)
    if size_mb > 25:
        raise ExtractorError(
            f"El audio pesa {size_mb:.1f} MB y la API de OpenAI limita a 25 MB. "
            "Usa el backend local o acorta el audio."
        )
    try:
        from openai import OpenAI
    except ImportError as e:  # pragma: no cover
        raise ExtractorError("Falta el paquete 'openai'.") from e

    client = OpenAI(api_key=api_key)
    kwargs = {"model": "whisper-1", "response_format": "verbose_json"}
    if language_hint:
        kwargs["language"] = language_hint
    try:
        with open(audio_path, "rb") as fh:
            resp = client.audio.transcriptions.create(file=fh, **kwargs)
    except Exception as e:  # noqa: BLE001
        raise ExtractorError(f"La API de transcripcion de OpenAI fallo: {e}") from e

    data = resp.model_dump() if hasattr(resp, "model_dump") else dict(resp)
    segments = _segments_from_whisper(data.get("segments") or [])
    if not segments and data.get("text"):
        segments = [Segment(0.0, 0.0, str(data["text"]).strip())]
    if not segments:
        raise ExtractorError("La API devolvio una transcripcion vacia.")
    return Transcript(
        segments=segments,
        language=(data.get("language") or "").lower() or "unknown",
        duration=float(data.get("duration") or segments[-1].end or 0.0),
        source="openai-api:whisper-1",
    )


def _fallback_duration(audio_path: Path) -> float:
    from src.audio_extractor import probe_duration
    return probe_duration(audio_path)
