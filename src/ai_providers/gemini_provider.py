"""Proveedor Google Gemini mediante el SDK unificado `google-genai`.

(El antiguo `google-generativeai` quedo deprecado en noviembre de 2025.)
"""
from __future__ import annotations

import logging
import re

from src.ai_providers.base import (AIAuthError, AIProvider, AIProviderError,
                                   AIRateLimitError)
from src.utils import get_logger

log = get_logger()

# El SDK de google-genai es muy verboso con un aviso sobre AFC que no aplica aqui.
logging.getLogger("google_genai").setLevel(logging.ERROR)
logging.getLogger("google_genai.models").setLevel(logging.ERROR)

_MODEL_MOVED = re.compile(r"use\s+models/([A-Za-z0-9.\-]+)", re.IGNORECASE)


class GeminiProvider(AIProvider):
    name = "gemini"

    def __init__(self, api_key: str, model: str, timeout: float | None = None):
        super().__init__(api_key, model)
        if not api_key:
            raise AIAuthError(
                "Falta GEMINI_API_KEY en el archivo .env. "
                "Consigue una clave gratuita en https://aistudio.google.com/apikey"
            )
        try:
            from google import genai
            from google.genai import types
        except ImportError as e:  # pragma: no cover
            raise AIProviderError(
                "Falta el paquete 'google-genai' (pip install google-genai)."
            ) from e
        self._genai = genai
        # Sin esto una llamada colgada se queda esperando indefinidamente
        # (el SDK no tiene timeout por defecto): usamos NETWORK_TIMEOUT del .env.
        http_options = types.HttpOptions(timeout=int(timeout * 1000)) if timeout else None
        self._client = genai.Client(api_key=api_key, http_options=http_options)

    def _complete_raw(self, system: str, user: str, want_json: bool, max_tokens: int,
                      _allow_model_switch: bool = True) -> str:
        from google.genai import types

        config = types.GenerateContentConfig(
            system_instruction=system,
            temperature=0.2,
            max_output_tokens=max_tokens,
            response_mime_type="application/json" if want_json else "text/plain",
        )
        try:
            resp = self._client.models.generate_content(
                model=self.model,
                contents=user,
                config=config,
            )
        except Exception as e:  # el SDK lanza APIError con .code
            msg = str(e).lower()
            code = getattr(e, "code", None) or getattr(e, "status_code", None)
            if code in (401, 403) or "api key" in msg or "permission" in msg or "unauthenticated" in msg:
                raise AIAuthError(f"{self.name}: clave de API rechazada o sin permisos.") from e
            if code == 429 or "resource_exhausted" in msg or "quota" in msg or "rate" in msg:
                raise AIRateLimitError(
                    f"{self.name}: limite/cuota alcanzado (la capa gratuita tiene limites)."
                ) from e
            # Modelo retirado: la API suele indicar el sustituto ("use models/xxx").
            if (code == 404 or "not_found" in msg or "no longer available" in msg
                    or "is not found" in msg):
                m = _MODEL_MOVED.search(str(e))
                if m and _allow_model_switch and m.group(1) != self.model:
                    new_model = m.group(1)
                    log.warning("%s: el modelo '%s' ya no existe; cambio a '%s'.",
                                self.name, self.model, new_model)
                    self.model = new_model
                    return self._complete_raw(system, user, want_json, max_tokens,
                                              _allow_model_switch=False)
                raise AIProviderError(
                    f"{self.name}: el modelo '{self.model}' no existe o no esta disponible. "
                    f"Define AI_MODEL en .env con un modelo valido. Detalle: {e}"
                ) from e
            raise AIProviderError(f"{self.name}: error de la API: {e}") from e

        text = getattr(resp, "text", None)
        if not text:
            # a veces el texto viene en candidates[0].content.parts[*].text
            try:
                parts = resp.candidates[0].content.parts
                text = "".join(getattr(p, "text", "") for p in parts)
            except Exception:
                text = None
        if not text:
            raise AIProviderError(f"{self.name}: respuesta vacia del modelo.")
        return text
