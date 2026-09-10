"""Deteccion del idioma original del contenido.

Estrategia:
  1. Fuente primaria = idioma que devuelve Whisper (se basa en el audio).
  2. Verificacion secundaria = langdetect sobre el texto transcrito.
     Si discrepan, se deja constancia pero se confia en Whisper.
"""
from __future__ import annotations

from src.models import LanguageInfo, Transcript
from src.utils import get_logger

log = get_logger()

# Nombres legibles por codigo ISO 639-1.
_LANGUAGE_NAMES = {
    "es": "Espanol", "en": "English", "pt": "Portugues", "fr": "Francais",
    "de": "Deutsch", "it": "Italiano", "nl": "Nederlands", "ca": "Catala",
    "gl": "Galego", "eu": "Euskara", "ru": "Russkiy", "uk": "Ukrainska",
    "pl": "Polski", "ja": "Nihongo", "zh": "Zhongwen", "ko": "Hangugeo",
    "ar": "Al-arabiyya", "hi": "Hindi", "tr": "Turkce", "sv": "Svenska",
    "no": "Norsk", "da": "Dansk", "fi": "Suomi", "el": "Ellinika",
    "he": "Ivrit", "id": "Bahasa Indonesia", "vi": "Tieng Viet",
    "ro": "Romana", "cs": "Cestina", "hu": "Magyar",
}


def language_name(code: str) -> str:
    code = (code or "").lower().split("-")[0]
    return _LANGUAGE_NAMES.get(code, code.upper() or "Desconocido")


def _secondary_detect(text: str) -> str | None:
    text = (text or "").strip()
    if len(text) < 20:
        return None
    try:
        from langdetect import DetectorFactory, detect
        DetectorFactory.seed = 0
        return detect(text).lower().split("-")[0]
    except Exception as e:  # noqa: BLE001
        log.info("langdetect no disponible o fallo: %s", e)
        return None


def detect_language(transcript: Transcript) -> LanguageInfo:
    primary = (transcript.language or "").lower().split("-")[0]
    secondary = _secondary_detect(transcript.full_text)

    method = "whisper"
    if secondary:
        method = "whisper+langdetect"
        if primary and secondary != primary:
            log.warning(
                "Discrepancia de idioma: Whisper=%s, langdetect=%s. Se usa Whisper.",
                primary, secondary,
            )
        elif not primary:
            primary = secondary
            method = "langdetect"

    if not primary:
        primary = "unknown"

    return LanguageInfo(
        code=primary,
        name=language_name(primary),
        is_spanish=(primary == "es"),
        method=method,
        secondary_code=secondary,
    )
