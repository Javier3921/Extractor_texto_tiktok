# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Qué es esto

CLI en Python que convierte un vídeo de TikTok (o un archivo local) en una
transcripción traducida al español y un informe técnico en PDF generado por
IA. Nunca descarga ni guarda el vídeo: solo obtiene el audio. Ver README.md
para uso/instalación y INFORME_TECNICO.md para el detalle de arquitectura
etapa por etapa.

## Comandos

```bat
:: activar el entorno (Windows)
.venv\Scripts\activate

:: instalar dependencias (arrastra PyTorch, tarda varios minutos)
pip install -r requirements.txt

:: correr toda la suite (mockeada, sin red ni PyTorch real)
pytest -q

:: un archivo de test
pytest tests/test_gemini_provider.py -q

:: un test concreto
pytest tests/test_gemini_provider.py::TestClasificacionDeErrores::test_error_401_es_auth -q

:: filtrar por nombre
pytest -k "gemini and not autocambio" -q

:: ejecutar la app
python main.py --config              :: ver configuracion resuelta
python main.py --url "https://www.tiktok.com/@u/video/123"
python main.py --url "..." --instructions "Enfocate en los riesgos de seguridad"
python main.py --file "C:\ruta\video.mp4"
python main.py                        :: menu interactivo
python main.py --gui                  :: interfaz grafica (Tkinter)
```

No hay linter/formatter configurado en el repo (sin `pyproject.toml`,
`.flake8` ni `ruff.toml`).

## Arquitectura

**Pipeline lineal orquestado por `src/pipeline.py::_process()`**: obtener
audio → normalizar (FFmpeg → WAV 16kHz mono) → transcribir (Whisper) →
detectar idioma → traducir al español si procede → escribir `.txt` →
analizar con IA → generar `.pdf`. Cada etapa es un módulo independiente que
intercambia `dataclasses` simples (`src/models.py`), sin estado global.
`ExtractorError` (y su jerarquía) es la excepción de dominio; `_process()`
nunca deja escapar una excepción sin capturar: siempre devuelve un
`ProcessingResult` con `ok`/`error`.

**Degradación en cascada, nunca aborta si ya hay trabajo útil hecho:**
traducción por lote falla → reintento segmento a segmento → si un segmento
concreto sigue fallando, se conserva el texto original y se cuenta en
`TranslationResult.failed_segments` (el pipeline lo reporta al usuario, no lo
silencia). Análisis con IA sin JSON válido → un reintento con recordatorio →
informe de reserva. Si el proveedor de IA falla del todo (rate-limit, modelo
caído) se emite un PDF *degradado* explicando el motivo — el `.txt` ya se
escribió antes y no se pierde. Solo `AIAuthError` (clave inválida/ausente)
aborta sin reintentar, en cualquier punto del pipeline.

**`TempWorkspace` (`src/utils.py`) tiene una semántica no obvia:** se borra
al salir solo si se llamó explícitamente a `mark_ok()` *y* no hubo excepción.
`keep_on_error` (de `KEEP_TEMP_ON_ERROR` en `.env`) conserva la carpeta ante
un fallo; `always_keep` (de `--keep-temp`) la conserva *siempre*, incluso en
éxito — son dos flags independientes, no lo mismo (antes de una corrección
reciente `--keep-temp` no tenía efecto porque solo tocaba
`keep_on_error`, que ya era `true` por defecto).

**Capa de proveedores de IA (`src/ai_providers/`) usa el patrón Strategy:**
`base.py::AIProvider` es la clase abstracta con reintentos/backoff
centralizados (`complete()`); cada proveedor concreto solo implementa
`_complete_raw()`. `AIAuthError` nunca se reintenta; `AIRateLimitError` usa
backoff creciente. La fábrica `ai_providers/__init__.py::get_provider()`
importa cada SDK de forma perezosa (para no cargar dependencias no usadas) y
solo pasa `timeout` a `GeminiProvider` (es el único proveedor con capa
gratuita, el que se usa y prueba realmente en este proyecto; OpenAI/DeepSeek
existen pero nunca se han validado con una clave real). `GeminiProvider`
además **autocorrige el modelo** si la API responde 404 indicando el
sustituto (regex `_MODEL_MOVED`, case-insensitive — la API no garantiza
mayúsculas/minúsculas); el cambio de modelo solo se permite una vez por
llamada (`_allow_model_switch`) para no entrar en bucle si el sustituto
también está retirado.

**`gui.py` es una ventana Tkinter (stdlib, sin dependencia nueva) que reutiliza
`src/pipeline.py::process_url` en un hilo aparte** (para no congelar la UI
mientras Whisper transcribe) y muestra al terminar, en un `messagebox`, dónde
quedaron el `.txt`/`.pdf`. No tiene tests automatizados (requiere un display;
la CI de GitHub Actions corre headless) — si se toca, verificar a mano con
`python main.py --gui`.

**Las indicaciones del usuario (`user_instructions`, vía `--instructions`, el
menú interactivo o la GUI) llegan a `ai_analyzer.py::analyze_content` y se
inyectan en el prompt como una sección propia.** A diferencia de la
transcripción (dato no confiable de un tercero), estas sí vienen del usuario
real, pero el *system prompt* aun así les prohíbe autorizar alucinaciones o
cambiar el esquema JSON de salida — solo pueden mover el énfasis dentro de
las mismas secciones.

**El contenido transcrito es de terceros no confiables y se envía a un LLM:**
los *system prompts* de `translator.py` y `ai_analyzer.py` incluyen
instrucciones explícitas para que el modelo trate la transcripción como
dato, nunca como instrucción (guarda contra inyección de prompts vía audio
de un vídeo). No quitar esa sección al tocar los prompts.

**Whisper local no recibe una ruta de archivo, sino un `ndarray`:**
`transcriber.py` lee el WAV con el módulo estándar `wave` y lo convierte a
`float32` normalizado antes de pasarlo a `model.transcribe()`. Es
intencional: si se le pasa la ruta, Whisper intenta invocar `ffmpeg` por su
cuenta, y el binario que trae `imageio-ffmpeg` no se llama `ffmpeg.exe`, así
que no lo encontraría. No "simplificar" esto a `model.transcribe(path)`.

**Config (`config.py::Config`) se carga una vez en `main.py` y los flags de
CLI la sobrescriben en memoria** (`load_config()`), nunca se persiste el
override. Las claves de API nunca se imprimen completas (`masked_keys()`) y
`src/utils.py::SecretFilter` redacta patrones de secretos (`sk-…`, `AIza…`,
`Bearer …`) en *todos* los handlers de logging, no solo en consola.

**Límites de tamaño/red son transversales:** `MAX_VIDEO_MB` se aplica tanto
a `--file` (`local_video.py`) como a la descarga de audio de TikTok
(`tiktok_downloader.py`, vía `max_filesize` de yt-dlp); `NETWORK_TIMEOUT` se
usa tanto para `yt-dlp` como para el timeout HTTP del SDK de Gemini
(`http_options`). Si se añade un proveedor de IA nuevo o se cambia el límite
de tamaño, hay que tocar ambos puntos de uso, no solo uno.

**Tests (`tests/`) están completamente mockeados:** `MockProvider` para el
pipeline de IA, y para `GeminiProvider` se monkeypatchea
`client.models.generate_content` tras construir el proveedor real (el SDK
`google-genai` está instalado pero no se llama a la red). Ningún test
requiere PyTorch, red ni claves reales — los imports de `whisper`/`torch` en
`transcriber.py` son perezosos precisamente para permitir esto.
