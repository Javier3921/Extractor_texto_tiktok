# Guía del proyecto — Extractor_texto_tiktok

> Documento único que explica **qué se implementó**, **cómo se hizo**, **cómo ejecutarlo**
> (con todos los comandos) y **cómo se probó**.
> Complementa al `README.md`: el README es el manual de usuario; esta guía es el "cómo se
> construyó" + operación detallada.

---

## Índice

1. [Resumen y pipeline](#1-resumen-y-pipeline)
2. [Cómo se hizo — proceso de desarrollo](#2-cómo-se-hizo--proceso-de-desarrollo)
3. [Arquitectura y módulos](#3-arquitectura-y-módulos)
4. [Requisitos](#4-requisitos)
5. [Instalación paso a paso (comandos)](#5-instalación-paso-a-paso-comandos)
6. [Configuración `.env`](#6-configuración-env)
7. [Cómo ejecutarlo — todos los comandos](#7-cómo-ejecutarlo--todos-los-comandos)
8. [Qué genera](#8-qué-genera)
9. [¿Dónde queda el audio del TikTok?](#9-dónde-queda-el-audio-del-tiktok)
10. [Cómo se probó](#10-cómo-se-probó)
11. [Solución de problemas](#11-solución-de-problemas)
12. [Limitaciones y decisiones de diseño](#12-limitaciones-y-decisiones-de-diseño)
13. [Historial de cambios](#13-historial-de-cambios)

---

## 1. Resumen y pipeline

**Extractor_texto_tiktok** es una aplicación Python (CLI, menú interactivo o una pequeña
interfaz gráfica) que, a partir de una URL de TikTok **o** de un archivo de vídeo local,
produce:

- un archivo **`.txt`** con la información del vídeo + la transcripción original + la traducción
  al español, y
- un **informe técnico `.html`** autónomo (sin dependencias, con gráficos SVG),
  **redactado íntegramente en español**, generado por una IA que analiza el contenido. Hasta
  septiembre de 2026 este informe se generaba en `.pdf` con ReportLab; se sustituyó por HTML
  (ver [sección 13](#13-historial-de-cambios)) porque pesa una fracción de lo mismo y permite
  gráficos reales.

Opcionalmente, el usuario puede darle **indicaciones a la IA** (`--instructions`, el menú o la
GUI) sobre qué priorizar en el informe.

Ubicación del proyecto (ajusta la ruta a donde lo tengas):
`C:\ruta\a\Extractor_texto_tiktok`

### Pipeline de 6 etapas

```
  URL de TikTok  ó  archivo local (--file)
          │
   [1] obtener el audio           (URL: yt-dlp baja SOLO el audio; local: se usa el archivo)
          │
   [2] extraer/normalizar audio   (FFmpeg → WAV 16 kHz mono en temp/)
          │
   [3] transcribir                (Whisper local → segmentos con timestamps + idioma)
          │
   [4] detectar idioma            (idioma de Whisper + verificación con langdetect)
          │
   ┌──────┴───────────────┐
 español                otro idioma
   │                       │
   │              [5a] traducir al español con IA  (conservando el original
   │                       │                        y los términos técnicos)
   └──────┬───────────────┘
          │
   escribir  output/txt/<id>.txt
          │
   [5b] análisis técnico con IA   (JSON con 12 apartados; reglas anti-alucinación;
          │                        admite instrucciones opcionales del usuario)
          │
   [6] generar  output/html/reporte_<id>.html   (secciones A–L + gráficos, en español)
```

**Nunca se descarga ni se guarda el vídeo.** Solo se obtiene la pista de audio, de forma
temporal, y se borra al terminar (ver [sección 9](#9-dónde-queda-el-audio-del-tiktok)).

### Tres formas de usarlo

1. **CLI directa**: `python main.py --url "..."` (o `--file`), con flags como `--provider`,
   `--ai-model`, `--instructions`, `--no-html`.
2. **Menú interactivo**: `python main.py` sin argumentos.
3. **Interfaz gráfica** (Tkinter, sin dependencias nuevas): `python main.py --gui`. Pide la URL
   y, opcionalmente, indicaciones para la IA; procesa en un hilo aparte (no congela la ventana)
   y al terminar muestra en un `messagebox` dónde quedaron el `.txt` y el `.html`.

Las tres llaman al mismo `src/pipeline.py::process_url` / `process_file`; ninguna duplica lógica.

---

## 2. Cómo se hizo — proceso de desarrollo

### 2.1. Análisis previo (antes de escribir código)

Se inspeccionó el entorno de la máquina:

| Hallazgo | Consecuencia |
|---|---|
| **Python 3.13** instalado (python.org + Microsoft Store). No hay 3.11/3.12. | Se usa `py -3.13` (python.org) para crear el `.venv` y se evita el Python de la Store (tiene el sistema de archivos aislado). |
| **FFmpeg no instalado**, no está en el PATH. `winget` disponible. | Se añade `imageio-ffmpeg` (trae un `ffmpeg.exe` embebido) como plan B automático. |
| `ctranslate2` (dependencia de `faster-whisper`) **no tiene wheels para Python 3.13**. | Se descarta `faster-whisper`; se usa `openai-whisper` (que sí funciona en 3.13). |
| `google-generativeai` **deprecado** (nov 2025). | Se usa el SDK nuevo unificado **`google-genai`**. |
| DeepSeek expone una API **compatible con OpenAI**. | El proveedor DeepSeek reutiliza el SDK `openai` cambiando solo `base_url`. |

### 2.2. Decisiones técnicas y su porqué

1. **Transcripción: `openai-whisper` local (modelo `small` por defecto).**
   Offline, gratis, sin API key. `faster-whisper` habría sido más rápido pero no instala en
   Python 3.13. El audio se lee con el módulo estándar `wave` a un array de NumPy y se le pasa
   directamente a Whisper: así **no se necesita un `ffmpeg.exe` llamado exactamente "ffmpeg"
   en el PATH** (el binario de `imageio-ffmpeg` tiene otro nombre).

2. **Proveedor de IA por defecto: Gemini.**
   Es el único con **capa gratuita** real (Google AI Studio). Se implementan además OpenAI,
   DeepSeek y un proveedor `mock` (simulado, offline) para poder probar sin claves.

3. **FFmpeg: sistema primero, `imageio-ffmpeg` como respaldo.**
   `resolve_ffmpeg()` busca `ffmpeg` en el PATH; si no lo encuentra, usa el binario de
   `imageio-ffmpeg`. Resultado: funciona con un simple `pip install`, sin permisos de admin.

4. **Sin descargar el vídeo — solo audio temporal, autoborrado.**
   Petición explícita del usuario. `yt-dlp` se invoca con `format="bestaudio/best"`, se guarda
   en `temp/job_<id>/` y esa carpeta se elimina al terminar con éxito.

5. **Arquitectura de proveedores de IA desacoplada.**
   Interfaz común `AIProvider` (`complete` / `complete_json`). Cambiar de proveedor es cambiar
   una variable en `.env`; el resto del programa no se toca.

### 2.3. Fases de construcción (en orden)

1. Estructura de carpetas y archivos base (`requirements.txt`, `.env.example`, `.gitignore`,
   `run.bat`).
2. `config.py` (carga y validación de `.env`) + `src/utils.py` (logging con redacción de
   secretos, rutas seguras, `TempWorkspace`, `extract_json`, `resolve_ffmpeg`).
3. `src/models.py` (dataclasses: `Segment`, `Transcript`, `LanguageInfo`, `AnalysisReport`,
   `ProcessingResult`).
4. `src/tiktok_downloader.py` (validación de URL + `fetch_audio` con `yt-dlp`, solo audio).
5. `src/local_video.py` (validación de archivos locales).
6. `src/audio_extractor.py` (FFmpeg → WAV 16 kHz mono).
7. `src/transcriber.py` (Whisper local + backend alternativo de API de OpenAI).
8. `src/language_detector.py` (idioma de Whisper + verificación con `langdetect`).
9. `src/translator.py` (traducción por lotes al español conservando términos técnicos).
10. `src/ai_providers/` (base + `openai_provider`, `gemini_provider`, `deepseek_provider`,
    `mock_provider` + fábrica `get_provider`).
11. `src/ai_analyzer.py` (prompt de análisis con reglas anti-alucinación; JSON → `AnalysisReport`).
12. `src/txt_writer.py` (formato exacto del `.txt`).
13. `src/html_generator.py` (HTML autónomo: CSS y SVG inline, sin JS; secciones A–L +
    gráfico de tecnologías + insignia de dificultad). Sustituyó a un `src/pdf_generator.py`
    original con ReportLab (ver [sección 13](#13-historial-de-cambios)).
14. `src/pipeline.py` (orquestador de las 6 etapas) + `main.py` (CLI + menú interactivo) +
    `gui.py` (interfaz gráfica, Tkinter).
15. `tests/` (121 tests con `pytest`, todos con mocks; sin red ni torch ni display).
16. Documentación (`README.md`, `CLAUDE.md` local y esta guía).

### 2.4. Incidencia resuelta durante las pruebas

Al probar con una API key real de Gemini, la API respondió **404: el modelo `gemini-2.0-flash`
ya no está disponible; usa `gemini-3.6-flash`** (Google lo retiró).

Correcciones aplicadas:

- Modelo Gemini por defecto → **`gemini-3.6-flash`**.
- **Autocorrección de modelo**: si la API devuelve un 404 indicando el sustituto
  (`use models/xxx`), el proveedor Gemini cambia solo al modelo nuevo y reintenta una vez.
- **El análisis con IA ya no aborta todo el procesamiento** si el proveedor falla (cuota
  agotada, modelo caído, red): el `.txt` se genera igualmente y el informe sale en modo
  degradado dejando constancia del motivo (actualmente en `.html`; era `.pdf` hasta que se
  cambió el formato, ver [sección 13](#13-historial-de-cambios)). Solo `AIAuthError` (clave
  inválida/ausente) corta el proceso, y sin reintentos inútiles.
- Nueva opción de CLI `--ai-model NOMBRE` para forzar el modelo del proveedor.

### 2.5. Incidencias resueltas en sesiones posteriores

Resumen breve; el detalle completo (con qué se probó) está en la
[sección 13, Historial de cambios](#13-historial-de-cambios).

- **TikTok empezó a exigir "impersonation" TLS** (para no bloquear la petición como bot) y
  `yt-dlp` fallaba con `Unexpected response from webpage request`. Se resolvió instalando y
  declarando `curl_cffi` en `requirements.txt` (no se importa en ningún módulo propio; lo usa
  `yt-dlp` internamente — no es una dependencia muerta).
- **Gemini devuelve 503 "sobrecargado por alta demanda"** de forma esporádica (problema de
  capacidad de Google, no de configuración). Se añadió `AIOverloadedError` con el mismo backoff
  creciente que un rate-limit, y un **fallback automático** a un modelo más ligero
  (`GEMINI_FALLBACK_MODEL`, por defecto `gemini-flash-lite-latest`) si el modelo principal sigue
  sobrecargado tras agotar los reintentos.
- **El regex de autocambio de modelo retirado** (`_MODEL_MOVED`) era sensible a mayúsculas y
  podía no detectar el sustituto si la API capitalizaba distinto ("Use models/…"). Se le añadió
  `re.IGNORECASE`.
- **`--keep-temp` no tenía efecto**: solo forzaba `KEEP_TEMP_ON_ERROR=true`, que ya era el valor
  por defecto, así que no cambiaba nada en el caso de éxito. Se separó en dos flags
  independientes (`keep_on_error` / `always_keep`) en `TempWorkspace`.

---

## 3. Arquitectura y módulos

```
Extractor_texto_tiktok/
├── main.py                     # CLI (argparse) + menú interactivo de 6 opciones
├── gui.py                      # interfaz grafica (Tkinter), python main.py --gui
├── config.py                   # Config (dataclass) desde .env: validación, rutas, claves enmascaradas
├── requirements.txt            # dependencias
├── .env / .env.example         # credenciales y ajustes (.env está en .gitignore)
├── run.bat                     # lanzador Windows: crea .venv + instala deps la 1ª vez
├── README.md                   # manual de usuario (documentación pública)
├── GUIA_DEL_PROYECTO.md        # este documento
├── CLAUDE.md                   # contexto privado para agentes de IA (NO se sube a Git)
│
├── src/
│   ├── models.py               # dataclasses compartidas
│   ├── pipeline.py             # orquesta las 6 etapas; imprime progreso; devuelve ProcessingResult
│   ├── tiktok_downloader.py    # validate_url / is_tiktok_url / fetch_audio (yt-dlp, SOLO audio)
│   ├── local_video.py          # validate_local_media (existe + extensión soportada)
│   ├── audio_extractor.py      # extract_audio → WAV 16 kHz mono con FFmpeg; probe_duration
│   ├── transcriber.py          # transcribe(): backend 'local' (openai-whisper) | 'openai_api'
│   ├── language_detector.py    # detect_language(): Whisper + langdetect; mapa de nombres
│   ├── translator.py           # translate_to_spanish(): por lotes; conserva original y timestamps
│   ├── ai_analyzer.py          # analyze_content(): prompt + JSON → AnalysisReport; admite
│   │                           #   user_instructions; informe degradado si el proveedor falla
│   ├── txt_writer.py           # build_txt / write_txt: formato exacto del .txt
│   ├── html_generator.py       # build_html: HTML autónomo (CSS/SVG inline, sin JS), A–L +
│   │                           #   gráfico de tecnologías + insignia de dificultad
│   ├── utils.py                # logging+SecretFilter, sanitize_filename, safe_output_path,
│   │                           #   extract_video_id, format_timestamp, extract_json,
│   │                           #   resolve_ffmpeg, TempWorkspace, read_urls_file
│   └── ai_providers/
│       ├── __init__.py         # get_provider(name, cfg, timeout=..., ) -> AIProvider
│       ├── base.py             # AIProvider (ABC): complete(), complete_json(), reintentos/backoff;
│       │                       #   AIProviderError / AIAuthError / AIRateLimitError / AIOverloadedError
│       ├── openai_provider.py  # SDK openai; response_format JSON
│       ├── gemini_provider.py  # SDK google-genai; autocorrección de modelo retirado; timeout de
│       │                       #   red; fallback a GEMINI_FALLBACK_MODEL si se sobrecarga (503)
│       ├── deepseek_provider.py# = OpenAIProvider con base_url de DeepSeek
│       └── mock_provider.py    # respuestas deterministas offline (tests / sin clave)
│
├── input/urls.txt              # una URL por línea (para procesar en lote)
├── output/txt/  ·  output/html/ # resultados
├── temp/                       # carpetas de trabajo temporales (se borran al terminar)
├── logs/                       # logs diarios (sin secretos)
└── tests/                      # 121 tests pytest
```

### Responsabilidad de cada archivo

| Archivo | Qué hace |
|---|---|
| `main.py` | Analiza argumentos; si no hay, muestra el menú de 6 opciones. Carga `Config`, aplica overrides de CLI, arranca el logging y llama al `pipeline`. Con `--gui` delega en `gui.py` en vez de la CLI. |
| `gui.py` | Ventana Tkinter (stdlib): URL + cuadro de indicaciones para la IA + botón. Corre `process_url` en un hilo aparte (no congela la ventana) y muestra el resultado (rutas de `.txt`/`.html`) en un `messagebox`. Sin tests automatizados (requiere display). |
| `config.py` | `Config.load()` lee `.env` + variables de entorno, valida (`AI_PROVIDER`, backend, modelo Whisper), crea carpetas, y enmascara las claves para mostrarlas. `DEFAULT_AI_MODELS` define el modelo por defecto de cada proveedor; `gemini_fallback_model` (`GEMINI_FALLBACK_MODEL`) el modelo de reserva de Gemini. |
| `src/pipeline.py` | Ejecuta las 6 etapas en orden, imprime `[1/6]…[6/6]` y los `[INFO]/[OK]`, gestiona la carpeta temporal (`TempWorkspace`) y devuelve un `ProcessingResult` con rutas y errores. |
| `src/tiktok_downloader.py` | `validate_url` (http/https + host), `is_tiktok_url` (dominios de TikTok), `fetch_audio(url, workdir)` con `yt-dlp` `format="bestaudio/best"`; mapea los errores de yt-dlp a mensajes claros (privado, geobloqueo, 403/rate-limit, no encontrado). No usa cookies ni login. |
| `src/local_video.py` | Comprueba que el archivo existe y que la extensión está soportada (`mp4, mov, mkv, webm, avi, m4v, flv` y audio suelto: `mp3, wav, m4a, aac, ogg, flac`). |
| `src/audio_extractor.py` | `extract_audio()` llama a FFmpeg (`-vn -ac 1 -ar 16000 -c:a pcm_s16le`) para dejar un WAV que Whisper procesa bien. Si no hay FFmpeg, error con instrucciones. |
| `src/transcriber.py` | `transcribe()`. Backend `local`: `whisper.load_model()` (cacheado) y `model.transcribe(array)`; lee el WAV con `wave` para no depender del `ffmpeg` del PATH. Backend `openai_api`: `client.audio.transcriptions.create(model="whisper-1")` (límite 25 MB). |
| `src/language_detector.py` | `detect_language()`: usa el idioma que devuelve Whisper (basado en audio) como primario y `langdetect` sobre el texto como verificación. Devuelve `LanguageInfo(code, name, is_spanish, …)`. |
| `src/translator.py` | Si el idioma ya es español → no traduce. Si no → traduce por lotes de ~40 segmentos con el proveedor de IA; conserva `start/end`, el nº de segmentos y los términos técnicos (React, Node.js, REST API, OAuth 2.0, Docker, Kubernetes…). Degrada a traducción segmento-a-segmento si un lote falla; `AIAuthError` corta. |
| `src/ai_analyzer.py` | Construye el prompt (transcripción ES como contenido principal + original para verificar términos + instrucciones opcionales del usuario) con reglas anti-alucinación (distinguir *información explícita* / *inferencia* / *recomendación*; no inventar) y una guarda explícita contra instrucciones ocultas en la transcripción (contenido de terceros no confiable). Pide JSON, lo valida/repara → `AnalysisReport`. Si el JSON es irrecuperable → informe de reserva. Si el proveedor falla (no-auth) → informe degradado (no rompe el pipeline). |
| `src/txt_writer.py` | Genera el `.txt` con el formato exacto: bloque `INFORMACION DEL VIDEO`, luego `TRANSCRIPCION ORIGINAL` (solo si hubo traducción) y `TRANSCRIPCION EN ESPANOL`, con líneas `[mm:ss] texto`. UTF-8. |
| `src/html_generator.py` | `build_html()`: un único archivo HTML con CSS y SVG *inline*, sin JavaScript ni peticiones externas. Secciones **A–L**, tabla + gráfico de barras SVG de tecnologías por categoría, insignia de color para la dificultad, estilos `@media print`. Todo el contenido pasa por `html.escape()` antes de insertarse (el contenido viene en última instancia de un vídeo de terceros). |
| `src/utils.py` | Utilidades transversales: logging a `logs/run_AAAAMMDD.log` con `SecretFilter` (redacta claves), `sanitize_filename`, `safe_output_path` (anti path-traversal), `extract_video_id`, `format_timestamp`, `extract_json` (tolera ```` ``` ````, texto alrededor, JSON truncado), `resolve_ffmpeg`, `TempWorkspace` (borra la carpeta al salir con éxito **solo si se llamó a `mark_ok()`**; `always_keep`/`keep_on_error` son flags independientes), `read_urls_file`. |
| `src/ai_providers/base.py` | `AIProvider` (ABC). `complete()` con reintentos y backoff ante rate-limit/sobrecarga/errores transitorios (`max_retries=4`); `complete_json()` usa `extract_json`. Excepciones: `AIProviderError`, `AIAuthError` (nunca se reintenta), `AIRateLimitError`, `AIOverloadedError` (503/alta demanda; mismo backoff creciente que el rate-limit). |
| `src/ai_providers/gemini_provider.py` | SDK `google-genai`. Mapea 401/403 → `AIAuthError`, 429/quota → `AIRateLimitError`, 503/"high demand" → `AIOverloadedError`, 404 modelo retirado → **cambia al modelo que indica la API y reintenta** (regex case-insensitive). `complete()` está sobreescrito: si tras agotar los reintentos sigue sobrecargado, prueba una vez con `GEMINI_FALLBACK_MODEL` antes de rendirse. Recibe también `timeout` (→ `http_options` del SDK, evita que una llamada colgada bloquee el pipeline). |
| `src/ai_providers/openai_provider.py` / `deepseek_provider.py` | SDK `openai`; DeepSeek = la misma clase con `base_url="https://api.deepseek.com"`. |
| `src/ai_providers/mock_provider.py` | Proveedor simulado: traducción "de marcador" (conserva términos técnicos) y un `AnalysisReport` JSON válido derivado del texto. Se usa con `--provider mock` o `AI_PROVIDER=mock`. |

### Modelos de datos (`src/models.py`)

- `Segment(start, end, text)` — un fragmento de transcripción con timestamps (segundos).
- `Transcript(segments, language, duration, source)` — resultado de transcribir.
- `LanguageInfo(code, name, is_spanish, method, secondary_code)`.
- `AnalysisReport` — espejo del JSON pedido a la IA: `title, original_language,
  translated_to_spanish, executive_summary, detailed_explanation, technologies[],
  technical_concepts[], architecture, code_analysis, best_practices[], risks[],
  recommendations[], difficulty, applications[], conclusion` (+ `parse_warning` interno).
- `ProcessingResult` — id, rutas de TXT/HTML, idioma, si hubo traducción, proveedor/modelo,
  error y tiempo.

---

## 4. Requisitos

| Componente | Detalle |
|---|---|
| SO | Windows 10/11 (probado en Windows 11). |
| Python | 3.11+ (probado en **3.13.7** de python.org). |
| FFmpeg | Opcional: si no hay uno del sistema, se usa el de `imageio-ffmpeg` (viene con las dependencias). |
| Clave de IA | Solo para traducción/análisis. **Gemini** tiene capa gratuita. |
| Disco | ~2–2,5 GB para PyTorch + Whisper; el modelo `small` añade ~460 MB la primera vez. |
| Red | Para instalar dependencias, descargar el modelo Whisper la 1ª vez y llamar a la IA. |

---

## 5. Instalación paso a paso (comandos)

Abre una terminal (PowerShell o CMD) **dentro de la carpeta del proyecto**:

```bat
cd C:\ruta\a\Extractor_texto_tiktok
```

### Opción A — automática (Windows)

```bat
run.bat
```

La primera vez crea `.venv`, instala las dependencias (tarda varios minutos por PyTorch) y
lanza el menú. Las siguientes veces solo lanza la app.

### Opción B — manual (paso a paso)

```bat
py -3.13 -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
copy .env.example .env
```

> Si `py -3.13` no existe en tu equipo, usa `py -3` o `python -m venv .venv`.

### (Opcional) FFmpeg del sistema

No hace falta (ya funciona con `imageio-ffmpeg`), pero si lo quieres:

```bat
winget install --id Gyan.FFmpeg -e
```

### Comprobar la instalación

```bat
.venv\Scripts\activate
python main.py --config
```

Debe listar la configuración. Si `AI_PROVIDER` sale con `[SIN CLAVE]`, edita `.env`
(ver sección 6).

---

## 6. Configuración `.env`

Copia `.env.example` a `.env` y rellena lo que necesites. Variables:

| Variable | Valores | Por defecto | Para qué |
|---|---|---|---|
| `AI_PROVIDER` | `gemini` `openai` `deepseek` `mock` | `gemini` | Proveedor de traducción + análisis. |
| `AI_MODEL` | texto | *(vacío)* | Modelo concreto. Vacío = el por defecto del proveedor. |
| `GEMINI_FALLBACK_MODEL` | texto | `gemini-flash-lite-latest` | Solo Gemini: si el modelo principal se sobrecarga (503) y se agotan los reintentos, se prueba una vez con este. Vacío = desactivado. |
| `OPENAI_API_KEY` | texto | — | Clave de OpenAI. |
| `GEMINI_API_KEY` | texto | — | Clave de Google AI Studio (gratuita). |
| `DEEPSEEK_API_KEY` | texto | — | Clave de DeepSeek. |
| `TRANSCRIPTION_BACKEND` | `local` `openai_api` | `local` | `local` = Whisper en tu PC; `openai_api` = API de OpenAI. |
| `TRANSCRIPTION_MODEL` | `tiny` `base` `small` `medium` `large` `large-v2` `large-v3` | `small` | Tamaño del modelo Whisper local. |
| `OUTPUT_DIRECTORY` | ruta | `output` | Carpeta de resultados. |
| `TEMP_DIRECTORY` | ruta | `temp` | Carpeta temporal. |
| `LOGS_DIRECTORY` | ruta | `logs` | Carpeta de logs. |
| `NETWORK_TIMEOUT` | entero (s) | `30` | Timeout de red de `yt-dlp` **y** de las llamadas al proveedor de IA. |
| `MAX_VIDEO_MB` | entero | `200` | Límite de tamaño para archivos locales **y** para el audio descargado de TikTok. |
| `ALLOW_MOCK_FALLBACK` | `true`/`false` | `false` | Si el proveedor elegido no tiene clave, usar `mock` en vez de fallar. |
| `KEEP_TEMP_ON_ERROR` | `true`/`false` | `true` | Conservar `temp/job_<id>/` cuando un procesamiento **falla** (para depurar). Independiente de `--keep-temp` (CLI), que conserva la carpeta **siempre**, incluso en éxito. |

### Conseguir la API key de Gemini (gratis)

1. Entra en <https://aistudio.google.com/apikey>.
2. Pulsa **"Crear clave de API en un proyecto nuevo"**. Si solo te deja elegir un proyecto
   existente, crea uno primero en <https://console.cloud.google.com/projectcreate> y vuelve.
3. Copia el valor y ponlo en `.env`:
   ```env
   GEMINI_API_KEY=el_valor_que_copiaste
   ```
4. No hace falta activar facturación; la capa gratuita funciona con límites por minuto.

---

## 7. Cómo ejecutarlo — todos los comandos

> Activa antes el entorno: `.venv\Scripts\activate`
> (o usa `run.bat` en lugar de `python main.py`, acepta los mismos argumentos).

### Menú interactivo

```bat
python main.py
```

```
1. Procesar un TikTok
2. Procesar múltiples TikToks (input/urls.txt)
3. Procesar archivo de video local
4. Cambiar proveedor de IA           (solo para la sesión actual)
5. Ver configuración
6. Salir
```

### Interfaz gráfica

```bat
python main.py --gui
```

### Un TikTok por URL

```bat
python main.py --url "https://www.tiktok.com/@usuario/video/1234567890123456789"
```

### Indicaciones para la IA (qué priorizar en el informe)

```bat
python main.py --url "..." --instructions "Enfocate en los riesgos de seguridad"
```

Disponible también en el menú interactivo (te lo pregunta al procesar) y en la GUI (cuadro de
texto). Guía el énfasis del informe dentro del mismo formato; no autoriza a la IA a inventar
datos que no estén en la transcripción.

### Un archivo de vídeo (o audio) local  —  plan B si TikTok bloquea

```bat
python main.py --file "C:\Videos\clip.mp4"
```

Formatos: `mp4, mov, mkv, webm, avi, m4v, flv` y audio suelto `mp3, wav, m4a, aac, ogg, flac`.

### Varias URLs en lote

1. Edita `input/urls.txt` (una URL por línea; las líneas vacías y las que empiezan por `#` se
   ignoran).
2. Ejecuta:

```bat
python main.py --urls-file
```

o con una ruta concreta:

```bat
python main.py --urls-file "C:\ruta\mis_urls.txt"
```

### Forzar el proveedor / modelo de IA (sin tocar `.env`)

```bat
python main.py --file "C:\Videos\clip.mp4" --provider gemini
python main.py --file "C:\Videos\clip.mp4" --provider openai --ai-model gpt-4o-mini
python main.py --file "C:\Videos\clip.mp4" --provider deepseek --ai-model deepseek-chat
python main.py --file "C:\Videos\clip.mp4" --provider mock          (sin coste, análisis simulado)
python main.py --url "..." --ai-model gemini-flash-latest
```

### Forzar el modelo de Whisper

```bat
python main.py --file "C:\Videos\clip.mp4" --model medium
python main.py --url "..." --model tiny
```

### Otras opciones

```bat
python main.py --file "C:\Videos\clip.mp4" --no-html     # genera solo el .txt
python main.py --file "C:\Videos\clip.mp4" --keep-temp   # no borra temp/ aunque todo vaya bien
python main.py --config                                  # muestra la configuración y sale
python main.py --help                                    # ayuda de argparse
```

### Combinaciones habituales

```bat
:: Procesado normal de un TikTok con Gemini
python main.py --url "https://www.tiktok.com/@u/video/123..."

:: Lote nocturno, solo TXT, modelo rápido
python main.py --urls-file --no-html --model tiny

:: Probar el pipeline completo sin gastar cuota de IA
python main.py --file "C:\Videos\demo.mp4" --provider mock
```

### Ejecutar los tests

```bat
.venv\Scripts\activate
pytest -q
```

---

## 8. Qué genera

```
output/
├── txt/
│   ├── tiktok_<id>.txt                  (TikTok)
│   └── local_<nombre>_<fecha>.txt       (archivo local)
└── html/
    ├── reporte_tiktok_<id>.html
    └── reporte_local_<nombre>_<fecha>.html
```

### Formato del `.txt`

```
==================================================
INFORMACION DEL VIDEO
=====================
URL:                     ...
FECHA DE PROCESAMIENTO:  AAAA-MM-DD HH:MM:SS
IDIOMA ORIGINAL:         English (en)
IDIOMA DEL REPORTE:      Espanol
TRADUCCION REALIZADA:    Si
DURACION:                00:27
ID DEL VIDEO:            ...

==================================================
TRANSCRIPCION ORIGINAL            (solo aparece si hubo traducción)
======================
[00:00] texto original...

==================================================
TRANSCRIPCION EN ESPANOL
========================
[00:00] texto en español...
```

Si el vídeo ya está en español, solo aparece el bloque **TRANSCRIPCION EN ESPANOL** con el
texto original.

### Estructura del `.html`

Un único archivo **autónomo**: CSS y SVG *inline*, sin JavaScript, sin peticiones externas — se
abre con doble clic en cualquier navegador, incluso sin internet. Cabecera (título, URL/origen,
fecha, idioma original, estado de traducción, proveedor/modelo de IA) + secciones:

**A** Resumen ejecutivo · **B** Explicación detallada · **C** Tecnologías (tabla
Categoría/Elemento + **gráfico de barras SVG** por categoría, si hay más de una) ·
**D** Conceptos técnicos · **E** Arquitectura · **F** Análisis de código ·
**G** Buenas prácticas · **H** Riesgos · **I** Recomendaciones · **J** Nivel de dificultad
(insignia de color) · **K** Aplicaciones · **L** Conclusión.

Incluye estilos `@media print` (se puede "Guardar como PDF" desde el navegador si aún se
necesita ese formato puntualmente). Los nombres técnicos (`React`, `Node.js`, `REST API`,
`Docker`, `Kubernetes`…) se conservan sin traducir. El análisis distingue de forma explícita lo
dicho en el vídeo, lo inferido y las recomendaciones. Pesa una fracción de lo que pesaba el PDF
(unos ~8 KB para un informe típico, frente a ~100 KB).

---

## 9. ¿Dónde queda el audio del TikTok?

**Respuesta corta: en `temp/`, de forma temporal, y se borra automáticamente al terminar.
El vídeo nunca se descarga.**

Ciclo de vida del audio:

```
python main.py --url "...tiktok.com/@u/video/7300000000000000123"
        │
        ▼
temp/job_7300000000000000123/           ← carpeta de trabajo (TempWorkspace)
        ├── audio_7300000000000000123.m4a   ← yt-dlp baja SOLO la pista de audio
        └── audio_16k.wav                    ← FFmpeg lo normaliza a 16 kHz mono (para Whisper)
        │
        ▼   (Whisper transcribe usando audio_16k.wav)
        │
   ¿terminó bien?
        ├── SÍ  → shutil.rmtree("temp/job_7300000000000000123/")   → todo borrado
        └── NO  → si KEEP_TEMP_ON_ERROR=true (por defecto): la carpeta se CONSERVA
                  para poder depurar. Con KEEP_TEMP_ON_ERROR=false: se borra igual.
```

Detalles:

- El código está en `src/tiktok_downloader.py::fetch_audio` (usa `yt-dlp` con
  `format="bestaudio/best"` → nunca pide el vídeo) y en `src/utils.py::TempWorkspace`
  (crea `temp/job_<id>/` al entrar y hace `rmtree` al salir con éxito).
- Para un archivo local (`--file`), no se descarga nada: se usa tu propio archivo y solo se
  crea el `audio_16k.wav` temporal, que también se borra.
- Lo único que **persiste** en disco tras un procesamiento correcto: el `.txt` en
  `output/txt/` y el `.html` en `output/html/`. Y los logs en `logs/` (sin claves ni secretos).
- Si quieres inspeccionar el audio de una ejecución concreta, añade `--keep-temp` y lo
  encontrarás en `temp/job_<id>/`.

---

## 10. Cómo se probó

### 10.1. Tests unitarios (`pytest`) — 121, todos en verde

No hacen descargas reales de TikTok ni llamadas reales a APIs (usan el proveedor `mock`, dobles
del SDK de Gemini y `monkeypatch`), y no necesitan PyTorch ni un display (`gui.py` no tiene
tests automatizados por eso mismo).

| Archivo | Qué cubre |
|---|---|
| `tests/test_url_validation.py` | `validate_url` / `is_tiktok_url`: válidas, inválidas, no-TikTok, enlaces `vm./vt.`, dominios "parecidos" rechazados. |
| `tests/test_utils_filenames.py` | `sanitize_filename` (sin `..`, sin separadores), `safe_output_path` (anti path-traversal), `extract_video_id`, `format_timestamp`. |
| `tests/test_temp_workspace.py` | `TempWorkspace`: se borra en éxito, se conserva con `keep_on_error`/`always_keep` (flags independientes). |
| `tests/test_tiktok_max_filesize.py` | `MAX_VIDEO_MB` se traduce en `max_filesize` para `yt-dlp` al descargar de TikTok. |
| `tests/test_config.py` | Parseo de `.env`, valores por defecto, validación (proveedor/backend/modelo inválidos), creación de carpetas, enmascarado de claves, `resolved_provider()` con/sin fallback a `mock`. |
| `tests/test_language_detector.py` | Detección es/en, nombres de idioma, `is_spanish`, "Whisper gana" ante discrepancia. |
| `tests/test_translator.py` | Español → no traduce; inglés → traduce conservando nº de segmentos y timestamps; términos técnicos intactos; lotes grandes (95 segmentos); fallo persistente se contabiliza (no se silencia). |
| `tests/test_gemini_provider.py` | Clasificación de errores del SDK (auth/rate-limit/sobrecarga 503/genérico), auth no reintenta, autocambio de modelo retirado (case-insensitive, sin bucle), timeout de construcción, **fallback a `GEMINI_FALLBACK_MODEL` tras agotar reintentos**. |
| `tests/test_txt_writer.py` | Cabeceras exactas, líneas `[mm:ss]`, dos secciones si hubo traducción, una sola si el original ya era español, nombre de archivo. |
| `tests/test_ai_parser.py` | `extract_json` (limpio, entre ```` ``` ````, con texto alrededor, anidado, truncado, vacío); `_coerce_report` (relleno de campos, coerción lista↔cadena); `analyze_content` (JSON válido a la 1ª, reintento, doble fallo → informe de reserva, **error del proveedor → informe degradado**, **`AIAuthError` → se propaga**, `user_instructions` se incluye/omite en el prompt). |
| `tests/test_html_generator.py` | Genera HTML válido (bien formado, sin `<script>`); el contenido de la IA se escapa (anti-XSS, dado que en última instancia viene de un vídeo de terceros); acentos y `¿?`; informe vacío; gráfico SVG solo con ≥2 categorías; insignia de dificultad. |

Comando: `pytest -q` → `121 passed`.

### 10.2. Prueba end-to-end real

> Nota: esta prueba se hizo cuando el informe todavía se generaba en `.pdf` (antes del cambio a
> `.html` de la [sección 13](#13-historial-de-cambios)). Se deja tal cual como registro
> histórico; el pipeline y las reglas anti-alucinación no cambiaron, solo el formato de salida.

Como TikTok bloquea la IP de descarga en este entorno (comportamiento esperado, por eso existe
`--file`), la prueba completa se hizo con un **vídeo local generado**:

1. Se sintetizó voz **en inglés** con la voz de Windows "Microsoft Zira" (SAPI) leyendo un
   texto técnico, y se combinó con una pista de vídeo negra → `temp/e2e_input.mp4` (~27 s).
2. Se ejecutó el pipeline completo **con la API key real de Gemini**:
   `python main.py --file "temp/e2e_input.mp4"`.
3. Resultado observado:
   - Consola: `[1/6]…[6/6]`, `Idioma detectado: English`, `Traduciendo contenido al español…`,
     `Traducción completada`, `Procesamiento completado`.
   - `.txt`: bloque de información + `TRANSCRIPCION ORIGINAL` (inglés) + `TRANSCRIPCION EN
     ESPANOL` (traducción **natural**), con `REST API`, `Node.js`, `Express`, `PostgreSQL`,
     `Docker`, `AWS`, `React`, `TypeScript`, `GitHub Actions` **sin traducir**.
   - `.pdf`: **4 páginas, íntegramente en español**, portada + secciones A–L, tabla de
     tecnologías. La regla anti-alucinación funcionó: marcó *"Inferencia técnica: el término
     'Cuba or Nets' de la transcripción se refiere a Kubernetes"* (Whisper `small` transcribe
     mal "Kubernetes" con la voz robótica; con voz real o modelo `medium` mejora).
4. Se **borró** el vídeo de prueba y los temporales. `pip check`: sin conflictos.

### 10.3. Comprobación de errores controlados

- `python main.py --url "no-soy-una-url"` → `URL invalida`.
- `python main.py --url "https://www.youtube.com/watch?v=..."` → `La URL no pertenece a TikTok`.
- `python main.py --url "<TikTok real>"` → yt-dlp devolvió *"Your IP address is blocked"* y la
  app lo tradujo a: *"TikTok ha bloqueado o limitado la petición… usa --file con un archivo de
  vídeo local"*.

---

## 11. Solución de problemas

| Síntoma | Solución |
|---|---|
| `FFmpeg no esta disponible` | Reinstala dependencias (`pip install -r requirements.txt`) o instala FFmpeg del sistema (`winget install --id Gyan.FFmpeg -e`). |
| `TikTok ha bloqueado o limitado la peticion` | Actualiza yt-dlp (`pip install -U yt-dlp`), espera un rato, o descarga el vídeo a mano y usa `--file`. |
| `Unexpected response from webpage request` (con aviso de "impersonation") | Falta `curl_cffi` (TikTok exige imitar el TLS de un navegador). Instala con `pip install -U curl_cffi` (ya está en `requirements.txt`). |
| `El video es privado, restringido…` | El contenido no es público. La app no accede a contenido no público. |
| `gemini: el modelo '…' no existe` | Pon un modelo válido en `AI_MODEL` (o `--ai-model`). Gemini intenta autocorregirse; si no puede, indica el nombre nuevo. |
| Informe degradado con `error 503 UNAVAILABLE` / `high demand` | Capa gratuita de Gemini saturada (temporal, no es un problema de configuración). Ya reintenta con backoff y cae a `GEMINI_FALLBACK_MODEL` si sigue sobrecargado; si aun así falla, espera unos minutos y reprocesa (el `.txt` no se pierde). |
| `Falta GEMINI_API_KEY` / `clave de API rechazada` | Rellena la clave correcta en `.env`, o usa `--provider mock`. |
| Instalación enorme | Es PyTorch (backend Whisper local). Alternativa: `TRANSCRIPTION_BACKEND=openai_api` en `.env`. |
| `faster-whisper` no instala | No se usa: no tiene soporte para Python 3.13. Este proyecto usa `openai-whisper`. |
| La 1.ª transcripción tarda mucho | Descarga el modelo Whisper (`small` ≈ 460 MB) una única vez; y en CPU `medium`/`large` son lentos. Usa `small` o `tiny`. |
| Palabras técnicas mal transcritas | Es precisión de Whisper con audio de baja calidad. Sube a `--model medium`. |
| `--keep-temp` no conserva nada / la GUI no abre | `--keep-temp` conserva `temp/` incluso en éxito (antes no tenía efecto; corregido). La GUI necesita `tkinter` (viene con Python estándar de python.org; no con todas las distribuciones). |

Logs detallados: `logs/run_AAAAMMDD.log` (nunca contienen claves).

---

## 12. Limitaciones y decisiones de diseño

- **Depende de `yt-dlp`** para el audio de TikTok; si TikTok cambia sus mecanismos puede dejar
  de funcionar. El modo `--file` es ciudadano de primera clase y ejercita todo el pipeline.
- **Transcripción local en CPU**: más lenta que con GPU. `small` es el compromiso recomendado.
- **`faster-whisper` no disponible** en Python 3.13 → se usa `openai-whisper` (arrastra
  PyTorch, ~2 GB).
- **Capa gratuita de Gemini**: tiene límites por minuto y sufre picos de sobrecarga (503)
  ocasionales. La traducción va por lotes con reintentos y el análisis cae a
  `GEMINI_FALLBACK_MODEL` si es necesario; aun así puedes toparte con el límite (el `.txt` se
  genera igual y el `.html` sale degradado).
- **API Whisper de OpenAI**: máximo 25 MB por archivo de audio.
- **Nombres de modelo de IA cambian** con el tiempo; se resuelven con `AI_MODEL` / `--ai-model`
  (y autocorrección en Gemini).
- **Calidad del análisis**: depende del proveedor y modelo; el sistema fuerza el idioma
  español y las reglas anti-alucinación, pero conviene revisar el resultado.
- **`gui.py` no tiene tests automatizados**: requiere un display, y la CI (GitHub Actions) corre
  headless. Si se toca, verificar a mano con `python main.py --gui`.
- **OpenAI/DeepSeek existen pero nunca se han validado con una clave real** en este proyecto;
  solo Gemini se usa y prueba de forma habitual.

---

## 13. Historial de cambios

Cada bloque es una sesión de trabajo real (con su fecha), de la más antigua a la más reciente.
El commit exacto de cada una está en `git log --oneline`.

### 2026-09-08/09 — Construcción inicial y publicación

| Cambio | Archivos |
|---|---|
| Modelo Gemini por defecto: `gemini-2.0-flash` → **`gemini-3.6-flash`** (Google retiró el anterior). | `config.py`, `.env.example`, `README.md` |
| **Autocorrección de modelo**: si la API dice "usa `models/xxx`", el proveedor Gemini cambia solo y reintenta. | `src/ai_providers/gemini_provider.py` |
| El **análisis con IA ya no aborta** todo si el proveedor falla (no-auth): se emite un PDF degradado con el motivo; el `.txt` no se ve afectado. `AIAuthError` sí corta, sin reintentos inútiles. | `src/ai_analyzer.py`, `src/translator.py` |
| Nueva opción de CLI **`--ai-model NOMBRE`**. | `main.py` |
| Silenciado un aviso ruidoso del SDK de Google. | `src/ai_providers/gemini_provider.py` |
| Lectura del WAV con el módulo `wave` para no depender de un `ffmpeg.exe` en el PATH (el binario embebido tiene otro nombre). | `src/transcriber.py` |
| 2 tests nuevos (degradación del análisis vs. propagación de `AIAuthError`). | `tests/test_ai_parser.py` |
| Auditoría para repo público: `.env` fuera de Git, `LICENSE` (MIT), CI de pytest. **Publicado en GitHub.** | `.gitignore`, `.github/workflows/tests.yml`, `LICENSE` |

Estado al cierre: 86 tests en verde, E2E real con Gemini verificado de extremo a extremo.

### 2026-09-18 — Seguridad y robustez del proveedor Gemini

| Cambio | Archivos |
|---|---|
| `--keep-temp` no tenía efecto (solo forzaba `KEEP_TEMP_ON_ERROR`, ya `true` por defecto). Se separó en dos flags independientes. | `src/utils.py::TempWorkspace`, `config.py`, `main.py` |
| Timeout de red también para las llamadas a Gemini (`http_options` del SDK); antes podían colgarse indefinidamente. | `src/ai_providers/gemini_provider.py` |
| `MAX_VIDEO_MB` se aplica también a la descarga de audio de TikTok (antes solo a `--file`), vía `max_filesize` de `yt-dlp`. | `src/tiktok_downloader.py` |
| Guardas explícitas contra inyección de instrucciones ocultas en la transcripción (contenido de un vídeo de terceros, no confiable) en los *system prompts*. | `src/translator.py`, `src/ai_analyzer.py` |
| Los fallos de traducción por segmento dejaron de silenciarse: se cuentan y se avisa al usuario. | `src/translator.py`, `src/pipeline.py` |
| Regex de autocambio de modelo (`_MODEL_MOVED`) sensible a mayúsculas → `re.IGNORECASE`. | `src/ai_providers/gemini_provider.py` |
| README: diagramas Mermaid de arquitectura/pipeline y sección de seguridad. | `README.md` |

### 2026-09-20 (mañana) — Interfaz gráfica, indicaciones a la IA, y limpieza de docs

| Cambio | Archivos |
|---|---|
| **Interfaz gráfica** (Tkinter, `python main.py --gui`): URL + indicaciones para la IA, procesamiento en hilo aparte, `messagebox` final con las rutas generadas. | `gui.py` (nuevo) |
| **`user_instructions`**: indicaciones opcionales del usuario sobre qué priorizar en el informe, disponibles en CLI (`--instructions`), menú interactivo y GUI. | `src/ai_analyzer.py`, `src/pipeline.py`, `main.py`, `gui.py` |
| Corregido el error de descarga `Unexpected response from webpage request`: faltaba `curl_cffi` (TikTok exige imitar el TLS de un navegador desde 2026). | `requirements.txt` |
| `CLAUDE.md` (contexto para agentes de IA) se crea pero se saca del repositorio público (es local, no documentación de usuario); se elimina `INFORME_TECNICO.md` y el README queda como única doc pública. | `.gitignore`, `README.md` |

### 2026-09-20 (tarde) — Resiliencia de Gemini ante sobrecarga (503)

Motivo: un usuario reportó un informe degradado con `error 503 UNAVAILABLE` / "high demand" de
Gemini, tras usar `gemini-3.6-flash`.

| Cambio | Archivos |
|---|---|
| Nueva excepción `AIOverloadedError`: el 503/"high demand"/"overloaded" se clasifica aparte del error genérico y comparte el backoff creciente de un rate-limit (antes se agotaba en 2 reintentos con delay fijo). `max_retries` sube de 3 a 4. | `src/ai_providers/base.py`, `src/ai_providers/gemini_provider.py` |
| **Fallback automático de modelo**: si tras agotar los reintentos sigue sobrecargado, se prueba una vez con `GEMINI_FALLBACK_MODEL` (por defecto `gemini-flash-lite-latest`, con más margen libre en el tier gratuito) antes de degradar el informe. | `config.py`, `src/ai_providers/__init__.py`, `src/ai_providers/gemini_provider.py` |

### 2026-09-20 (noche) — PDF → HTML

Motivo: pedido explícito para reducir el peso del informe y poder incluir gráficos/diagramas
reales (ReportLab era muy limitado para eso).

| Cambio | Archivos |
|---|---|
| `src/pdf_generator.py` (ReportLab) eliminado; nuevo `src/html_generator.py`: informe **HTML autónomo** (CSS/SVG *inline*, sin JS, sin peticiones externas), mismas 12 secciones A–L más un gráfico de barras de tecnologías y una insignia de dificultad. Todo el contenido pasa por `html.escape()` (anti-XSS). | `src/html_generator.py` (nuevo), `src/pdf_generator.py` (eliminado) |
| `reportlab` fuera de `requirements.txt` y desinstalado del `.venv` (nada más dependía de él). | `requirements.txt` |
| Renombrados consistentes: `ProcessingResult.pdf_path` → `html_path`, `Config.pdf_dir` → `html_dir` (`output/pdf/` → `output/html/`), `--no-pdf` → `--no-html`. | `src/models.py`, `config.py`, `main.py`, `src/pipeline.py` |
| `gui.py`: ajuste mínimo (mismo diseño) para reflejar `.html` en el mensaje final. | `gui.py` |

Estado al cierre de esta guía: **121 tests en verde**, HTML verificado con un parser (etiquetas
balanceadas, sin `<script>`, gráfico SVG presente) al no haber navegador disponible en esa
sesión para una verificación visual directa.
