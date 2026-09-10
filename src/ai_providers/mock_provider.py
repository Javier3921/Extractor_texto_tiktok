"""Proveedor simulado (offline, determinista).

Sirve para:
  * ejecutar los tests sin claves ni red,
  * probar el pipeline completo cuando el usuario aun no tiene API key.

No hace analisis real: produce una traduccion "de marcador" y un informe
JSON valido derivado del propio texto de entrada.
"""
from __future__ import annotations

import json
import re

from src.ai_providers.base import AIProvider

# Marcadores que los prompts incluyen para que el mock sepa que se le pide.
MARK_TRANSLATE = "TAREA::TRADUCCION_SEGMENTOS"
MARK_ANALYZE = "TAREA::ANALISIS_TECNICO"

# Terminos tecnicos que NO deben traducirse: el mock los deja intactos.
_TECH_TERMS = [
    "React", "Node.js", "Express", "Python", "JavaScript", "TypeScript",
    "REST API", "GraphQL", "OAuth 2.0", "OAuth", "Docker", "Kubernetes",
    "GitHub", "GitLab", "PostgreSQL", "MySQL", "MongoDB", "Redis", "AWS",
    "Azure", "GCP", "Django", "Flask", "FastAPI", "Vue", "Angular", "Next.js",
    "Whisper", "OpenAI", "Gemini", "DeepSeek", "SQL", "HTML", "CSS", "JSON",
    "API", "CLI", "SDK", "CI/CD", "Linux", "Windows", "npm", "pip",
]


class MockProvider(AIProvider):
    name = "mock"

    def __init__(self, api_key: str = "", model: str = "mock-1"):
        super().__init__(api_key or "n/a", model or "mock-1")

    def _complete_raw(self, system: str, user: str, want_json: bool, max_tokens: int) -> str:
        blob = f"{system}\n{user}"
        if MARK_TRANSLATE in blob:
            return self._fake_translation(user)
        if MARK_ANALYZE in blob:
            return self._fake_analysis(user)
        # respuesta generica
        return json.dumps({"resultado": "respuesta simulada", "eco": user[:200]},
                          ensure_ascii=False)

    # ------------------------------------------------------------------
    def _fake_translation(self, user: str) -> str:
        """Espera en `user` un JSON {"segments":[{"i":0,"text":"..."}]}."""
        try:
            data = json.loads(_first_json_block(user))
            segments = data.get("segments", [])
        except Exception:
            segments = []
        out = []
        for seg in segments:
            txt = str(seg.get("text", ""))
            out.append({"i": seg.get("i", len(out)), "text": _es_marker(txt)})
        return json.dumps({"segments": out}, ensure_ascii=False)

    # ------------------------------------------------------------------
    def _fake_analysis(self, user: str) -> str:
        found = sorted({t for t in _TECH_TERMS if re.search(re.escape(t), user, re.I)})
        snippet = " ".join(user.split())[:400]
        report = {
            "title": "Analisis simulado del contenido",
            "original_language": _guess_lang(user),
            "translated_to_spanish": "TRANSCRIPCION ORIGINAL" in user.upper(),
            "executive_summary": (
                "[SIMULADO] Este informe lo ha generado el proveedor 'mock', sin IA real. "
                "El video trata sobre: " + snippet[:180] + "..."
            ),
            "detailed_explanation": (
                "[SIMULADO] Explicacion no disponible sin un proveedor de IA real. "
                "Texto analizado (extracto): " + snippet
            ),
            "technologies": [{"category": "Mencionada", "name": t} for t in found]
            or ["No se identificaron tecnologias de forma explicita."],
            "technical_concepts": found[:5] or ["No se identificaron conceptos concretos."],
            "architecture": "No se puede determinar con certeza a partir del contenido disponible.",
            "code_analysis": "No se observo codigo en el contenido proporcionado (analisis simulado).",
            "best_practices": ["No se pueden evaluar buenas practicas en modo simulado."],
            "risks": ["No se pueden evaluar riesgos en modo simulado."],
            "recommendations": [
                "Recomendacion: configura un proveedor de IA real (Gemini tiene capa gratuita) "
                "para obtener un analisis tecnico completo."
            ],
            "difficulty": "Intermedio",
            "applications": ["Uso general de las tecnologias mencionadas: " + ", ".join(found)]
            if found else ["No determinado."],
            "conclusion": (
                "[SIMULADO] El pipeline funciona de extremo a extremo. Para un informe real, "
                "define AI_PROVIDER y su API key en .env."
            ),
        }
        return json.dumps(report, ensure_ascii=False)


# ----------------------------------------------------------------------
def _es_marker(text: str) -> str:
    """Devuelve el texto 'traducido' conservando los terminos tecnicos."""
    t = text.strip()
    if not t:
        return t
    return "[ES] " + t


def _first_json_block(text: str) -> str:
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start:end + 1]
    return "{}"


def _guess_lang(text: str) -> str:
    low = text.lower()
    if any(w in low for w in (" the ", " and ", " with ", " we ", " to build ")):
        return "English"
    if any(w in low for w in (" que ", " para ", " con ", " vamos ", " el ", " la ")):
        return "Espanol"
    return "Desconocido"
