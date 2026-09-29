"""Interfaz grafica minima (Tkinter, sin dependencias nuevas).

Pide la URL de un video de TikTok y, opcionalmente, indicaciones para la IA
sobre que priorizar en el informe; permite elegir proveedor de IA y formato
del informe (valores iniciales: los del .env). Al terminar, muestra en un
mensaje donde quedaron guardados el .txt y el informe .html/.md.

Uso:
    python main.py --gui
"""
from __future__ import annotations

import threading
import tkinter as tk
from tkinter import messagebox, ttk

from config import VALID_PROVIDERS, VALID_REPORT_FORMATS, Config
from src.models import ProcessingResult
from src.utils import ExtractorError


def run_gui(cfg: Config) -> None:
    root = tk.Tk()
    root.title("Extractor_texto_tiktok")
    root.geometry("560x500")
    root.minsize(480, 420)

    pad = {"padx": 16, "pady": (10, 2)}

    tk.Label(root, text="URL del video de TikTok", anchor="w").pack(fill="x", **pad)
    url_var = tk.StringVar()
    tk.Entry(root, textvariable=url_var).pack(fill="x", padx=16)

    tk.Label(
        root,
        text="Indicaciones para la IA (que priorizar o incluir en el informe; opcional)",
        anchor="w",
    ).pack(fill="x", **pad)
    instructions_txt = tk.Text(root, height=9, wrap="word")
    instructions_txt.pack(fill="both", expand=True, padx=16)

    options = tk.Frame(root)
    options.pack(fill="x", padx=16, pady=(10, 0))
    tk.Label(options, text="Proveedor de IA").pack(side="left")
    provider_var = tk.StringVar(value=cfg.ai_provider)
    ttk.Combobox(options, textvariable=provider_var, values=VALID_PROVIDERS,
                 state="readonly", width=12).pack(side="left", padx=(6, 18))
    tk.Label(options, text="Formato del informe").pack(side="left")
    format_var = tk.StringVar(value=cfg.report_format)
    ttk.Combobox(options, textvariable=format_var, values=VALID_REPORT_FORMATS,
                 state="readonly", width=10).pack(side="left", padx=(6, 0))

    def provider_note() -> str:
        prov = provider_var.get()
        return f"Proveedor de IA: {prov}" + ("" if cfg.has_key_for(prov) else "  [SIN CLAVE]")

    status_var = tk.StringVar(value=provider_note())
    provider_var.trace_add("write", lambda *_: status_var.set(provider_note()))
    tk.Label(root, textvariable=status_var, anchor="w", fg="#555").pack(
        fill="x", padx=16, pady=(10, 0))

    progress = ttk.Progressbar(root, mode="indeterminate")
    generate_btn = tk.Button(root, text="Generar informe")

    def set_busy(busy: bool) -> None:
        generate_btn.config(state="disabled" if busy else "normal")
        url_entry_state = "disabled" if busy else "normal"
        instructions_txt.config(state=url_entry_state)
        if busy:
            progress.pack(fill="x", padx=16, pady=(8, 0))
            progress.start(12)
        else:
            progress.stop()
            progress.pack_forget()

    def finish_error(msg: str) -> None:
        set_busy(False)
        status_var.set("Fallo el procesamiento.")
        messagebox.showerror("Error", msg)

    def finish_result(result: ProcessingResult) -> None:
        set_busy(False)
        if result.ok:
            status_var.set("Informe generado correctamente.")
            lines = ["El informe se genero correctamente.\n"]
            if result.txt_path:
                lines.append(f"Transcripcion (.txt):\n{result.txt_path}\n")
            if result.html_path:
                lines.append(f"Informe tecnico (.html):\n{result.html_path}\n")
            if result.md_path:
                lines.append(f"Informe tecnico (.md):\n{result.md_path}")
            messagebox.showinfo("Informe generado", "\n".join(lines))
        else:
            status_var.set("Fallo el procesamiento.")
            messagebox.showerror("Error", result.error or "Fallo desconocido.")

    def worker(url: str, instructions: str) -> None:
        from src.pipeline import process_url
        try:
            result = process_url(url, cfg, make_report=True, user_instructions=instructions)
        except ExtractorError as e:
            root.after(0, finish_error, str(e))
            return
        except Exception as e:  # noqa: BLE001
            root.after(0, finish_error, f"Error inesperado: {e}")
            return
        root.after(0, finish_result, result)

    def on_generate() -> None:
        url = url_var.get().strip()
        if not url:
            messagebox.showwarning("Falta la URL", "Ingresa la URL de un video de TikTok.")
            return
        instructions = instructions_txt.get("1.0", "end").strip()
        # solo en memoria para esta sesion, igual que los flags de la CLI
        cfg.ai_provider = provider_var.get()
        cfg.report_format = format_var.get()
        set_busy(True)
        status_var.set("Procesando... puede tardar varios minutos (transcripcion con Whisper).")
        threading.Thread(target=worker, args=(url, instructions), daemon=True).start()

    generate_btn.config(command=on_generate)
    generate_btn.pack(pady=14)

    root.mainloop()


if __name__ == "__main__":
    _cfg = Config.load()
    run_gui(_cfg)
