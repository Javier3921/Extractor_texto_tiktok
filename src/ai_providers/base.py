"""Interfaz comun de los proveedores de IA.

Cambiar de proveedor NO debe requerir tocar el resto del programa: todos
exponen `complete()` y `complete_json()`.
"""
from __future__ import annotations

import abc
import time
from typing import Any

from src.utils import ExtractorError, extract_json, get_logger

log = get_logger()


class AIProviderError(ExtractorError):
    """Error de un proveedor de IA, ya traducido a lenguaje de usuario."""


class AIAuthError(AIProviderError):
    """Falta la clave o es invalida."""


class AIRateLimitError(AIProviderError):
    """Se alcanzo el limite de peticiones del proveedor."""


class AIOverloadedError(AIProviderError):
    """El servicio esta temporalmente sobrecargado (503/UNAVAILABLE, alta
    demanda). Es transitorio: el proveedor recomienda reintentar mas tarde."""


class AIProvider(abc.ABC):
    """Base de todos los proveedores."""

    name: str = "base"
    max_retries: int = 4
    retry_base_delay: float = 4.0

    def __init__(self, api_key: str, model: str):
        self.api_key = api_key
        self.model = model

    # -- API publica -----------------------------------------------------
    @abc.abstractmethod
    def _complete_raw(self, system: str, user: str, want_json: bool, max_tokens: int) -> str:
        """Implementacion concreta de cada proveedor. Devuelve el texto de la respuesta."""

    def complete(self, system: str, user: str, *, want_json: bool = False,
                 max_tokens: int = 4096) -> str:
        """Llama al modelo con reintentos ante rate-limit / errores transitorios."""
        last_err: Exception | None = None
        for attempt in range(1, self.max_retries + 1):
            try:
                return self._complete_raw(system, user, want_json, max_tokens)
            except AIAuthError:
                raise
            except (AIRateLimitError, AIOverloadedError) as e:
                last_err = e
                if attempt == self.max_retries:
                    break
                delay = self.retry_base_delay * attempt
                log.warning("%s: %s (reintento %d/%d en %.0fs)",
                            self.name, e, attempt, self.max_retries, delay)
                time.sleep(delay)
            except AIProviderError as e:
                last_err = e
                if attempt == self.max_retries:
                    break
                time.sleep(self.retry_base_delay)
            except Exception as e:  # noqa: BLE001 - lo normalizamos
                last_err = AIProviderError(f"{self.name}: error inesperado: {e}")
                if attempt == self.max_retries:
                    break
                time.sleep(self.retry_base_delay)
        raise last_err if isinstance(last_err, AIProviderError) else \
            AIProviderError(f"{self.name}: fallo tras {self.max_retries} intentos: {last_err}")

    def complete_json(self, system: str, user: str, *, max_tokens: int = 4096) -> Any:
        """Como complete() pero exige y parsea una respuesta JSON."""
        text = self.complete(system, user, want_json=True, max_tokens=max_tokens)
        return extract_json(text)

    def describe(self) -> str:
        return f"{self.name} ({self.model})"
