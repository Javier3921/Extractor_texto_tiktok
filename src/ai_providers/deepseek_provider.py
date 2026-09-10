"""Proveedor DeepSeek.

La API de DeepSeek es compatible con la de OpenAI, asi que reutilizamos el
mismo SDK cambiando unicamente `base_url`.
"""
from __future__ import annotations

from src.ai_providers.openai_provider import OpenAIProvider


class DeepSeekProvider(OpenAIProvider):
    name = "deepseek"
    base_url = "https://api.deepseek.com"
