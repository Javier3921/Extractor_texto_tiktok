"""Fabrica de proveedores de IA.

    from src.ai_providers import get_provider
    provider = get_provider("gemini", cfg)
    texto = provider.complete(system, user)
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from src.ai_providers.base import (AIAuthError, AIOverloadedError, AIProvider,
                                   AIProviderError, AIRateLimitError)
from src.ai_providers.mock_provider import (MARK_ANALYZE, MARK_TRANSLATE,
                                            MockProvider)

if TYPE_CHECKING:  # evita import circular en runtime
    from config import Config

__all__ = [
    "get_provider", "AIProvider", "AIProviderError", "AIAuthError",
    "AIRateLimitError", "AIOverloadedError", "MARK_ANALYZE", "MARK_TRANSLATE",
]


def get_provider(name: str, cfg: "Config", *, timeout: float | None = None) -> AIProvider:
    """Devuelve una instancia lista para usar del proveedor pedido."""
    name = (name or "").lower()
    model = cfg.ai_model or _default_model(name)

    if name == "mock":
        return MockProvider(model=model)
    if name == "openai":
        from src.ai_providers.openai_provider import OpenAIProvider
        return OpenAIProvider(cfg.openai_api_key, model)
    if name == "gemini":
        from src.ai_providers.gemini_provider import GeminiProvider
        return GeminiProvider(cfg.gemini_api_key, model, timeout=timeout)
    if name == "deepseek":
        from src.ai_providers.deepseek_provider import DeepSeekProvider
        return DeepSeekProvider(cfg.deepseek_api_key, model)
    raise AIProviderError(f"Proveedor de IA desconocido: {name!r}")


def _default_model(name: str) -> str:
    from config import DEFAULT_AI_MODELS
    return DEFAULT_AI_MODELS.get(name, "")
