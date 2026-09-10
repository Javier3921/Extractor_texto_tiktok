"""Traduccion al espanol de la transcripcion, usando el proveedor de IA.

Reglas (seccion 12 del prompt):
  * Si el idioma original ya es espanol -> NO se traduce.
  * Si no -> se traduce TODO al espanol, conservando la transcripcion original.
  * Se conservan timestamps, nombres propios y terminologia tecnica
    (React, Node.js, REST API, OAuth 2.0, Docker, Kubernetes, ...).
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from src.ai_providers.base import AIAuthError, AIProvider
from src.ai_providers.mock_provider import MARK_TRANSLATE
from src.models import Segment
from src.utils import ExtractorError, extract_json, get_logger

log = get_logger()

BATCH_SIZE = 40

_SYSTEM = f"""{MARK_TRANSLATE}
Eres un traductor tecnico profesional. Traduces al ESPANOL manteniendo el
significado tecnico exacto y un espanol natural (no literal).

REGLAS OBLIGATORIAS:
- NO traduzcas nombres propios, marcas, ni nombres de tecnologias, lenguajes,
  frameworks, librerias, APIs, productos, protocolos o herramientas.
  Ejemplos que se dejan TAL CUAL: React, Node.js, Express, Python, JavaScript,
  TypeScript, REST API, GraphQL, OAuth 2.0, JWT, Docker, Kubernetes, GitHub,
  PostgreSQL, MongoDB, Redis, AWS, Azure, GCP, Django, FastAPI, Next.js, Linux.
- Manten el sentido tecnico; si una frase en ingles usa un termino tecnico,
  consérvalo en ingles cuando su traduccion pueda causar confusion.
- Devuelve EXACTAMENTE el mismo numero de segmentos que recibes y en el mismo orden.
- Responde SOLO con JSON valido, sin texto adicional, con esta forma:
  {{"segments": [{{"i": 0, "text": "..."}}, {{"i": 1, "text": "..."}}]}}
"""


@dataclass
class TranslationResult:
    spanish_segments: list[Segment]
    translated: bool
    provider: str


def translate_to_spanish(segments: list[Segment], *, source_language: str,
                         provider: AIProvider, is_spanish: bool) -> TranslationResult:
    if is_spanish:
        log.info("El contenido ya esta en espanol: no se traduce.")
        return TranslationResult(list(segments), translated=False, provider=provider.name)

    log.info("Traduciendo %d segmentos de '%s' al espanol con %s",
             len(segments), source_language, provider.name)

    translated_texts: list[str] = []
    for start in range(0, len(segments), BATCH_SIZE):
        chunk = segments[start:start + BATCH_SIZE]
        translated_texts.extend(_translate_batch(chunk, provider, offset=start))

    if len(translated_texts) != len(segments):
        raise ExtractorError(
            f"La traduccion devolvio {len(translated_texts)} textos para "
            f"{len(segments)} segmentos."
        )

    es_segments = [
        Segment(seg.start, seg.end, txt.strip() or seg.text)
        for seg, txt in zip(segments, translated_texts)
    ]
    return TranslationResult(es_segments, translated=True, provider=provider.name)


def _translate_batch(chunk: list[Segment], provider: AIProvider, offset: int) -> list[str]:
    payload = {"segments": [{"i": i, "text": s.clean_text()} for i, s in enumerate(chunk)]}
    user = (
        "Traduce al espanol estos segmentos de una transcripcion. "
        "Conserva timestamps implicitos por el indice 'i'.\n\n"
        + json.dumps(payload, ensure_ascii=False)
    )
    try:
        raw = provider.complete(_SYSTEM, user, want_json=True, max_tokens=4096)
        data = extract_json(raw)
        items = data.get("segments", []) if isinstance(data, dict) else []
        by_index = {int(it.get("i", k)): str(it.get("text", "")) for k, it in enumerate(items)}
        result = [by_index.get(i, "") for i in range(len(chunk))]
    except AIAuthError:
        raise  # sin clave valida no tiene sentido seguir intentando
    except Exception as e:  # noqa: BLE001 - degradamos a traduccion 1 a 1
        log.warning("Traduccion por lote fallo (%s). Reintento segmento a segmento.", e)
        result = [_translate_single(s, provider) for s in chunk]

    # rellenar huecos que hayan quedado vacios
    for i, txt in enumerate(result):
        if not txt.strip():
            result[i] = _translate_single(chunk[i], provider)
    return result


def _translate_single(seg: Segment, provider: AIProvider) -> str:
    text = seg.clean_text()
    if not text:
        return ""
    user = (
        "Traduce esta unica linea al espanol siguiendo las reglas. "
        'Responde SOLO JSON: {"segments":[{"i":0,"text":"..."}]}\n\n'
        + json.dumps({"segments": [{"i": 0, "text": text}]}, ensure_ascii=False)
    )
    try:
        data = extract_json(provider.complete(_SYSTEM, user, want_json=True, max_tokens=1024))
        return str(data["segments"][0]["text"]).strip() or text
    except AIAuthError:
        raise
    except Exception as e:  # noqa: BLE001
        log.warning("No se pudo traducir un segmento; se deja el original. (%s)", e)
        return text
