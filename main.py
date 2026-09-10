"""Extractor_texto_tiktok - punto de entrada.

Uso:
    python main.py                              -> menu interactivo
    python main.py --url "URL_TIKTOK"           -> procesar un TikTok
    python main.py --file "C:\\v\\video.mp4"     -> procesar un video local
    python main.py --urls-file input/urls.txt   -> procesar varias URLs
    python main.py --provider gemini --url ...  -> forzar proveedor de IA
    python main.py --config                     -> ver configuracion
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

# Permite ejecutar el script directamente (añade la raiz del proyecto al path).
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import PROJECT_ROOT, VALID_PROVIDERS, VALID_WHISPER_MODELS, Config  # noqa: E402
from src.utils import ExtractorError, read_urls_file, setup_logging  # noqa: E402

BANNER = r"""
==============================================
        EXTRACTOR DE TEXTO DE TIKTOK
==============================================
"""


# --------------------------------------------------------------------------
def build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="Extractor_texto_tiktok",
        description="TikTok/video -> transcripcion -> traduccion ES -> TXT -> "
                    "analisis IA -> PDF tecnico.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    src = p.add_mutually_exclusive_group()
    src.add_argument("--url", help="URL de un video de TikTok")
    src.add_argument("--file", help="Ruta de un archivo de video/audio local")
    src.add_argument("--urls-file", nargs="?", const="input/urls.txt",
                     help="Archivo con una URL por linea (def: input/urls.txt)")
    p.add_argument("--provider", choices=VALID_PROVIDERS,
                   help="Proveedor de IA a usar (sobrescribe .env)")
    p.add_argument("--ai-model", metavar="NOMBRE",
                   help="Modelo concreto del proveedor de IA (sobrescribe AI_MODEL)")
    p.add_argument("--model", choices=VALID_WHISPER_MODELS,
                   help="Modelo de Whisper (sobrescribe .env)")
    p.add_argument("--no-pdf", action="store_true", help="No generar el PDF")
    p.add_argument("--keep-temp", action="store_true",
                   help="Conservar la carpeta temporal aunque todo vaya bien")
    p.add_argument("--config", action="store_true",
                   help="Mostrar la configuracion actual y salir")
    return p


# --------------------------------------------------------------------------
def load_config(args: argparse.Namespace) -> Config:
    cfg = Config.load()
    if getattr(args, "provider", None):
        cfg.ai_provider = args.provider
    if getattr(args, "ai_model", None):
        cfg.ai_model = args.ai_model
    if getattr(args, "model", None):
        cfg.transcription_model = args.model
    if getattr(args, "keep_temp", False):
        cfg.keep_temp_on_error = True
    return cfg


def show_config(cfg: Config) -> None:
    print(BANNER)
    print("CONFIGURACION ACTUAL")
    print("-" * 46)
    for line in cfg.summary_lines():
        print("  " + line)
    print()
    prov = cfg.ai_provider
    if not cfg.has_key_for(prov):
        print(f"  [AVISO] No hay API key para '{prov}'.")
        if cfg.allow_mock_fallback:
            print("          Se usara el proveedor 'mock' (analisis simulado).")
        else:
            print("          El analisis fallara. Configura la clave en .env o usa "
                  "--provider mock.")
    print()


# --------------------------------------------------------------------------
def run_batch(urls: list[str], cfg: Config, make_pdf: bool) -> int:
    from src.pipeline import process_url
    if not urls:
        print("[ERROR] No hay URLs que procesar.")
        return 1
    print(f"\nSe procesaran {len(urls)} URL(s).\n")
    results = []
    for i, url in enumerate(urls, start=1):
        print("=" * 60)
        print(f"  ({i}/{len(urls)})  {url}")
        print("=" * 60)
        results.append(process_url(url, cfg, make_pdf=make_pdf))

    ok = sum(1 for r in results if r.ok)
    print("=" * 60)
    print(f"RESUMEN: {ok}/{len(results)} completadas correctamente.")
    for r in results:
        estado = "OK  " if r.ok else "FALLO"
        print(f"  [{estado}] {r.source_ref}")
        if not r.ok:
            print(f"          -> {r.error}")
    print("=" * 60)
    return 0 if ok == len(results) else 2


# --------------------------------------------------------------------------
def interactive_menu(cfg: Config) -> int:
    from src.pipeline import process_file, process_url
    while True:
        print(BANNER)
        print(f"  Proveedor IA actual: {cfg.ai_provider}"
              f"{'' if cfg.has_key_for(cfg.ai_provider) else '  [SIN CLAVE]'}")
        print(f"  Modelo Whisper: {cfg.transcription_model}")
        print()
        print("  1. Procesar un TikTok")
        print("  2. Procesar multiples TikToks (input/urls.txt)")
        print("  3. Procesar archivo de video local")
        print("  4. Cambiar proveedor de IA")
        print("  5. Ver configuracion")
        print("  6. Salir")
        print()
        choice = input("  Opcion > ").strip()

        if choice == "1":
            url = input("  URL de TikTok > ").strip()
            if url:
                process_url(url, cfg)
        elif choice == "2":
            path = input("  Archivo de URLs [input/urls.txt] > ").strip() or "input/urls.txt"
            try:
                urls = read_urls_file(_resolve(path))
                run_batch(urls, cfg, make_pdf=True)
            except ExtractorError as e:
                print(f"  [ERROR] {e}")
        elif choice == "3":
            path = input("  Ruta del archivo de video > ").strip().strip('"')
            if path:
                process_file(path, cfg)
        elif choice == "4":
            _change_provider(cfg)
        elif choice == "5":
            show_config(cfg)
            input("  (Enter para continuar) ")
        elif choice == "6" or choice.lower() in ("q", "salir", "exit"):
            print("  Hasta luego.")
            return 0
        else:
            print("  Opcion no valida.")
        print()


def _change_provider(cfg: Config) -> None:
    print("\n  Proveedores disponibles:")
    for i, p in enumerate(VALID_PROVIDERS, start=1):
        mark = "" if cfg.has_key_for(p) else "  (sin clave)"
        print(f"    {i}. {p}{mark}")
    sel = input("  Nuevo proveedor > ").strip().lower()
    if sel.isdigit() and 1 <= int(sel) <= len(VALID_PROVIDERS):
        sel = VALID_PROVIDERS[int(sel) - 1]
    if sel in VALID_PROVIDERS:
        cfg.ai_provider = sel
        print(f"  Proveedor cambiado a '{sel}' (solo para esta sesion).")
        if not cfg.has_key_for(sel):
            print("  [AVISO] Ese proveedor no tiene API key configurada en .env.")
    else:
        print("  Proveedor no valido.")


def _resolve(path: str) -> Path:
    p = Path(path)
    return p if p.is_absolute() else PROJECT_ROOT / p


# --------------------------------------------------------------------------
def main(argv: list[str] | None = None) -> int:
    args = build_arg_parser().parse_args(argv)

    try:
        cfg = load_config(args)
    except ExtractorError as e:
        print(f"[ERROR DE CONFIGURACION] {e}")
        return 1

    setup_logging(cfg.logs_dir)

    if args.config:
        show_config(cfg)
        return 0

    make_pdf = not args.no_pdf

    try:
        if args.url:
            from src.pipeline import process_url
            r = process_url(args.url, cfg, make_pdf=make_pdf)
            return 0 if r.ok else 2
        if args.file:
            from src.pipeline import process_file
            r = process_file(args.file, cfg, make_pdf=make_pdf)
            return 0 if r.ok else 2
        if args.urls_file is not None:
            urls = read_urls_file(_resolve(args.urls_file))
            return run_batch(urls, cfg, make_pdf=make_pdf)
        return interactive_menu(cfg)
    except KeyboardInterrupt:
        print("\n[INTERRUMPIDO] Cancelado por el usuario.")
        return 130
    except ExtractorError as e:
        print(f"[ERROR] {e}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
