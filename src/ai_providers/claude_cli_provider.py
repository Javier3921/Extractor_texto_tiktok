"""Proveedor Claude mediante el CLI de Claude Code (`claude -p`, modo no
interactivo), usando la sesion ya autenticada en el equipo (suscripcion de
Claude): no necesita ANTHROPIC_API_KEY ni paga por token.

Decisiones (validadas contra el CLI real, v2.1.x):
  1. El contenido (transcripcion, posiblemente larga) va por stdin, no en la
     linea de comandos: evita el limite de longitud de linea de Windows.
  2. `--system-prompt` reemplaza el prompt de sistema por defecto de Claude
     Code (el de un agente de programacion) por el nuestro.
  3. `--json-schema` fuerza la salida estructurada: sin el, `claude -p` tiende
     a responder como asistente conversacional (Markdown, aclaraciones)
     aunque el prompt pida "solo JSON". Por eso el proveedor declara
     `supports_json_schema` y traductor/analizador le pasan su esquema.
  4. `--tools ""` deshabilita todas las herramientas: no se necesitan y asi no
     hay solicitudes de permisos en modo no interactivo (ni forma de que una
     inyeccion de prompts en la transcripcion ejecute nada).
  5. Se ejecuta con el directorio temporal del sistema como cwd, para que el
     CLI no cargue el CLAUDE.md de este proyecto como contexto.
  6. En Windows, `npm` instala un shim `claude.cmd` que habria que ejecutar via
     `cmd.exe /c`, y cmd.exe corrompe en silencio los argumentos con saltos de
     linea. Se localiza el `claude.exe` real que hay detras del shim y se
     invoca directamente; solo si no existe se cae a `cmd.exe /c` colapsando
     el system prompt a una linea.
"""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

from src.ai_providers.base import (AIAuthError, AIOverloadedError, AIProvider,
                                   AIProviderError, AIRateLimitError)
from src.utils import get_logger

log = get_logger()

# Ubicacion del ejecutable real respecto al shim de npm (claude.cmd).
_NPM_EXE = Path("node_modules") / "@anthropic-ai" / "claude-code" / "bin" / "claude.exe"
_IS_WINDOWS = os.name == "nt"

_USER_PROMPT = ("Procesa el contenido recibido por la entrada estandar siguiendo "
                "estrictamente las instrucciones del sistema.")

_AUTH_HINTS = ("not logged in", "log in", "login", "authenticat", "oauth",
               "invalid api key", "credential")
_RATE_HINTS = ("usage limit", "rate limit", "limit reached", "429", "quota")
_OVERLOAD_HINTS = ("overloaded", "529", "503", "unavailable")


def resolve_cli(cli_cmd: str) -> tuple[str, bool]:
    """Devuelve (ruta_ejecutable, necesita_cmd_exe). Lanza AIAuthError si no
    se encuentra el CLI (fallo de configuracion: no tiene sentido reintentar)."""
    found = shutil.which(cli_cmd) or (cli_cmd if Path(cli_cmd).is_file() else None)
    if not found:
        raise AIAuthError(
            f"No se encontro el CLI de Claude Code ('{cli_cmd}'). Instalalo con "
            "`npm install -g @anthropic-ai/claude-code`, inicia sesion ejecutando "
            "`claude` una vez, o define CLAUDE_CLI_CMD en .env con la ruta completa."
        )
    path = Path(found)
    if _IS_WINDOWS and path.suffix.lower() != ".exe":
        real_exe = path.parent / _NPM_EXE
        if real_exe.is_file():
            return str(real_exe), False
        if path.suffix.lower() in (".cmd", ".bat"):
            return str(path), True
    return str(path), False


class ClaudeCliProvider(AIProvider):
    name = "claude_cli"
    supports_json_schema = True
    # Cada intento lanza un proceso nuevo (varios segundos): pocos reintentos.
    max_retries = 2
    retry_base_delay = 5.0

    def __init__(self, model: str, *, cli_cmd: str = "claude", timeout: float = 600):
        super().__init__("n/a", model)
        self._exe, self._via_cmd = resolve_cli(cli_cmd)
        self._timeout = timeout
        self._cwd = tempfile.gettempdir()

    def _build_cmd(self, system: str, json_schema: dict | None) -> list[str]:
        if self._via_cmd:
            # cmd.exe vuelve a parsear la linea completa: sin saltos de linea.
            system = " ".join(system.split())
        cmd = [self._exe, "-p", _USER_PROMPT,
               "--system-prompt", system,
               "--output-format", "json",
               "--tools", "",
               "--no-session-persistence"]
        if self.model:
            cmd += ["--model", self.model]
        if json_schema is not None:
            cmd += ["--json-schema", json.dumps(json_schema, ensure_ascii=False)]
        if self._via_cmd:
            cmd = ["cmd.exe", "/c"] + cmd
        return cmd

    def _complete_raw(self, system: str, user: str, want_json: bool, max_tokens: int,
                      json_schema: dict | None = None) -> str:
        # max_tokens no tiene equivalente en el CLI; se ignora.
        cmd = self._build_cmd(system, json_schema if want_json else None)
        try:
            proc = subprocess.run(
                cmd, input=user, capture_output=True, text=True, encoding="utf-8",
                errors="replace", timeout=self._timeout, cwd=self._cwd,
            )
        except FileNotFoundError as e:
            raise AIAuthError(f"{self.name}: no se pudo ejecutar '{self._exe}'.") from e
        except subprocess.TimeoutExpired as e:
            raise AIProviderError(
                f"{self.name}: el CLI tardo mas de {self._timeout:.0f}s y se cancelo "
                "(ajusta CLAUDE_CLI_TIMEOUT en .env)."
            ) from e

        stdout = (proc.stdout or "").strip()
        wrapper = None
        try:
            wrapper = json.loads(stdout) if stdout else None
        except json.JSONDecodeError:
            pass

        is_error = proc.returncode != 0 or (isinstance(wrapper, dict)
                                            and wrapper.get("is_error"))
        if is_error:
            detail = ""
            if isinstance(wrapper, dict):
                detail = str(wrapper.get("result") or wrapper.get("subtype") or "")
            detail = (detail or proc.stderr or stdout or "").strip()[-800:]
            raise _classify_error(self.name, proc.returncode, detail)

        if isinstance(wrapper, dict):
            structured = wrapper.get("structured_output")
            if isinstance(structured, (dict, list)):
                return json.dumps(structured, ensure_ascii=False)
            text = str(wrapper.get("result") or "")
        else:
            text = stdout  # version del CLI sin envoltorio JSON: texto tal cual
        if not text.strip():
            raise AIProviderError(f"{self.name}: respuesta vacia del CLI.")
        return text


def _classify_error(name: str, returncode: int, detail: str) -> AIProviderError:
    low = detail.lower()
    if any(h in low for h in _AUTH_HINTS):
        return AIAuthError(
            f"{name}: el CLI de Claude Code no tiene una sesion valida. Ejecuta "
            f"`claude` en una terminal e inicia sesion. Detalle: {detail}"
        )
    if any(h in low for h in _RATE_HINTS):
        return AIRateLimitError(f"{name}: limite de uso de Claude alcanzado. Detalle: {detail}")
    if any(h in low for h in _OVERLOAD_HINTS):
        return AIOverloadedError(f"{name}: el servicio de Claude esta sobrecargado (temporal).")
    return AIProviderError(f"{name}: el CLI devolvio un error (codigo {returncode}): {detail}")
