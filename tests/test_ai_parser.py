import json

import pytest

from src.ai_analyzer import _coerce_report, analyze_content
from src.ai_providers.base import AIProvider
from src.models import AnalysisReport
from src.utils import JSONParseError, extract_json


class TestExtractJson:
    def test_clean_json(self):
        assert extract_json('{"a": 1}') == {"a": 1}

    def test_fenced_json(self):
        assert extract_json('```json\n{"a": 1}\n```') == {"a": 1}

    def test_fenced_without_lang(self):
        assert extract_json('```\n{"a": 2}\n```') == {"a": 2}

    def test_json_with_prose_around(self):
        raw = 'Claro, aqui tienes el informe:\n{"a": 3, "b": [1,2]}\nEspero que ayude.'
        assert extract_json(raw) == {"a": 3, "b": [1, 2]}

    def test_array_json(self):
        assert extract_json('prefix [1, 2, 3] suffix') == [1, 2, 3]

    def test_nested_braces(self):
        raw = 'x {"a": {"b": {"c": 1}}, "d": "}"} y'
        assert extract_json(raw) == {"a": {"b": {"c": 1}}, "d": "}"}

    def test_truncated_raises(self):
        with pytest.raises(JSONParseError):
            extract_json('{"a": 1, "b": [1, 2, 3')

    def test_empty_raises(self):
        with pytest.raises(JSONParseError):
            extract_json("")

    def test_no_json_raises(self):
        with pytest.raises(JSONParseError):
            extract_json("solo texto sin json")


class TestCoerceReport:
    def test_full_dict(self, sample_report_dict):
        rep = _coerce_report(sample_report_dict, "English", True, "T")
        assert isinstance(rep, AnalysisReport)
        assert rep.title.startswith("Construir")
        assert rep.difficulty == "Intermedio"
        assert len(rep.technologies) == 2

    def test_missing_fields_filled(self):
        rep = _coerce_report({"title": "Solo titulo"}, "English", True, "T")
        assert rep.executive_summary.startswith("No se puede determinar")
        assert rep.parse_warning

    def test_string_where_list_expected(self):
        rep = _coerce_report(
            {"risks": "Un unico riesgo como cadena"}, "Espanol", False, "T")
        assert rep.risks == ["Un unico riesgo como cadena"]

    def test_list_where_string_expected(self):
        rep = _coerce_report(
            {"architecture": ["parte 1", "parte 2"]}, "Espanol", False, "T")
        assert isinstance(rep.architecture, str)
        assert "parte 1" in rep.architecture

    def test_non_dict_input_falls_back(self):
        rep = _coerce_report("una cadena", "English", True, "T")
        assert rep.parse_warning


# --- proveedor de prueba parametrizable ---------------------------------
class _ScriptedProvider(AIProvider):
    name = "scripted"

    def __init__(self, responses):
        super().__init__("k", "m")
        self._responses = list(responses)

    def _complete_raw(self, system, user, want_json, max_tokens):
        return self._responses.pop(0)


class TestAnalyzeContent:
    def test_valid_first_try(self, sample_report_dict):
        prov = _ScriptedProvider([json.dumps(sample_report_dict)])
        rep = analyze_content(
            spanish_text="contenido", original_text=None, translated=False,
            original_language="Espanol", title="T", url="u", duration_str="00:30",
            provider=prov,
        )
        assert rep.title.startswith("Construir")

    def test_retry_then_success(self, sample_report_dict):
        prov = _ScriptedProvider(["esto no es json",
                                  "```json\n" + json.dumps(sample_report_dict) + "\n```"])
        rep = analyze_content(
            spanish_text="c", original_text=None, translated=False,
            original_language="Espanol", title="T", url="u", duration_str="00:30",
            provider=prov,
        )
        assert rep.difficulty == "Intermedio"

    def test_double_failure_returns_fallback_report(self):
        prov = _ScriptedProvider(["no json", "sigue sin json"])
        rep = analyze_content(
            spanish_text="c", original_text=None, translated=True,
            original_language="English", title="T", url="u", duration_str="00:30",
            provider=prov,
        )
        assert isinstance(rep, AnalysisReport)
        assert rep.parse_warning
        assert "degradado" in rep.conclusion.lower()


class _RaisingProvider(AIProvider):
    name = "raising"
    max_retries = 1          # sin esperas en los tests
    retry_base_delay = 0.0

    def __init__(self, exc):
        super().__init__("k", "m")
        self._exc = exc

    def _complete_raw(self, system, user, want_json, max_tokens):
        raise self._exc


class TestAnalyzeContentProviderErrors:
    def test_provider_error_returns_degraded_report_not_exception(self):
        from src.ai_providers.base import AIProviderError
        rep = analyze_content(
            spanish_text="c", original_text=None, translated=True,
            original_language="English", title="T", url="u", duration_str="00:30",
            provider=_RaisingProvider(AIProviderError("gemini: modelo caido")),
        )
        assert isinstance(rep, AnalysisReport)
        assert "no pudo completarse" in rep.executive_summary
        assert "modelo caido" in rep.parse_warning

    def test_auth_error_propagates(self):
        from src.ai_providers.base import AIAuthError
        with pytest.raises(AIAuthError):
            analyze_content(
                spanish_text="c", original_text=None, translated=True,
                original_language="English", title="T", url="u", duration_str="00:30",
                provider=_RaisingProvider(AIAuthError("falta la clave")),
            )
