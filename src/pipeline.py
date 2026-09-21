"""Orquestador del pipeline completo (6 etapas).

URL/archivo -> audio -> Whisper -> transcripcion -> deteccion de idioma ->
traduccion al espanol (si procede) -> TXT -> analisis IA -> HTML.
"""
from __future__ import annotations

import time
from datetime import datetime
from pathlib import Path

from config import Config
from src.ai_analyzer import analyze_content
from src.ai_providers import get_provider
from src.audio_extractor import extract_audio, probe_duration
from src.html_generator import build_html
from src.language_detector import detect_language
from src.local_video import validate_local_media
from src.models import ProcessingResult, Transcript
from src.tiktok_downloader import fetch_audio
from src.transcriber import transcribe
from src.translator import translate_to_spanish
from src.txt_writer import build_txt, write_txt
from src.utils import (ExtractorError, format_timestamp, get_logger, local_stem,
                       TempWorkspace)

log = get_logger()

TOTAL_STEPS = 6


def _step(n: int, msg: str) -> None:
    print(f"[{n}/{TOTAL_STEPS}] {msg}")


def _info(msg: str) -> None:
    print(f"[INFO] {msg}")


def _ok(msg: str) -> None:
    print(f"[OK] {msg}")


def process_url(url: str, cfg: Config, *, make_html: bool = True,
                user_instructions: str = "") -> ProcessingResult:
    return _process(kind="url", ref=url, cfg=cfg, make_html=make_html,
                    user_instructions=user_instructions)


def process_file(path: str, cfg: Config, *, make_html: bool = True,
                 user_instructions: str = "") -> ProcessingResult:
    return _process(kind="file", ref=path, cfg=cfg, make_html=make_html,
                    user_instructions=user_instructions)


# --------------------------------------------------------------------------
def _process(*, kind: str, ref: str, cfg: Config, make_html: bool,
            user_instructions: str = "") -> ProcessingResult:
    started = time.time()
    provider_name = cfg.resolved_provider()
    result = ProcessingResult(
        video_id="", source_kind=kind, source_ref=ref,
        provider=provider_name, ai_model=cfg.effective_ai_model(),
        whisper_model=cfg.transcription_model,
    )

    # id / carpeta temporal
    if kind == "url":
        from src.utils import extract_video_id, fallback_id_from_text
        vid = extract_video_id(ref) or fallback_id_from_text(ref)
    else:
        vid = local_stem(ref)
    result.video_id = vid

    ws = TempWorkspace(cfg.temp_dir, f"job_{vid}", keep_on_error=cfg.keep_temp_on_error,
                       always_keep=cfg.always_keep_temp)
    try:
        with ws as workdir:
            log.info("=== Inicio procesamiento (%s) id=%s provider=%s modelo_whisper=%s ===",
                     kind, vid, provider_name, cfg.transcription_model)

            # -- 1. Obtener audio (sin guardar video) -----------------------
            url_for_report = ref if kind == "url" else ""
            title = ""
            if kind == "url":
                _step(1, "Obteniendo audio del TikTok (no se descarga el video)...")
                media = fetch_audio(ref, workdir, timeout=cfg.network_timeout,
                                    max_mb=cfg.max_video_mb)
                raw_media = media.audio_path
                result.video_id = media.video_id or vid
                vid = result.video_id
                title = media.title
                url_for_report = media.webpage_url or ref
                known_duration = media.duration
            else:
                _step(1, "Validando archivo local...")
                local = validate_local_media(ref, max_mb=cfg.max_video_mb)
                raw_media = local
                known_duration = probe_duration(local)
                title = Path(ref).stem

            # -- 2. Extraer / normalizar audio para Whisper ----------------
            # (vale tanto para video como para audio suelto: siempre se
            #  normaliza a WAV 16 kHz mono, que es lo que espera Whisper)
            _step(2, "Extrayendo audio (WAV 16 kHz mono)...")
            audio_wav = extract_audio(raw_media, workdir)

            # -- 3. Transcribir -------------------------------------------
            _step(3, f"Transcribiendo con Whisper ({cfg.transcription_backend}:"
                     f"{cfg.transcription_model})...")
            transcript: Transcript = transcribe(
                audio_wav,
                backend=cfg.transcription_backend,
                model=cfg.transcription_model,
                api_key=cfg.openai_api_key,
            )
            if not transcript.duration and known_duration:
                transcript.duration = known_duration
            result.duration = transcript.duration

            # -- 4. Detectar idioma -------------------------------------
            _step(4, "Detectando idioma...")
            language = detect_language(transcript)
            _info(f"Idioma detectado: {language.name}")
            result.original_language = language.name

            # -- 5. Traduccion + analisis con IA -----------------------
            _step(5, "Traduciendo/analizando con IA...")
            provider = get_provider(provider_name, cfg, timeout=cfg.network_timeout)
            if provider_name == "mock" and cfg.ai_provider != "mock":
                _info("Proveedor 'mock' en uso (sin clave del proveedor elegido). "
                      "El analisis NO es real.")

            if not language.is_spanish:
                _info("Traduciendo contenido al espanol...")
                tr = translate_to_spanish(
                    transcript.segments, source_language=language.name,
                    provider=provider, is_spanish=False,
                )
                _ok("Traduccion completada.")
            else:
                tr = translate_to_spanish(
                    transcript.segments, source_language=language.name,
                    provider=provider, is_spanish=True,
                )
            result.translated = tr.translated
            if tr.failed_segments:
                _info(f"[AVISO] {tr.failed_segments} segmento(s) no se pudieron traducir; "
                      "se dejo el texto original (mezcla de idiomas posible en el TXT/HTML).")

            spanish_segments = tr.spanish_segments
            original_segments = transcript.segments

            # -- TXT (etapa intermedia obligatoria) --------------------
            txt_body = build_txt(
                url=url_for_report, video_id=vid, language=language,
                duration=transcript.duration, translated=tr.translated,
                original_segments=original_segments,
                spanish_segments=spanish_segments,
            )
            txt_path = write_txt(txt_body, cfg.txt_dir, vid)
            result.txt_path = str(txt_path)
            log.info("TXT escrito en %s", txt_path)

            # -- Analisis tecnico -------------------------------------
            spanish_text = "\n".join(s.clean_text() for s in spanish_segments)
            original_text = "\n".join(s.clean_text() for s in original_segments)
            report = analyze_content(
                spanish_text=spanish_text,
                original_text=original_text if tr.translated else None,
                translated=tr.translated,
                original_language=language.name,
                title=title,
                url=url_for_report,
                duration_str=format_timestamp(transcript.duration),
                provider=provider,
                user_instructions=user_instructions,
            )

            # -- 6. HTML ---------------------------------------------
            if make_html:
                _step(6, "Generando informe HTML...")
                html_path = build_html(
                    report, html_dir=cfg.html_dir, video_id=vid,
                    url=url_for_report, original_language=language.name,
                    translated=tr.translated, provider=provider.name,
                    ai_model=cfg.effective_ai_model(),
                    duration_str=format_timestamp(transcript.duration),
                )
                result.html_path = str(html_path)
            else:
                _step(6, "Informe HTML omitido (--no-html).")

            result.ok = True
            ws.mark_ok()

    except ExtractorError as e:
        result.error = str(e)
        log.error("Procesamiento fallido (%s): %s", vid, e)
    except Exception as e:  # noqa: BLE001
        result.error = f"Error inesperado: {e}"
        log.exception("Error inesperado procesando %s", vid)

    result.elapsed_seconds = round(time.time() - started, 1)
    _print_summary(result)
    return result


def _print_summary(r: ProcessingResult) -> None:
    print()
    if r.ok:
        _ok("Procesamiento completado.")
        print()
        print("TXT:")
        print(f"  {r.txt_path}")
        if r.html_path:
            print("Informe HTML:")
            print(f"  {r.html_path}")
    else:
        print(f"[ERROR] No se pudo completar el procesamiento de: {r.source_ref}")
        print(f"        {r.error}")
    print(f"        (tiempo: {r.elapsed_seconds}s)")
    print()
