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
13. [Cambios de esta sesión](#13-cambios-de-esta-sesión)

---

## 1. Resumen y pipeline

**Extractor_texto_tiktok** es una aplicación de línea de comandos (Python) que, a partir de una
URL de TikTok **o** de un archivo de vídeo local, produce:

- un archivo **`.txt`** con la información del vídeo + la transcripción original + la traducción
  al español, y
- un **informe técnico `.pdf`** profesional, **redactado íntegramente en español**, generado
  por una IA que analiza el contenido.

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
   [5b] análisis técnico con IA   (JSON con 12 apartados; reglas anti-alucinación)
          │
   [6] generar  output/pdf/reporte_<id>.pdf   (portada + secciones A–L, en español)
```

**Nunca se descarga ni se guarda el vídeo.** Solo se obtiene la pista de audio, de forma
temporal, y se borra al terminar (ver [sección 9](#9-dónde-queda-el-audio-del-tiktok)).

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
13. `src/pdf_generator.py` (ReportLab: portada + secciones A–L + numeración + fuente Unicode).
14. `src/pipeline.py` (orquestador de las 6 etapas) + `main.py` (CLI + menú interactivo).
15. `tests/` (86 tests con `pytest`, todos con mocks; sin red ni torch).
16. Documentación (`README.md` y esta guía).

### 2.4. Incidencia resuelta durante las pruebas

Al probar con una API key real de Gemini, la API respondió **404: el modelo `gemini-2.0-flash`
ya no está disponible; usa `gemini-3.6-flash`** (Google lo retiró).

Correcciones aplicadas:

- Modelo Gemini por defecto → **`gemini-3.6-flash`**.
- **Autocorrección de modelo**: si la API devuelve un 404 indicando el sustituto
  (`use models/xxx`), el proveedor Gemini cambia solo al modelo nuevo y reintenta una vez.
- **El análisis con IA ya no aborta todo el procesamiento** si el proveedor falla (cuota
  agotada, modelo caído, red): el `.txt` se genera igualmente y el `.pdf` sale en modo
  degradado dejando constancia del motivo. Solo `AIAuthError` (clave inválida/ausente) corta
  el proceso, y sin reintentos inútiles.
- Nueva opción de CLI `--ai-model NOMBRE` para forzar el modelo del proveedor.

---

## 3. Arquitectura y módulos

```
Extractor_texto_tiktok/
├── main.py                     # CLI (argparse) + menú interactivo de 6 opciones
├── config.py                   # Config (dataclass) desde .env: validación, rutas, claves enmascaradas
├── requirements.txt            # dependencias
├── .env / .env.example         # credenciales y ajustes (.env está en .gitignore)
├── run.bat                     # lanzador Windows: crea .venv + instala deps la 1ª vez
├── README.md                   # manual de usuario
├── GUIA_DEL_PROYECTO.md        # este documento
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
│   ├── ai_analyzer.py          # analyze_content(): prompt + JSON → AnalysisReport; informe degradado
│   ├── txt_writer.py           # build_txt / write_txt: formato exacto del .txt
│   ├── pdf_generator.py        # build_pdf: ReportLab, portada + A–L, "Página X de Y", Unicode
│   ├── utils.py                # logging+SecretFilter, sanitize_filename, safe_output_path,
│   │                           #   extract_video_id, format_timestamp, extract_json,
│   │                           #   resolve_ffmpeg, TempWorkspace, read_urls_file
│   └── ai_providers/
│       ├── __init__.py         # get_provider(name, cfg) -> AIProvider
│       ├── base.py             # AIProvider (ABC): complete(), complete_json(), reintentos/backoff
│       ├── openai_provider.py  # SDK openai; response_format JSON
│       ├── gemini_provider.py  # SDK google-genai; autocorrección de modelo retirado
│       ├── deepseek_provider.py# = OpenAIProvider con base_url de DeepSeek
│       └── mock_provider.py    # respuestas deterministas offline (tests / sin clave)
│
├── input/urls.txt              # una URL por línea (para procesar en lote)
├── output/txt/  ·  output/pdf/ # resultados
├── temp/                       # carpetas de trabajo temporales (se borran al terminar)
├── logs/                       # logs diarios (sin secretos)
└── tests/                      # 86 tests pytest
```

### Responsabilidad de cada archivo

| Archivo | Qué hace |
|---|---|
| `main.py` | Analiza argumentos; si no hay, muestra el menú de 6 opciones. Carga `Config`, aplica overrides de CLI, arranca el logging y llama al `pipeline`. |
| `config.py` | `Config.load()` lee `.env` + variables de entorno, valida (`AI_PROVIDER`, backend, modelo Whisper), crea carpetas, y enmascara las claves para mostrarlas. `DEFAULT_AI_MODELS` define el modelo por defecto de cada proveedor. |
| `src/pipeline.py` | Ejecuta las 6 etapas en orden, imprime `[1/6]…[6/6]` y los `[INFO]/[OK]`, gestiona la carpeta temporal (`TempWorkspace`) y devuelve un `ProcessingResult` con rutas y errores. |
| `src/tiktok_downloader.py` | `validate_url` (http/https + host), `is_tiktok_url` (dominios de TikTok), `fetch_audio(url, workdir)` con `yt-dlp` `format="bestaudio/best"`; mapea los errores de yt-dlp a mensajes claros (privado, geobloqueo, 403/rate-limit, no encontrado). No usa cookies ni login. |
| `src/local_video.py` | Comprueba que el archivo existe y que la extensión está soportada (`mp4, mov, mkv, webm, avi, m4v, flv` y audio suelto: `mp3, wav, m4a, aac, ogg, flac`). |
| `src/audio_extractor.py` | `extract_audio()` llama a FFmpeg (`-vn -ac 1 -ar 16000 -c:a pcm_s16le`) para dejar un WAV que Whisper procesa bien. Si no hay FFmpeg, error con instrucciones. |
| `src/transcriber.py` | `transcribe()`. Backend `local`: `whisper.load_model()` (cacheado) y `model.transcribe(array)`; lee el WAV con `wave` para no depender del `ffmpeg` del PATH. Backend `openai_api`: `client.audio.transcriptions.create(model="whisper-1")` (límite 25 MB). |
| `src/language_detector.py` | `detect_language()`: usa el idioma que devuelve Whisper (basado en audio) como primario y `langdetect` sobre el texto como verificación. Devuelve `LanguageInfo(code, name, is_spanish, …)`. |
| `src/translator.py` | Si el idioma ya es español → no traduce. Si no → traduce por lotes de ~40 segmentos con el proveedor de IA; conserva `start/end`, el nº de segmentos y los términos técnicos (React, Node.js, REST API, OAuth 2.0, Docker, Kubernetes…). Degrada a traducción segmento-a-segmento si un lote falla; `AIAuthError` corta. |
| `src/ai_analyzer.py` | Construye el prompt (transcripción ES como contenido principal + original para verificar términos) con reglas anti-alucinación (distinguir *información explícita* / *inferencia* / *recomendación*; no inventar). Pide JSON, lo valida/repara → `AnalysisReport`. Si el JSON es irrecuperable → informe de reserva. Si el proveedor falla (no-auth) → informe degradado (no rompe el pipeline). |
| `src/txt_writer.py` | Genera el `.txt` con el formato exacto: bloque `INFORMACION DEL VIDEO`, luego `TRANSCRIPCION ORIGINAL` (solo si hubo traducción) y `TRANSCRIPCION EN ESPANOL`, con líneas `[mm:ss] texto`. UTF-8. |
| `src/pdf_generator.py` | ReportLab/Platypus. Registra Arial de `C:\Windows\Fonts` (o Helvetica) para acentos/`ñ`/`¿¡`. Portada + secciones **A–L**, tabla de tecnologías, recuadro de dificultad, pie `Página X de Y`, encabezado. |
| `src/utils.py` | Utilidades transversales: logging a `logs/run_AAAAMMDD.log` con `SecretFilter` (redacta claves), `sanitize_filename`, `safe_output_path` (anti path-traversal), `extract_video_id`, `format_timestamp`, `extract_json` (tolera ```` ``` ````, texto alrededor, JSON truncado), `resolve_ffmpeg`, `TempWorkspace` (borra la carpeta al salir con éxito), `read_urls_file`. |
| `src/ai_providers/base.py` | `AIProvider` (ABC). `complete()` con reintentos y backoff ante rate-limit/errores transitorios; `complete_json()` usa `extract_json`. Excepciones: `AIProviderError`, `AIAuthError`, `AIRateLimitError`. |
| `src/ai_providers/gemini_provider.py` | SDK `google-genai`. Mapea 401/403 → `AIAuthError`, 429/quota → `AIRateLimitError`, 404 modelo retirado → **cambia al modelo que indica la API y reintenta**. |
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
- `ProcessingResult` — id, rutas de TXT/PDF, idioma, si hubo traducción, proveedor/modelo,
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
| `OPENAI_API_KEY` | texto | — | Clave de OpenAI. |
| `GEMINI_API_KEY` | texto | — | Clave de Google AI Studio (gratuita). |
| `DEEPSEEK_API_KEY` | texto | — | Clave de DeepSeek. |
| `TRANSCRIPTION_BACKEND` | `local` `openai_api` | `local` | `local` = Whisper en tu PC; `openai_api` = API de OpenAI. |
| `TRANSCRIPTION_MODEL` | `tiny` `base` `small` `medium` `large` `large-v2` `large-v3` | `small` | Tamaño del modelo Whisper local. |
| `OUTPUT_DIRECTORY` | ruta | `output` | Carpeta de resultados. |
| `TEMP_DIRECTORY` | ruta | `temp` | Carpeta temporal. |
| `LOGS_DIRECTORY` | ruta | `logs` | Carpeta de logs. |
| `NETWORK_TIMEOUT` | entero (s) | `30` | Timeout de red de `yt-dlp`. |
| `MAX_VIDEO_MB` | entero | `200` | Límite de tamaño para archivos locales. |
| `ALLOW_MOCK_FALLBACK` | `true`/`false` | `false` | Si el proveedor elegido no tiene clave, usar `mock` en vez de fallar. |
| `KEEP_TEMP_ON_ERROR` | `true`/`false` | `true` | Conservar `temp/job_<id>/` cuando un procesamiento **falla** (para depurar). |

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

### Un TikTok por URL

```bat
python main.py --url "https://www.tiktok.com/@usuario/video/1234567890123456789"
```

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
python main.py --file "C:\Videos\clip.mp4" --no-pdf      # genera solo el .txt
python main.py --file "C:\Videos\clip.mp4" --keep-temp   # no borra temp/ aunque todo vaya bien
python main.py --config                                  # muestra la configuración y sale
python main.py --help                                    # ayuda de argparse
```

### Combinaciones habituales

```bat
:: Procesado normal de un TikTok con Gemini
python main.py --url "https://www.tiktok.com/@u/video/123..."

:: Lote nocturno, solo TXT, modelo rápido
python main.py --urls-file --no-pdf --model tiny

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
│   ├── tiktok_<id>.txt                 (TikTok)
│   └── local_<nombre>_<fecha>.txt      (archivo local)
└── pdf/
    ├── reporte_tiktok_<id>.pdf
    └── reporte_local_<nombre>_<fecha>.pdf
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

### Estructura del `.pdf`

Portada (título, URL/origen, fecha, idioma original, estado de traducción, proveedor/modelo de
IA, dificultad) + secciones:

**A** Resumen ejecutivo · **B** Explicación detallada · **C** Tecnologías (tabla
Categoría/Elemento) · **D** Conceptos técnicos · **E** Arquitectura · **F** Análisis de código ·
**G** Buenas prácticas · **H** Riesgos · **I** Recomendaciones · **J** Nivel de dificultad ·
**K** Aplicaciones · **L** Conclusión.

Con numeración `Página X de Y`, encabezado, y acentos/`ñ`/`¿¡` correctos. Los nombres técnicos
(`React`, `Node.js`, `REST API`, `Docker`, `Kubernetes`…) se conservan sin traducir. El
análisis distingue de forma explícita lo dicho en el vídeo, lo inferido y las recomendaciones.

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
  `output/txt/` y el `.pdf` en `output/pdf/`. Y los logs en `logs/` (sin claves ni secretos).
- Si quieres inspeccionar el audio de una ejecución concreta, añade `--keep-temp` y lo
  encontrarás en `temp/job_<id>/`.

---

## 10. Cómo se probó

### 10.1. Tests unitarios (`pytest`) — 86, todos en verde

No hacen descargas reales de TikTok ni llamadas reales a APIs (usan el proveedor `mock` y
`monkeypatch`), y no necesitan PyTorch.

| Archivo | Qué cubre |
|---|---|
| `tests/test_url_validation.py` | `validate_url` / `is_tiktok_url`: válidas, inválidas, no-TikTok, enlaces `vm./vt.`, dominios "parecidos" rechazados. |
| `tests/test_utils_filenames.py` | `sanitize_filename` (sin `..`, sin separadores), `safe_output_path` (anti path-traversal), `extract_video_id`, `format_timestamp`. |
| `tests/test_config.py` | Parseo de `.env`, valores por defecto, validación (proveedor/backend/modelo inválidos), creación de carpetas, enmascarado de claves, `resolved_provider()` con/sin fallback a `mock`. |
| `tests/test_language_detector.py` | Detección es/en, nombres de idioma, `is_spanish`, "Whisper gana" ante discrepancia. |
| `tests/test_translator.py` | Español → no traduce; inglés → traduce conservando nº de segmentos y timestamps; términos técnicos intactos; lotes grandes (95 segmentos). |
| `tests/test_txt_writer.py` | Cabeceras exactas, líneas `[mm:ss]`, dos secciones si hubo traducción, una sola si el original ya era español, nombre de archivo. |
| `tests/test_ai_parser.py` | `extract_json` (limpio, entre ```` ``` ````, con texto alrededor, anidado, truncado, vacío); `_coerce_report` (relleno de campos, coerción lista↔cadena); `analyze_content` (JSON válido a la 1ª, reintento, doble fallo → informe de reserva, **error del proveedor → informe degradado**, **`AIAuthError` → se propaga**). |
| `tests/test_pdf_generator.py` | Genera PDF en carpeta temporal: existe, empieza por `%PDF`, > 2 KB; acentos y `¿?`; informe vacío; tecnologías como lista de cadenas. |

Comando: `pytest -q` → `86 passed`.

### 10.2. Prueba end-to-end real

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
| `El video es privado, restringido…` | El contenido no es público. La app no accede a contenido no público. |
| `gemini: el modelo '…' no existe` | Pon un modelo válido en `AI_MODEL` (o `--ai-model`). Gemini intenta autocorregirse; si no puede, indica el nombre nuevo. |
| `Falta GEMINI_API_KEY` / `clave de API rechazada` | Rellena la clave correcta en `.env`, o usa `--provider mock`. |
| Instalación enorme | Es PyTorch (backend Whisper local). Alternativa: `TRANSCRIPTION_BACKEND=openai_api` en `.env`. |
| `faster-whisper` no instala | No se usa: no tiene soporte para Python 3.13. Este proyecto usa `openai-whisper`. |
| La 1.ª transcripción tarda mucho | Descarga el modelo Whisper (`small` ≈ 460 MB) una única vez; y en CPU `medium`/`large` son lentos. Usa `small` o `tiny`. |
| Palabras técnicas mal transcritas | Es precisión de Whisper con audio de baja calidad. Sube a `--model medium`. |
| El PDF usa otra tipografía | Si no está `C:\Windows\Fonts\arial.ttf`, usa Helvetica; el español se renderiza igual. |

Logs detallados: `logs/run_AAAAMMDD.log` (nunca contienen claves).

---

## 12. Limitaciones y decisiones de diseño

- **Depende de `yt-dlp`** para el audio de TikTok; si TikTok cambia sus mecanismos puede dejar
  de funcionar. El modo `--file` es ciudadano de primera clase y ejercita todo el pipeline.
- **Transcripción local en CPU**: más lenta que con GPU. `small` es el compromiso recomendado.
- **`faster-whisper` no disponible** en Python 3.13 → se usa `openai-whisper` (arrastra
  PyTorch, ~2 GB).
- **Capa gratuita de Gemini**: tiene límites por minuto. La traducción va por lotes con
  reintentos; aun así puedes toparte con el límite (el `.txt` se genera igual y el `.pdf` sale
  degradado).
- **API Whisper de OpenAI**: máximo 25 MB por archivo de audio.
- **Nombres de modelo de IA cambian** con el tiempo; se resuelven con `AI_MODEL` / `--ai-model`
  (y autocorrección en Gemini).
- **Calidad del análisis**: depende del proveedor y modelo; el sistema fuerza el idioma
  español y las reglas anti-alucinación, pero conviene revisar el resultado.

---

## 13. Cambios de esta sesión

| Cambio | Archivos |
|---|---|
| Modelo Gemini por defecto: `gemini-2.0-flash` → **`gemini-3.6-flash`** (Google retiró el anterior). | `config.py`, `.env.example`, `README.md` |
| **Autocorrección de modelo**: si la API dice "usa `models/xxx`", el proveedor Gemini cambia solo y reintenta. | `src/ai_providers/gemini_provider.py` |
| El **análisis con IA ya no aborta** todo si el proveedor falla (no-auth): se emite un PDF degradado con el motivo; el `.txt` no se ve afectado. `AIAuthError` sí corta, sin reintentos inútiles. | `src/ai_analyzer.py`, `src/translator.py` |
| Nueva opción de CLI **`--ai-model NOMBRE`**. | `main.py` |
| Silenciado un aviso ruidoso del SDK de Google. | `src/ai_providers/gemini_provider.py` |
| Lectura del WAV con el módulo `wave` para no depender de un `ffmpeg.exe` en el PATH (el binario embebido tiene otro nombre). | `src/transcriber.py` |
| 2 tests nuevos (degradación del análisis vs. propagación de `AIAuthError`). | `tests/test_ai_parser.py` |

Estado final: **86 tests en verde**, E2E real con Gemini verificado de extremo a extremo.
