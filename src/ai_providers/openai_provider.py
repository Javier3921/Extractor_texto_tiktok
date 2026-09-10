"""Proveedor OpenAI (ChatGPT) mediante el SDK oficial `openai`."""
from __future__ import annotations

from src.ai_providers.base import (AIAuthError, AIProvider, AIProviderError,
                                   AIRateLimitError)


class OpenAIProvider(AIProvider):
    name = "openai"
    base_url: str | None = None          # DeepSeek reutiliza esta clase con otro base_url

    def __init__(self, api_key: str, model: str):
        super().__init__(api_key, model)
        if not api_key:
            raise AIAuthError(
                f"Falta la clave de API para {self.name}. "
                f"Configura la variable correspondiente en el archivo .env"
            )
        try:
            from openai import OpenAI
        except ImportError as e:  # pragma: no cover
            raise AIProviderError("Falta el paquete 'openai' (pip install openai).") from e
        kwargs = {"api_key": api_key}
        if self.base_url:
            kwargs["base_url"] = self.base_url
        self._client = OpenAI(**kwargs)

    def _complete_raw(self, system: str, user: str, want_json: bool, max_tokens: int) -> str:
        try:
            from openai import (APIConnectionError, APIStatusError,
                                AuthenticationError, RateLimitError)
        except ImportError:  # pragma: no cover
            AuthenticationError = RateLimitError = APIConnectionError = APIStatusError = ()

        kwargs = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.2,
            "max_tokens": max_tokens,
        }
        if want_json:
            kwargs["response_format"] = {"type": "json_object"}

        try:
            resp = self._client.chat.completions.create(**kwargs)
        except AuthenticationError as e:
            raise AIAuthError(f"{self.name}: clave de API rechazada.") from e
        except RateLimitError as e:
            raise AIRateLimitError(f"{self.name}: limite de peticiones alcanzado.") from e
        except APIConnectionError as e:
            raise AIProviderError(f"{self.name}: no se pudo conectar con la API.") from e
        except APIStatusError as e:
            raise AIProviderError(f"{self.name}: la API respondio {e.status_code}.") from e

        choice = (resp.choices or [None])[0]
        content = getattr(getattr(choice, "message", None), "content", None)
        if not content:
            raise AIProviderError(f"{self.name}: respuesta vacia del modelo.")
        return content
