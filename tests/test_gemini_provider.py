"""Tests del proveedor Gemini: clasificacion de errores del SDK, autocambio
de modelo retirado y timeout de red, todo sin llamadas reales a la API
(se sustituye `client.models.generate_content` por un doble de prueba).
"""
from __future__ import annotations

import pytest

from src.ai_providers.base import (AIAuthError, AIOverloadedError, AIProviderError,
                                   AIRateLimitError)
from src.ai_providers.gemini_provider import GeminiProvider


def _provider(**kw) -> GeminiProvider:
    return GeminiProvider(api_key="AIzaFakeKeyForTests1234567890", model="gemini-3.6-flash", **kw)


class _FakeResponse:
    def __init__(self, text: str):
        self.text = text


class _FakeAPIError(Exception):
    def __init__(self, message: str, code: int | None = None):
        super().__init__(message)
        self.code = code


class TestConstruccion:
    def test_requiere_api_key(self):
        with pytest.raises(AIAuthError):
            GeminiProvider(api_key="", model="gemini-3.6-flash")

    def test_construye_con_timeout(self):
        # No debe lanzar: el timeout se traduce a http_options internamente.
        p = _provider(timeout=15)
        assert p.model == "gemini-3.6-flash"

    def test_construye_sin_timeout(self):
        p = _provider(timeout=None)
        assert p.model == "gemini-3.6-flash"


class TestClasificacionDeErrores:
    def test_error_401_es_auth(self, monkeypatch):
        p = _provider()
        p.max_retries = 1  # no reintentar en el test

        def boom(**_kw):
            raise _FakeAPIError("permission denied", code=401)

        monkeypatch.setattr(p._client.models, "generate_content", boom)
        with pytest.raises(AIAuthError):
            p.complete("sys", "user")

    def test_error_api_key_en_mensaje_es_auth(self, monkeypatch):
        p = _provider()
        p.max_retries = 1

        def boom(**_kw):
            raise _FakeAPIError("API key not valid")

        monkeypatch.setattr(p._client.models, "generate_content", boom)
        with pytest.raises(AIAuthError):
            p.complete("sys", "user")

    def test_error_429_es_rate_limit(self, monkeypatch):
        p = _provider()
        p.max_retries = 1

        def boom(**_kw):
            raise _FakeAPIError("resource exhausted", code=429)

        monkeypatch.setattr(p._client.models, "generate_content", boom)
        with pytest.raises(AIRateLimitError):
            p.complete("sys", "user")

    def test_error_generico_es_provider_error(self, monkeypatch):
        p = _provider()
        p.max_retries = 1

        def boom(**_kw):
            raise _FakeAPIError("internal server error", code=500)

        monkeypatch.setattr(p._client.models, "generate_content", boom)
        with pytest.raises(AIProviderError):
            p.complete("sys", "user")

    def test_auth_error_no_reintenta(self, monkeypatch):
        p = _provider()
        p.max_retries = 5
        calls = {"n": 0}

        def boom(**_kw):
            calls["n"] += 1
            raise _FakeAPIError("unauthenticated", code=401)

        monkeypatch.setattr(p._client.models, "generate_content", boom)
        with pytest.raises(AIAuthError):
            p.complete("sys", "user")
        assert calls["n"] == 1


class TestSobrecargaTransitoria:
    def test_503_es_overloaded(self, monkeypatch):
        p = _provider()
        p.max_retries = 1

        def boom(**_kw):
            raise _FakeAPIError("UNAVAILABLE", code=503)

        monkeypatch.setattr(p._client.models, "generate_content", boom)
        with pytest.raises(AIOverloadedError):
            p.complete("sys", "user")

    def test_high_demand_sin_codigo_es_overloaded(self, monkeypatch):
        p = _provider()
        p.max_retries = 1

        def boom(**_kw):
            raise _FakeAPIError(
                "This model is currently experiencing high demand. "
                "Please try again later."
            )

        monkeypatch.setattr(p._client.models, "generate_content", boom)
        with pytest.raises(AIOverloadedError):
            p.complete("sys", "user")

    def test_reintenta_con_backoff_y_se_recupera(self, monkeypatch):
        import time as time_module
        monkeypatch.setattr(time_module, "sleep", lambda _s: None)
        p = _provider()  # max_retries por defecto (4): debe alcanzar para recuperarse
        calls = {"n": 0}

        def fake_generate(*, model, contents, config):
            calls["n"] += 1
            if calls["n"] < 3:
                raise _FakeAPIError("high demand, please try again later", code=503)
            return _FakeResponse("ok")

        monkeypatch.setattr(p._client.models, "generate_content", fake_generate)
        assert p.complete("sys", "user") == "ok"
        assert calls["n"] == 3

    def test_agota_reintentos_y_propaga_overloaded(self, monkeypatch):
        import time as time_module
        monkeypatch.setattr(time_module, "sleep", lambda _s: None)
        p = _provider()
        p.max_retries = 2

        def boom(**_kw):
            raise _FakeAPIError("UNAVAILABLE", code=503)

        monkeypatch.setattr(p._client.models, "generate_content", boom)
        with pytest.raises(AIOverloadedError):
            p.complete("sys", "user")


class TestAutocambioDeModelo:
    def test_modelo_retirado_cambia_al_sustituto(self, monkeypatch):
        p = _provider()
        p.max_retries = 1
        calls = {"n": 0}

        def fake_generate(*, model, contents, config):
            calls["n"] += 1
            if calls["n"] == 1:
                raise _FakeAPIError(
                    "models/gemini-3.6-flash is not found. Use models/gemini-4.0-flash",
                    code=404,
                )
            return _FakeResponse("ok")

        monkeypatch.setattr(p._client.models, "generate_content", fake_generate)
        result = p.complete("sys", "user")
        assert result == "ok"
        assert p.model == "gemini-4.0-flash"
        assert calls["n"] == 2

    def test_modelo_no_encontrado_sin_sustituto_falla(self, monkeypatch):
        p = _provider()
        p.max_retries = 1

        def boom(**_kw):
            raise _FakeAPIError("model xyz is not found", code=404)

        monkeypatch.setattr(p._client.models, "generate_content", boom)
        with pytest.raises(AIProviderError):
            p.complete("sys", "user")

    def test_no_reintenta_el_switch_dos_veces(self, monkeypatch):
        # Si el sustituto TAMBIEN esta retirado, no debe entrar en bucle:
        # solo se permite un cambio de modelo por llamada.
        p = _provider()
        p.max_retries = 1
        calls = {"n": 0}

        def boom(**_kw):
            calls["n"] += 1
            raise _FakeAPIError(
                "models/gemini-3.6-flash is not found. Use models/gemini-4.0-flash",
                code=404,
            )

        monkeypatch.setattr(p._client.models, "generate_content", boom)
        with pytest.raises(AIProviderError):
            p.complete("sys", "user")
        assert calls["n"] == 2  # 1 intento original + 1 con el modelo sustituto


class TestRespuestaVacia:
    def test_respuesta_sin_texto_falla(self, monkeypatch):
        p = _provider()
        p.max_retries = 1

        monkeypatch.setattr(p._client.models, "generate_content",
                            lambda **_kw: _FakeResponse(""))
        with pytest.raises(AIProviderError):
            p.complete("sys", "user")
