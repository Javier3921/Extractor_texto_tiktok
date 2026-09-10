"""Analisis tecnico del contenido mediante IA.

Entrada principal: la transcripcion EN ESPANOL. Si hubo traduccion, se adjunta
tambien la original para que el modelo verifique los terminos tecnicos.

Reglas anti-alucinacion (secciones 16, 17, 33 del prompt):
  * Distinguir informacion explicita / inferencia / recomendacion.
  * No inventar tecnologias, arquitectura ni codigo.
  * Si no hay evidencia suficiente: decir que no se puede determinar.

Salida: JSON con el esquema de la seccion 18 -> AnalysisReport.
"""
from __future__ import annotations

import json
from typing import Any

from src.ai_providers.base import AIAuthError, AIProvider, AIProviderError
from src.ai_providers.mock_provider import MARK_ANALYZE
from src.models import AnalysisReport
from src.utils import JSONParseError, extract_json, get_logger

log = get_logger()

_SCHEMA_KEYS_STR = ("title", "original_language", "executive_summary",
                    "detailed_explanation", "architecture", "code_analysis",
                    "difficulty", "conclusion")
_SCHEMA_KEYS_LIST = ("technologies", "technical_concepts", "best_practices",
                     "risks", "recommendations", "applications")

_SYSTEM = f"""{MARK_ANALYZE}
Eres un analista tecnico senior. Analizas la transcripcion de un video tecnico
y produces un informe RIGUROSO en ESPANOL.

PRINCIPIOS OBLIGATORIOS (muy importante):
- Analiza SOLO lo que aparece en el contenido o lo que se puede inferir de forma
  razonable. NO inventes tecnologias, frameworks, librerias, bases de datos,
  APIs, servicios cloud, arquitecturas ni codigo que no esten presentes.
- Distingue con claridad tres niveles:
    * Informacion explicita: dicha o mostrada directamente en el video.
    * Inferencia tecnica: deduccion razonable a partir del contenido
      (prefijala con "Inferencia tecnica:").
    * Recomendacion: propuesta tuya, no algo observado
      (prefijala con "Recomendacion:").
- Si no hay evidencia suficiente para una seccion, escribe exactamente:
  "No se puede determinar con certeza a partir del contenido disponible."
- Todo el texto en espanol. CONSERVA sin traducir los nombres tecnicos
  (React, Node.js, REST API, OAuth 2.0, Docker, Kubernetes, PostgreSQL, ...).

FORMATO DE SALIDA: responde UNICAMENTE con un objeto JSON valido, sin texto
alrededor, con EXACTAMENTE estas claves:
{{
  "title": "",
  "original_language": "",
  "translated_to_spanish": true,
  "executive_summary": "",
  "detailed_explanation": "",
  "technologies": [],
  "technical_concepts": [],
  "architecture": "",
  "code_analysis": "",
  "best_practices": [],
  "risks": [],
  "recommendations": [],
  "difficulty": "",
  "applications": [],
  "conclusion": ""
}}
- "technologies": lista de objetos {{"category": "...", "name": "..."}} donde
  category es una de: lenguaje, framework, libreria, base de datos, API,
  plataforma, herramienta, cloud, sistema operativo, devops, ia/ml, otro.
- "difficulty": uno de: "Basico", "Intermedio", "Avanzado", "Experto"
  (anade una frase justificando por que).
"""


def analyze_content(*, spanish_text: str, original_text: str | None,
                    translated: bool, original_language: str,
                    title: str, url: str, duration_str: str,
                    provider: AIProvider) -> AnalysisReport:
    user = _build_user_prompt(spanish_text, original_text, translated,
                              original_language, title, url, duration_str)
    log.info("Enviando contenido a %s para analisis tecnico...", provider.name)

    try:
        raw = provider.complete(_SYSTEM, user, want_json=True, max_tokens=6000)
        try:
            data = extract_json(raw)
        except JSONParseError:
            log.warning("Respuesta de IA no era JSON valido. Reintento con recordatorio.")
            raw = provider.complete(
                _SYSTEM,
                user + "\n\nIMPORTANTE: responde EXCLUSIVAMENTE con el objeto JSON, "
                       "sin ```, sin explicaciones.",
                want_json=True, max_tokens=6000,
            )
            try:
                data = extract_json(raw)
            except JSONParseError:
                log.error("La IA no devolvio JSON utilizable. Se genera informe de reserva.")
                return _fallback_report(raw, original_language, translated, title)
    except AIAuthError:
        # sin credenciales validas no tiene sentido continuar
        raise
    except AIProviderError as e:
        # el proveedor fallo (rate limit agotado, modelo caido, red...): no se
        # tira todo el procesamiento, se emite un informe degradado con el motivo
        log.error("El analisis con IA fallo: %s. Se genera informe degradado.", e)
        return _provider_error_report(str(e), original_language, translated, title)

    return _coerce_report(data, original_language, translated, title)


# --------------------------------------------------------------------------
def _build_user_prompt(spanish_text, original_text, translated, original_language,
                       title, url, duration_str) -> str:
    parts = [
        "METADATOS DEL VIDEO",
        f"- Titulo: {title or '(desconocido)'}",
        f"- URL/Origen: {url or '(no aplica)'}",
        f"- Idioma original: {original_language}",
        f"- Duracion: {duration_str}",
        f"- Traduccion realizada: {'si' if translated else 'no'}",
        "",
        "=== TRANSCRIPCION EN ESPANOL (contenido principal a analizar) ===",
        spanish_text.strip() or "(vacio)",
    ]
    if translated and original_text and original_text.strip():
        parts += [
            "",
            "=== TRANSCRIPCION ORIGINAL (solo para verificar terminos tecnicos) ===",
            original_text.strip(),
        ]
    parts += [
        "",
        "Genera ahora el informe JSON siguiendo TODAS las reglas del sistema.",
    ]
    return "\n".join(parts)


def _coerce_report(data: Any, original_language: str, translated: bool,
                   title: str) -> AnalysisReport:
    if not isinstance(data, dict):
        return _fallback_report(str(data), original_language, translated, title)

    rep = AnalysisReport()
    warnings: list[str] = []

    for key in _SCHEMA_KEYS_STR:
        val = data.get(key, "")
        if isinstance(val, (list, dict)):
            val = json.dumps(val, ensure_ascii=False)
        setattr(rep, key, str(val).strip())

    for key in _SCHEMA_KEYS_LIST:
        val = data.get(key, [])
        if isinstance(val, str):
            val = [val] if val.strip() else []
        elif not isinstance(val, list):
            val = [str(val)]
        setattr(rep, key, val)

    tt = data.get("translated_to_spanish", translated)
    rep.translated_to_spanish = bool(tt) if isinstance(tt, bool) else translated

    if not rep.original_language:
        rep.original_language = original_language
    if not rep.title:
        rep.title = title or "Informe tecnico del video"

    for key in _SCHEMA_KEYS_STR:
        if not getattr(rep, key):
            setattr(rep, key,
                    "No se puede determinar con certeza a partir del contenido disponible.")
            warnings.append(key)

    if warnings:
        rep.parse_warning = ("Campos que la IA dejo vacios y se completaron con el "
                             "texto por defecto: " + ", ".join(warnings))
    return rep


def _fallback_report(raw_text: str, original_language: str, translated: bool,
                     title: str) -> AnalysisReport:
    raw_text = (raw_text or "").strip()
    return AnalysisReport(
        title=title or "Informe tecnico (formato degradado)",
        original_language=original_language,
        translated_to_spanish=translated,
        executive_summary=(
            "La IA no devolvio un JSON con el formato esperado. A continuacion se "
            "incluye su respuesta en bruto para no perder informacion."
        ),
        detailed_explanation=raw_text[:6000] or "(respuesta vacia)",
        architecture="No se puede determinar con certeza a partir del contenido disponible.",
        code_analysis="No se puede determinar con certeza a partir del contenido disponible.",
        difficulty="No determinado",
        conclusion=(
            "Informe generado en modo degradado por un error de formato en la "
            "respuesta de la IA. Reintenta el procesamiento."
        ),
        parse_warning="La respuesta de la IA no se pudo parsear como JSON.",
    )


def _provider_error_report(reason: str, original_language: str, translated: bool,
                           title: str) -> AnalysisReport:
    """Informe minimo cuando el proveedor de IA no responde (rate limit, modelo
    caido, red...). El TXT con la transcripcion ya se genero antes; aqui se
    produce un PDF que deja constancia del fallo en vez de abortar todo."""
    nd = "No se pudo generar: el proveedor de IA no completo la peticion."
    return AnalysisReport(
        title=title or "Informe tecnico (analisis no disponible)",
        original_language=original_language,
        translated_to_spanish=translated,
        executive_summary=(
            "El analisis tecnico automatico no pudo completarse porque el proveedor "
            "de IA devolvio un error. La transcripcion (archivo .txt) si se genero "
            "correctamente. Motivo: " + reason
        ),
        detailed_explanation=nd,
        architecture=nd,
        code_analysis=nd,
        difficulty="No determinado",
        applications=[nd],
        recommendations=[
            "Reintenta el procesamiento mas tarde, o cambia de proveedor/modelo "
            "(AI_PROVIDER / AI_MODEL en .env).",
        ],
        conclusion=(
            "Informe incompleto: falta el analisis tecnico por un fallo del proveedor "
            "de IA. La transcripcion en el .txt no se ve afectada."
        ),
        parse_warning="Analisis omitido por error del proveedor de IA: " + reason,
    )
