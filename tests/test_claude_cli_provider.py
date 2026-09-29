"""Tests del proveedor claude_cli. Se mockean `shutil.which` y
`subprocess.run`: no se invoca el CLI real ni se necesita sesion de Claude."""
import json
import subprocess
from types import SimpleNamespace

import pytest

from src.ai_providers import claude_cli_provider as mod
from src.ai_providers.base import (AIAuthError, AIOverloadedError, AIProviderError,
                                   AIRateLimitError)
from src.ai_providers.claude_cli_provider import ClaudeCliProvider, resolve_cli


@pytest.fixture
def fake_exe(tmp_path, monkeypatch):
    exe = tmp_path / "claude.exe"
    exe.write_text("")
    monkeypatch.setattr(mod.shutil, "which", lambda _cmd: str(exe))
    return exe


def _provider(monkeypatch, *, stdout="", returncode=0, stderr="", calls=None):
    def fake_run(cmd, **kwargs):
        if calls is not None:
            calls.append((cmd, kwargs))
        return SimpleNamespace(stdout=stdout, stderr=stderr, returncode=returncode)

    monkeypatch.setattr(mod.subprocess, "run", fake_run)
    p = ClaudeCliProvider("sonnet", timeout=5)
    p.retry_base_delay = 0.0
    return p


def _wrapper(**fields):
    return json.dumps({"type": "result", "is_error": False, **fields})


class TestInvocacion:
    def test_structured_output_y_argumentos(self, fake_exe, monkeypatch):
        calls = []
        schema = {"type": "object"}
        p = _provider(monkeypatch, stdout=_wrapper(result="x",
                      structured_output={"segments": [{"i": 0, "text": "hola"}]}),
                      calls=calls)
        out = p.complete("sistema\nmultilinea", "contenido", want_json=True,
                         json_schema=schema)
        assert json.loads(out) == {"segments": [{"i": 0, "text": "hola"}]}

        cmd, kwargs = calls[0]
        assert cmd[0] == str(fake_exe)
        assert cmd[cmd.index("--system-prompt") + 1] == "sistema\nmultilinea"
        assert cmd[cmd.index("--json-schema") + 1] == json.dumps(schema)
        assert cmd[cmd.index("--tools") + 1] == ""
        assert cmd[cmd.index("--model") + 1] == "sonnet"
        assert "--no-session-persistence" in cmd
        # el contenido (no confiable y potencialmente largo) va por stdin
        assert kwargs["input"] == "contenido"
        assert "contenido" not in cmd

    def test_sin_structured_output_usa_result(self, fake_exe, monkeypatch):
        p = _provider(monkeypatch, stdout=_wrapper(result='{"a": 1}'))
        assert p.complete("s", "u") == '{"a": 1}'

    def test_respuesta_vacia(self, fake_exe, monkeypatch):
        p = _provider(monkeypatch, stdout=_wrapper(result=""))
        with pytest.raises(AIProviderError, match="vacia"):
            p.complete("s", "u")

    def test_timeout(self, fake_exe, monkeypatch):
        def boom(cmd, **kw):
            raise subprocess.TimeoutExpired(cmd, 5)
        monkeypatch.setattr(mod.subprocess, "run", boom)
        p = ClaudeCliProvider("sonnet", timeout=5)
        p.retry_base_delay = 0.0
        with pytest.raises(AIProviderError, match="CLAUDE_CLI_TIMEOUT"):
            p.complete("s", "u")


class TestClasificacionDeErrores:
    def test_sin_sesion_es_auth_y_no_reintenta(self, fake_exe, monkeypatch):
        calls = []
        p = _provider(monkeypatch, returncode=1, stdout=_wrapper(
            is_error=True, result="Not logged in · Please run /login"), calls=calls)
        with pytest.raises(AIAuthError):
            p.complete("s", "u")
        assert len(calls) == 1

    def test_limite_de_uso(self, fake_exe, monkeypatch):
        p = _provider(monkeypatch, returncode=1, stderr="Claude usage limit reached")
        with pytest.raises(AIRateLimitError):
            p.complete("s", "u")

    def test_sobrecarga(self, fake_exe, monkeypatch):
        p = _provider(monkeypatch, returncode=1, stderr="API Error: 529 Overloaded")
        with pytest.raises(AIOverloadedError):
            p.complete("s", "u")

    def test_is_error_con_codigo_cero(self, fake_exe, monkeypatch):
        p = _provider(monkeypatch, stdout=_wrapper(is_error=True, result="algo raro"))
        with pytest.raises(AIProviderError, match="algo raro"):
            p.complete("s", "u")


class TestResolverEjecutable:
    def test_cli_no_encontrado_es_auth(self, monkeypatch):
        monkeypatch.setattr(mod.shutil, "which", lambda _cmd: None)
        with pytest.raises(AIAuthError, match="npm install"):
            resolve_cli("claude-inexistente")

    def test_shim_npm_se_sustituye_por_el_exe_real(self, tmp_path, monkeypatch):
        shim = tmp_path / "claude.cmd"
        shim.write_text("")
        real = tmp_path / mod._NPM_EXE
        real.parent.mkdir(parents=True)
        real.write_text("")
        monkeypatch.setattr(mod.shutil, "which", lambda _cmd: str(shim))
        monkeypatch.setattr(mod, "_IS_WINDOWS", True)
        assert resolve_cli("claude") == (str(real), False)

    def test_shim_sin_exe_usa_cmd_y_colapsa_saltos(self, tmp_path, monkeypatch):
        shim = tmp_path / "claude.cmd"
        shim.write_text("")
        monkeypatch.setattr(mod.shutil, "which", lambda _cmd: str(shim))
        monkeypatch.setattr(mod, "_IS_WINDOWS", True)
        calls = []
        p = _provider(monkeypatch, stdout=_wrapper(result="ok"), calls=calls)
        p.complete("linea 1\nlinea 2", "u")
        cmd = calls[0][0]
        assert cmd[:3] == ["cmd.exe", "/c", str(shim)]
        assert cmd[cmd.index("--system-prompt") + 1] == "linea 1 linea 2"
