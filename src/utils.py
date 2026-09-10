"""Utilidades transversales: logging seguro, nombres de archivo, rutas,
resolucion de FFmpeg, parseo de JSON y espacio de trabajo temporal.
"""
from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Iterable, Optional


# --------------------------------------------------------------------------
# Excepciones del dominio
# --------------------------------------------------------------------------
class ExtractorError(Exception):
    """Error controlado y legible para el usuario final."""


class JSONParseError(ExtractorError):
    """No se pudo extraer un JSON valido de la respuesta de la IA."""


# --------------------------------------------------------------------------
# Logging con redaccion de secretos
# --------------------------------------------------------------------------
_SECRET_PATTERNS = [
    re.compile(r"sk-[A-Za-z0-9_\-]{16,}"),
    re.compile(r"AIza[0-9A-Za-z_\-]{20,}"),
    re.compile(r"(?i)(api[_-]?key\"?\s*[:=]\s*\"?)([A-Za-z0-9_\-]{12,})"),
    re.compile(r"Bearer\s+[A-Za-z0-9_\-\.]{16,}"),
]


class SecretFilter(logging.Filter):
    """Sustituye posibles claves/tokens por [REDACTED] en todos los registros."""

    def filter(self, record: logging.LogRecord) -> bool:  # noqa: A003
        try:
            msg = record.getMessage()
        except Exception:
            return True
        redacted = msg
        for pat in _SECRET_PATTERNS:
            redacted = pat.sub(lambda m: _redact_match(m), redacted)
        if redacted != msg:
            record.msg = redacted
            record.args = ()
        return True


def _redact_match(m: re.Match) -> str:
    if m.re.groups >= 2:
        return f"{m.group(1)}[REDACTED]"
    return "[REDACTED]"


def setup_logging(logs_dir: Path, level: int = logging.INFO) -> logging.Logger:
    """Configura el logger raiz del proyecto (consola + archivo diario)."""
    logs_dir = Path(logs_dir)
    logs_dir.mkdir(parents=True, exist_ok=True)
    logfile = logs_dir / f"run_{datetime.now():%Y%m%d}.log"

    logger = logging.getLogger("extractor")
    logger.setLevel(level)
    logger.handlers.clear()
    logger.propagate = False

    fmt = logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s",
                            datefmt="%Y-%m-%d %H:%M:%S")
    secret_filter = SecretFilter()

    fh = logging.FileHandler(logfile, encoding="utf-8")
    fh.setFormatter(fmt)
    fh.addFilter(secret_filter)
    logger.addHandler(fh)

    ch = logging.StreamHandler(sys.stderr)
    ch.setLevel(logging.WARNING)          # la consola de usuario usa print(); aqui solo avisos
    ch.setFormatter(logging.Formatter("[%(levelname)s] %(message)s"))
    ch.addFilter(secret_filter)
    logger.addHandler(ch)

    return logger


def get_logger() -> logging.Logger:
    return logging.getLogger("extractor")


# --------------------------------------------------------------------------
# Nombres de archivo y rutas seguras
# --------------------------------------------------------------------------
_SAFE_CHARS = re.compile(r"[^A-Za-z0-9._ -]+")
_MULTI_DASH = re.compile(r"[-_ ]{2,}")


def sanitize_filename(name: str, max_length: int = 120, default: str = "archivo") -> str:
    """Devuelve un nombre de archivo seguro (sin rutas, sin '..', ASCII simple)."""
    if not name:
        return default
    name = str(name).replace("\\", "-").replace("/", "-")
    name = name.replace("..", "-")
    name = _SAFE_CHARS.sub("-", name)
    name = _MULTI_DASH.sub("-", name).strip(" .-")
    if not name:
        return default
    return name[:max_length].rstrip(" .-") or default


def slugify(text: str, max_length: int = 60) -> str:
    text = sanitize_filename(text, max_length=max_length, default="video")
    return text.replace(" ", "_")


def safe_output_path(base_dir: Path, filename: str) -> Path:
    """Une base_dir + filename garantizando que el resultado queda DENTRO de base_dir."""
    base_dir = Path(base_dir).resolve()
    candidate = (base_dir / sanitize_filename(filename)).resolve()
    if not _is_relative_to(candidate, base_dir):
        raise ExtractorError(f"Ruta de salida no permitida (path traversal): {filename!r}")
    return candidate


def _is_relative_to(path: Path, base: Path) -> bool:
    try:
        path.relative_to(base)
        return True
    except ValueError:
        return False


# --------------------------------------------------------------------------
# Identificadores de video
# --------------------------------------------------------------------------
_TIKTOK_VIDEO_ID = re.compile(r"/video/(\d{6,25})")
_PHOTO_ID = re.compile(r"/photo/(\d{6,25})")


def extract_video_id(url: str) -> Optional[str]:
    """Extrae el id numerico de una URL de TikTok tipo /video/123... ."""
    if not url:
        return None
    m = _TIKTOK_VIDEO_ID.search(url) or _PHOTO_ID.search(url)
    return m.group(1) if m else None


def fallback_id_from_text(text: str) -> str:
    """Id corto y estable a partir de cualquier texto (URL rara, enlace corto...)."""
    digest = hashlib.sha1(text.encode("utf-8", "replace")).hexdigest()
    return digest[:12]


def local_stem(file_path: str) -> str:
    """Identificador para un archivo local: local_<nombre>_<timestamp>."""
    stem = slugify(Path(file_path).stem, max_length=40)
    return f"local_{stem}_{datetime.now():%Y%m%d_%H%M%S}"


# --------------------------------------------------------------------------
# Marcas de tiempo
# --------------------------------------------------------------------------
def format_timestamp(seconds: float) -> str:
    """Segundos -> 'MM:SS' (o 'HH:MM:SS' si supera la hora)."""
    seconds = max(0, int(round(float(seconds or 0))))
    h, rem = divmod(seconds, 3600)
    m, s = divmod(rem, 60)
    if h:
        return f"{h:d}:{m:02d}:{s:02d}"
    return f"{m:02d}:{s:02d}"


# --------------------------------------------------------------------------
# JSON tolerante a respuestas de IA imperfectas
# --------------------------------------------------------------------------
_FENCE = re.compile(r"^\s*```(?:json)?\s*|\s*```\s*$", re.IGNORECASE)


def extract_json(text: str) -> Any:
    """Intenta obtener un objeto/array JSON de una respuesta de texto libre.

    Maneja: JSON limpio, JSON rodeado de ```fences```, JSON con texto antes/despues.
    Lanza JSONParseError si no lo consigue.
    """
    if text is None:
        raise JSONParseError("Respuesta vacia de la IA.")
    raw = str(text).strip()
    if not raw:
        raise JSONParseError("Respuesta vacia de la IA.")

    # 1) tal cual
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        pass

    # 2) quitar fences de markdown
    without_fence = _FENCE.sub("", raw).strip()
    if without_fence != raw:
        try:
            return json.loads(without_fence)
        except json.JSONDecodeError:
            raw = without_fence

    # 3) recortar al primer bloque {...} o [...] balanceado
    for open_ch, close_ch in (("{", "}"), ("[", "]")):
        start = raw.find(open_ch)
        if start == -1:
            continue
        depth = 0
        in_str = False
        esc = False
        for i in range(start, len(raw)):
            ch = raw[i]
            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
                continue
            if ch == '"':
                in_str = True
            elif ch == open_ch:
                depth += 1
            elif ch == close_ch:
                depth -= 1
                if depth == 0:
                    candidate = raw[start:i + 1]
                    try:
                        return json.loads(candidate)
                    except json.JSONDecodeError:
                        break
    raise JSONParseError("No se encontro un JSON valido en la respuesta de la IA.")


# --------------------------------------------------------------------------
# Resolucion de FFmpeg (sistema o binario embebido de imageio-ffmpeg)
# --------------------------------------------------------------------------
_ffmpeg_cache: Optional[str] = None


def resolve_ffmpeg() -> Optional[str]:
    """Devuelve la ruta a un ejecutable ffmpeg utilizable, o None si no hay ninguno.

    Ademas antepone su carpeta al PATH del proceso para que yt-dlp y whisper
    lo encuentren sin configuracion adicional.
    """
    global _ffmpeg_cache
    if _ffmpeg_cache:
        return _ffmpeg_cache

    system = shutil.which("ffmpeg")
    if system:
        _ffmpeg_cache = system
    else:
        try:
            import imageio_ffmpeg
            _ffmpeg_cache = imageio_ffmpeg.get_ffmpeg_exe()
        except Exception:
            _ffmpeg_cache = None

    if _ffmpeg_cache:
        folder = str(Path(_ffmpeg_cache).parent)
        if folder not in os.environ.get("PATH", "").split(os.pathsep):
            os.environ["PATH"] = folder + os.pathsep + os.environ.get("PATH", "")
    return _ffmpeg_cache


def ffmpeg_install_hint() -> str:
    return (
        "FFmpeg no esta disponible.\n"
        "  Opcion A (recomendada): winget install --id Gyan.FFmpeg -e\n"
        "  Opcion B: descarga manual desde https://www.gyan.dev/ffmpeg/builds/ y anade\n"
        "            la carpeta 'bin' al PATH.\n"
        "  Opcion C: pip install imageio-ffmpeg   (ya deberia estar en requirements.txt)"
    )


# --------------------------------------------------------------------------
# Espacio de trabajo temporal
# --------------------------------------------------------------------------
class TempWorkspace:
    """Carpeta temporal por elemento procesado.

    Se borra al salir si todo fue bien; se conserva si hubo excepcion y
    keep_on_error=True (util para depurar).
    """

    def __init__(self, temp_root: Path, name: str, keep_on_error: bool = True):
        self.path = Path(temp_root) / sanitize_filename(name)
        self.keep_on_error = keep_on_error
        self._ok = False

    def __enter__(self) -> Path:
        if self.path.exists():
            shutil.rmtree(self.path, ignore_errors=True)
        self.path.mkdir(parents=True, exist_ok=True)
        return self.path

    def mark_ok(self) -> None:
        self._ok = True

    def __exit__(self, exc_type, exc, tb) -> None:
        keep = (exc_type is not None or not self._ok) and self.keep_on_error
        if keep:
            get_logger().info("Carpeta temporal conservada para depuracion: %s", self.path)
            return
        shutil.rmtree(self.path, ignore_errors=True)


# --------------------------------------------------------------------------
# Lectura de listas de URLs
# --------------------------------------------------------------------------
def read_urls_file(path: Path) -> list[str]:
    """Lee input/urls.txt: ignora lineas vacias y comentarios (#)."""
    p = Path(path)
    if not p.exists():
        raise ExtractorError(f"No existe el archivo de URLs: {p}")
    urls: list[str] = []
    for line in p.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        urls.append(line)
    return urls


def iter_unique(items: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    out: list[str] = []
    for it in items:
        if it not in seen:
            seen.add(it)
            out.append(it)
    return out
