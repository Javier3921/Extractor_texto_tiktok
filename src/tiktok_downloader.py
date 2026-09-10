"""Obtencion del AUDIO de un video de TikTok a partir de su URL publica.

IMPORTANTE (decision de diseno): este modulo NO descarga ni guarda el video.
Solo obtiene la pista de audio en un archivo temporal que el pipeline borra
al terminar.

No se accede a contenido privado ni se eluden mecanismos de acceso (login,
cookies de sesion, captchas...). Si TikTok bloquea la peticion se informa
con un mensaje claro y se recomienda usar el modo --file con un archivo local.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlparse

from src.utils import (ExtractorError, extract_video_id, fallback_id_from_text,
                       get_logger, resolve_ffmpeg)

log = get_logger()

_TIKTOK_HOSTS = {
    "tiktok.com", "www.tiktok.com", "m.tiktok.com",
    "vm.tiktok.com", "vt.tiktok.com",
}


@dataclass
class RemoteMedia:
    audio_path: Path
    video_id: str
    title: str
    duration: float
    uploader: str
    webpage_url: str


# --------------------------------------------------------------------------
# Validacion de URLs
# --------------------------------------------------------------------------
def validate_url(url: str) -> bool:
    """True si `url` es una URL http/https con host valido."""
    if not url or not isinstance(url, str):
        return False
    try:
        p = urlparse(url.strip())
    except Exception:
        return False
    return p.scheme in ("http", "https") and bool(p.netloc)


def is_tiktok_url(url: str) -> bool:
    """True si la URL apunta a un dominio de TikTok."""
    if not validate_url(url):
        return False
    host = (urlparse(url.strip()).hostname or "").lower()
    if host in _TIKTOK_HOSTS:
        return True
    return host.endswith(".tiktok.com")


# --------------------------------------------------------------------------
# Descarga de audio
# --------------------------------------------------------------------------
def fetch_audio(url: str, workdir: Path, *, timeout: int = 30) -> RemoteMedia:
    """Descarga SOLO el audio de la URL a `workdir` y devuelve sus metadatos."""
    url = url.strip()
    if not validate_url(url):
        raise ExtractorError(f"URL invalida: {url!r}")
    if not is_tiktok_url(url):
        raise ExtractorError(
            f"La URL no pertenece a TikTok: {url!r}\n"
            "Este modo solo acepta URLs de tiktok.com. Para otros origenes usa "
            "--file con un archivo de video local."
        )

    try:
        import yt_dlp
    except ImportError as e:  # pragma: no cover
        raise ExtractorError("Falta el paquete 'yt-dlp' (pip install yt-dlp).") from e

    workdir = Path(workdir)
    workdir.mkdir(parents=True, exist_ok=True)
    outtmpl = str(workdir / "audio_%(id)s.%(ext)s")
    ffmpeg = resolve_ffmpeg()

    ydl_opts = {
        "format": "bestaudio/best",
        "outtmpl": outtmpl,
        "noplaylist": True,
        "quiet": True,
        "no_warnings": True,
        "retries": 3,
        "socket_timeout": timeout,
        "nocheckcertificate": False,
        "restrictfilenames": True,
        # nada de cookies ni credenciales: solo contenido publico
    }
    if ffmpeg:
        ydl_opts["ffmpeg_location"] = ffmpeg

    log.info("yt-dlp: obteniendo solo audio de %s", url)
    try:
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            info = ydl.extract_info(url, download=True)
            info = ydl.sanitize_info(info)
            filename = ydl.prepare_filename(info)
    except yt_dlp.utils.DownloadError as e:
        raise _friendly_download_error(e, url) from e
    except yt_dlp.utils.ExtractorError as e:  # pragma: no cover
        raise _friendly_download_error(e, url) from e
    except ExtractorError:
        raise
    except Exception as e:  # noqa: BLE001
        raise ExtractorError(f"Error inesperado al obtener el audio de TikTok: {e}") from e

    audio_path = Path(filename)
    if not audio_path.exists():
        # yt-dlp puede haber cambiado la extension; buscamos el archivo real
        candidates = sorted(workdir.glob("audio_*"))
        if not candidates:
            raise ExtractorError(
                "yt-dlp no genero ningun archivo de audio. Es posible que TikTok "
                "haya bloqueado la descarga. Prueba con --file y un archivo local."
            )
        audio_path = candidates[0]

    vid = extract_video_id(url) or str(info.get("id") or "") or fallback_id_from_text(url)
    return RemoteMedia(
        audio_path=audio_path,
        video_id=vid,
        title=str(info.get("title") or info.get("description") or "").strip()[:200],
        duration=float(info.get("duration") or 0.0),
        uploader=str(info.get("uploader") or info.get("uploader_id") or "").strip(),
        webpage_url=str(info.get("webpage_url") or url),
    )


def _friendly_download_error(err: Exception, url: str) -> ExtractorError:
    msg = str(err).lower()
    if any(k in msg for k in ("private", "login required", "sign in", "age-restricted",
                              "requested format is not available")):
        return ExtractorError(
            "El video es privado, restringido o no ofrece contenido descargable "
            "publicamente. No se accede a contenido no publico."
        )
    if any(k in msg for k in ("not available in your country", "geo", "geoblock")):
        return ExtractorError("El video no esta disponible en tu region (geobloqueo).")
    if any(k in msg for k in ("http error 404", "no video", "unable to find", "not found",
                              "does not exist")):
        return ExtractorError("El video no existe o la URL es incorrecta.")
    if any(k in msg for k in ("429", "rate", "too many requests", "captcha", "blocked",
                              "forbidden", "http error 403")):
        return ExtractorError(
            "TikTok ha bloqueado o limitado la peticion (rate limit / captcha / 403).\n"
            "Sugerencias: espera un rato, actualiza yt-dlp (pip install -U yt-dlp) o usa "
            "--file con un archivo de video local."
        )
    return ExtractorError(
        f"No se pudo obtener el audio de TikTok.\nDetalle: {err}\n"
        "Como alternativa, descarga el video manualmente y usa --file."
    )
