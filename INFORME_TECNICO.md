# Informe técnico — Extractor_texto_tiktok

> Documento de arquitectura e implementación. Describe **qué hace** el sistema, **cómo está
> construido**, **qué tecnologías usa y por qué**, y las **decisiones de diseño** tomadas.
> Para instalación y uso, consulta el [README](README.md). Para el registro de construcción y
> operación detallada, consulta [GUIA_DEL_PROYECTO.md](GUIA_DEL_PROYECTO.md).

---

## Índice

1. [Propósito y alcance](#1-propósito-y-alcance)
2. [Vista general de la arquitectura](#2-vista-general-de-la-arquitectura)
3. [El pipeline etapa por etapa](#3-el-pipeline-etapa-por-etapa)
4. [Capa de proveedores de IA](#4-capa-de-proveedores-de-ia)
5. [Generación de salidas (TXT y PDF)](#5-generación-de-salidas-txt-y-pdf)
6. [Configuración](#6-configuración)
7. [Modelo de datos](#7-modelo-de-datos)
8. [Seguridad y privacidad](#8-seguridad-y-privacidad)
9. [Manejo de errores y resiliencia](#9-manejo-de-errores-y-resiliencia)
10. [Stack tecnológico](#10-stack-tecnológico)
11. [Decisiones de diseño y trade-offs](#11-decisiones-de-diseño-y-trade-offs)
12. [Pruebas e integración continua](#12-pruebas-e-integración-continua)
13. [Rendimiento](#13-rendimiento)
14. [Limitaciones conocidas](#14-limitaciones-conocidas)
15. [Estructura del repositorio](#15-estructura-del-repositorio)

---

## 1. Propósito y alcance

**Extractor_texto_tiktok** es una aplicación de línea de comandos escrita en Python que, a
partir de la **URL de un vídeo público de TikTok** o de un **archivo de vídeo/audio local**,
produce dos artefactos:

- un archivo **`.txt`** con los metadatos del vídeo, la transcripción original y —si el idioma
  no era español— su traducción al español;
- un **informe técnico en `.pdf`**, redactado íntegramente en español, generado por un modelo
  de IA que analiza el contenido con reglas anti-alucinación.

### No-objetivos (decisiones explícitas de alcance)

| Se hace | No se hace |
|---|---|
| Descargar **solo la pista de audio** de una URL, a un archivo temporal. | Descargar o almacenar el **vídeo**. |
| Procesar contenido **público**. | Acceder a cuentas privadas, usar cookies de sesión, resolver captchas o eludir controles de acceso. |
| Transcribir y traducir en local por defecto. | Enviar el audio a servicios de terceros salvo que el usuario active explícitamente el backend de API. |
| Borrar los temporales al terminar. | Conservar el audio (salvo `--keep-temp` o fallo con `KEEP_TEMP_ON_ERROR=true`). |

---

## 2. Vista general de la arquitectura

El sistema es un **pipeline lineal de 6 etapas** orquestado por `src/pipeline.py::_process()`.
Cada etapa es un módulo independiente que recibe y devuelve `dataclasses` simples
(`src/models.py`), sin estado global compartido. Esto mantiene las piezas desacopladas y
testeables de forma aislada.

```
  URL de TikTok  ó  archivo local (--file)
          │
   [1] Obtención de audio          src/tiktok_downloader.py  (yt-dlp: SOLO audio)
          │                        src/local_video.py        (validación de archivo local)
          ▼
   [2] Normalización de audio      src/audio_extractor.py    (FFmpeg → WAV 16 kHz mono PCM)
          ▼
   [3] Transcripción               src/transcriber.py        (openai-whisper local / API OpenAI)
          ▼
   [4] Detección de idioma         src/language_detector.py  (Whisper + verificación langdetect)
          │
   ┌──────┴───────────────┐
 español                otro idioma
   │                       │
   │              [5a] Traducción al español   src/translator.py   (por lotes, vía proveedor IA)
   └──────┬───────────────┘
          ▼
   Escritura del .txt              src/txt_writer.py
          ▼
   [5b] Análisis técnico con IA    src/ai_analyzer.py        (prompt anti-alucinación → JSON)
          ▼
   [6] Generación del .pdf         src/pdf_generator.py      (ReportLab / Platypus)
```

Componentes transversales:

- **`config.py`** — carga y valida la configuración desde `.env` / variables de entorno.
- **`src/ai_providers/`** — capa de abstracción de proveedores de IA (patrón *Strategy*).
- **`src/utils.py`** — logging con redacción de secretos, rutas seguras, resolución de FFmpeg,
  parseo tolerante de JSON, gestión del espacio de trabajo temporal.
- **`main.py`** — CLI (`argparse`) + menú interactivo + modo lote.

---

## 3. El pipeline etapa por etapa

### Etapa 1 — Obtención de audio

**Desde una URL** (`src/tiktok_downloader.py::fetch_audio`):

1. Se valida que la cadena sea una URL `http(s)` con host de TikTok
   (`tiktok.com`, `www.`, `m.`, `vm.`, `vt.` y cualquier subdominio `*.tiktok.com`).
   URLs de otros dominios se rechazan con un mensaje que remite a `--file`.
2. Se invoca **`yt-dlp`** con `format="bestaudio/best"` → nunca se solicita la pista de vídeo.
   Opciones relevantes: `noplaylist`, `restrictfilenames`, `socket_timeout` configurable,
   `retries=3`. **Sin `cookiefile` ni credenciales**: solo contenido público.
3. Los errores de `yt-dlp` se traducen a mensajes de usuario accionables mediante
   `_friendly_download_error()`: privado/restringido, geobloqueo, 404, y
   rate-limit / captcha / 403 (el caso habitual cuando TikTok bloquea la IP).
4. Se devuelve un `RemoteMedia` con la ruta del audio y metadatos
   (`video_id`, `title`, `duration`, `uploader`, `webpage_url`).

**Desde un archivo local** (`src/local_video.py::validate_local_media`):

- Extensiones de vídeo aceptadas: `.mp4 .mov .mkv .webm .avi .m4v .flv`.
- Extensiones de audio aceptadas: `.mp3 .wav .m4a .aac .ogg .flac`.
- Se comprueba existencia, que sea un fichero y el límite `MAX_VIDEO_MB` (por defecto 200).

### Etapa 2 — Normalización de audio

`src/audio_extractor.py::extract_audio` ejecuta **FFmpeg** como subproceso para convertir
cualquier entrada a **WAV PCM `s16le`, 16 kHz, mono** (`-vn` descarta cualquier pista de
vídeo). Es el formato que espera Whisper y elimina variabilidad de códecs.

- **Resolución de FFmpeg** (`src/utils.py::resolve_ffmpeg`): primero `shutil.which("ffmpeg")`
  (FFmpeg del sistema); si no hay, el binario que trae **`imageio-ffmpeg`**. La carpeta del
  ejecutable se antepone al `PATH` del proceso. Resultado cacheado en variable de módulo.
- Salvaguardas: timeout de 30 min, verificación de código de retorno, y comprobación de que
  el WAV resultante pesa > 1 KB (un archivo vacío indica vídeo sin pista de audio).
- `probe_duration()` usa `ffprobe` si está disponible para obtener la duración real.

### Etapa 3 — Transcripción

`src/transcriber.py`. Dos backends seleccionables con `TRANSCRIPTION_BACKEND`:

**`local` (por defecto)** — `openai-whisper` ejecutándose en la máquina (offline, gratis):

- El import de `whisper` / `torch` es **perezoso**: los tests no necesitan esas dependencias.
- El modelo se **cachea** en `_local_model_cache` para no recargarlo en cada elemento de un lote.
- El WAV se lee con el módulo estándar **`wave`** y se convierte a un `ndarray` `float32`
  normalizado a `[-1, 1]` con NumPy, que se pasa directamente a `model.transcribe()`. Esto
  **evita que Whisper invoque `ffmpeg` por su cuenta** (el binario embebido de `imageio-ffmpeg`
  no se llama `ffmpeg.exe`, así que Whisper no lo encontraría en el PATH). Incluye un
  remuestreo lineal de seguridad por si el WAV no viniera a 16 kHz.
- Se llama con `task="transcribe"`, `fp16=False` (CPU).

**`openai_api`** — API de OpenAI (`whisper-1`), de pago:

- Requiere `OPENAI_API_KEY`. Límite duro de **25 MB** por archivo de audio (se verifica antes
  de subir). `response_format="verbose_json"` para obtener segmentos con timestamps.

Ambos backends devuelven un `Transcript` con `segments: list[Segment]` (start, end, text),
`language` (código ISO detectado), `duration` y `source`.

### Etapa 4 — Detección de idioma

`src/language_detector.py::detect_language`. Estrategia de doble fuente:

1. **Primaria**: el idioma que devuelve Whisper (se basa en el audio, más fiable).
2. **Secundaria (verificación)**: `langdetect` sobre el texto transcrito completo (solo si hay
   ≥ 20 caracteres; `DetectorFactory.seed = 0` para determinismo).
3. Si discrepan, se registra un `WARNING` pero **se confía en Whisper**. `langdetect` solo
   "gana" si Whisper no devolvió idioma.

Produce un `LanguageInfo` con `code`, `name` (nombre legible desde una tabla ISO 639-1),
`is_spanish`, `method` (`whisper` / `whisper+langdetect` / `langdetect`) y `secondary_code`.

### Etapa 5a — Traducción al español

`src/translator.py::translate_to_spanish`. **Solo se ejecuta si el idioma no es español**
(si ya lo es, se devuelven los segmentos tal cual con `translated=False`).

- Los segmentos se procesan **en lotes de 40** (`BATCH_SIZE`). Cada lote se envía como un
  objeto JSON `{"segments": [{"i": 0, "text": "..."}, ...]}` y se exige la misma estructura de
  vuelta, preservando el índice `i` (y por tanto los timestamps, que se reasocian por posición).
- El *system prompt* fija reglas: traducción técnica natural (no literal) y **no traducir**
  nombres propios, marcas, lenguajes, frameworks, librerías, APIs, protocolos ni herramientas
  (React, Node.js, REST API, OAuth 2.0, Docker, Kubernetes, PostgreSQL, …).
- **Degradación en cascada**: si la traducción por lote falla o devuelve un JSON inválido, se
  reintenta **segmento a segmento**; si un segmento concreto tampoco se puede traducir, **se
  conserva el texto original** en su lugar (nunca se pierde una línea). `AIAuthError` corta el
  proceso (sin clave válida no tiene sentido reintentar).
- El parseo de la respuesta usa `src/utils.py::extract_json`, tolerante a JSON rodeado de
  ```` ``` ````, con texto alrededor o con un único bloque `{...}` balanceado.

### Etapa 5b — Análisis técnico con IA

`src/ai_analyzer.py::analyze_content`. Entrada: la transcripción **en español** (contenido
principal); si hubo traducción, se adjunta también la original *solo* para que el modelo
verifique la terminología técnica.

**Reglas anti-alucinación** codificadas en el *system prompt*:

- Analizar solo lo presente en el contenido o inferible de forma razonable; **no inventar**
  tecnologías, arquitecturas ni código.
- Distinguir explícitamente tres niveles, con prefijos literales:
  *información explícita* · `Inferencia técnica:` · `Recomendación:`.
- Si no hay evidencia para una sección: texto fijo
  *"No se puede determinar con certeza a partir del contenido disponible."*

**Esquema de salida** (JSON → `AnalysisReport`, 15 campos): `title`, `original_language`,
`translated_to_spanish`, `executive_summary`, `detailed_explanation`, `technologies[]`
(objetos `{category, name}`), `technical_concepts[]`, `architecture`, `code_analysis`,
`best_practices[]`, `risks[]`, `recommendations[]`, `difficulty` (Básico/Intermedio/
Avanzado/Experto + justificación), `applications[]`, `conclusion`.

**Robustez del parseo**:

- Si la respuesta no es JSON válido → **un reintento** con un recordatorio más estricto.
- Si el segundo intento también falla → **informe de reserva** (`_fallback_report`) que
  incrusta la respuesta en bruto para no perder información.
- Si el proveedor devuelve un error de servicio (rate-limit agotado, modelo caído, red) →
  **informe degradado** (`_provider_error_report`) que deja constancia del motivo; **el `.txt`
  ya se generó** y no se ve afectado.
- `AIAuthError` (credenciales inválidas) → se propaga y aborta.
- `_coerce_report()` normaliza tipos (lista ↔ cadena), rellena campos vacíos con el texto por
  defecto y registra qué campos rellenó en `parse_warning`.

### Etapa 6 — PDF

Ver [sección 5](#5-generación-de-salidas-txt-y-pdf).

---

## 4. Capa de proveedores de IA

Directorio `src/ai_providers/`. Objetivo: **cambiar de proveedor no debe requerir tocar el
resto del programa**.

### Contrato común — `base.py::AIProvider` (clase base abstracta)

- Método abstracto `_complete_raw(system, user, want_json, max_tokens) -> str` que implementa
  cada proveedor concreto.
- Método público `complete(...)` con **reintentos y backoff**: `max_retries = 3`,
  `retry_base_delay = 4.0 s`. Ante `AIRateLimitError` espera `delay * intento`; ante otros
  `AIProviderError`, espera fijo; `AIAuthError` se propaga sin reintentar.
- `complete_json()` = `complete()` + `extract_json()`.

### Jerarquía de excepciones

```
ExtractorError
└── AIProviderError          (fallo del proveedor, ya traducido a lenguaje de usuario)
    ├── AIAuthError          (falta la clave o es inválida → aborta)
    └── AIRateLimitError     (límite/cuota alcanzado → reintenta con backoff)
```

### Proveedores concretos

| Proveedor | Clase | SDK | Modelo por defecto | Notas |
|---|---|---|---|---|
| **Gemini** | `GeminiProvider` | `google-genai` | `gemini-3.6-flash` | Única capa gratuita. `temperature=0.2`, `response_mime_type="application/json"` cuando se pide JSON. **Autocorrección de modelo**: si la API responde 404 con *"use models/xxx"*, cambia `self.model` y reintenta una vez. |
| **OpenAI** | `OpenAIProvider` | `openai` | `gpt-4o-mini` | `chat.completions` con `response_format={"type":"json_object"}`. Mapea `AuthenticationError`/`RateLimitError`/`APIConnectionError`/`APIStatusError` a la jerarquía propia. |
| **DeepSeek** | `DeepSeekProvider` | `openai` (reutilizado) | `deepseek-chat` | Hereda de `OpenAIProvider` cambiando únicamente `base_url = https://api.deepseek.com`. |
| **mock** | `MockProvider` | — | `mock-1` | Proveedor simulado offline. Lo usan los tests y sirve para ejercitar el pipeline sin claves ni coste. **No hace análisis real.** |

### Fábrica — `src/ai_providers/__init__.py::get_provider(name, cfg)`

Devuelve la instancia adecuada; los imports de cada SDK son perezosos (dentro de la rama
correspondiente) para no cargar dependencias no usadas. El modelo efectivo es
`cfg.ai_model` o el `DEFAULT_AI_MODELS[name]` de `config.py`.

> **Nota operativa**: los proveedores retiran modelos con el tiempo. La respuesta es cambiar
> `AI_MODEL` en `.env` o pasar `--ai-model NOMBRE`; Gemini además intenta autocorregirse.

---

## 5. Generación de salidas (TXT y PDF)

### Archivo `.txt` — `src/txt_writer.py`

Formato de texto plano UTF-8 con secciones delimitadas por `=`:

```
INFORMACION DEL VIDEO   → URL, fecha, idioma original (nombre + código), traducción sí/no,
                          duración (MM:SS), ID del vídeo
TRANSCRIPCION ORIGINAL  → solo si hubo traducción; líneas "[MM:SS] texto"
TRANSCRIPCION EN ESPANOL → siempre; si el original ya era español, es la única sección
```

Nombre: `tiktok_<id>.txt` si el id es numérico; si no, `<id>.txt` (archivos locales:
`local_<nombre>_<timestamp>.txt`).

### Informe `.pdf` — `src/pdf_generator.py` (ReportLab / Platypus)

- **`BaseDocTemplate`** con dos `PageTemplate`: `cover` (portada con banda de color) y
  `content` (encabezado con el título + línea). Página A4, márgenes de 2,2 cm.
- **`NumberedCanvas`** (subclase de `canvas.Canvas`): bufferiza las páginas para poder
  escribir *"Página X de Y"* en el pie (la portada no lleva pie).
- **Portada**: título fijo *"INFORME TECNICO DE VIDEO"*, título del análisis, y metadatos
  (URL/origen, fecha, idioma original, traducción, duración, proveedor + modelo de IA, nivel
  de dificultad). Si el informe salió degradado, se imprime la nota de `parse_warning`.
- **12 secciones A–L**: A Resumen ejecutivo · B Explicación detallada · C Tecnologías (tabla
  *Categoría / Elemento* con filas alternas) · D Conceptos técnicos · E Arquitectura ·
  F Análisis de código · G Buenas prácticas · H Riesgos · I Recomendaciones · J Nivel de
  dificultad (*callout*) · K Aplicaciones · L Conclusión. Las listas se renderizan como
  viñetas; si una lista viene vacía se imprime un texto neutro.
- **Fuentes**: si existe `C:\Windows\Fonts\arial.ttf` se registra Arial (y sus variantes
  bold/italic) para cobertura Unicode completa (acentos, `ñ`, `¿ ¡`, `ü`); si no, se usa
  Helvetica base-14. El texto se escapa (`& < >`) antes de pasarlo a `Paragraph`.
- Metadatos del PDF: `title` y `author = "Extractor_texto_tiktok"`.

---

## 6. Configuración

`config.py`. Se carga `.env` con `python-dotenv` (con *fallback* a un `load_dotenv` no-op si
la librería no está). Toda la configuración vive en la `dataclass` **`Config`**, construida en
`Config.load()`:

| Variable | Valores | Defecto | Rol |
|---|---|---|---|
| `AI_PROVIDER` | `gemini` `openai` `deepseek` `mock` | `gemini` | Proveedor de traducción + análisis. |
| `AI_MODEL` | texto | *(vacío → modelo por defecto)* | Modelo concreto del proveedor. |
| `OPENAI_API_KEY` / `GEMINI_API_KEY` / `DEEPSEEK_API_KEY` | texto | — | Solo la del proveedor en uso. |
| `TRANSCRIPTION_BACKEND` | `local` `openai_api` | `local` | Motor de transcripción. |
| `TRANSCRIPTION_MODEL` | `tiny`…`large-v3` | `small` | Tamaño del modelo Whisper local. |
| `OUTPUT_DIRECTORY` / `TEMP_DIRECTORY` / `LOGS_DIRECTORY` | ruta | `output` / `temp` / `logs` | Carpetas (relativas → bajo la raíz del proyecto). |
| `NETWORK_TIMEOUT` | entero (s) | `30` | `socket_timeout` de yt-dlp. |
| `MAX_VIDEO_MB` | entero | `200` | Límite para archivos locales. |
| `ALLOW_MOCK_FALLBACK` | bool | `false` | Si el proveedor elegido no tiene clave, usar `mock` en vez de fallar. |
| `KEEP_TEMP_ON_ERROR` | bool | `true` | Conservar `temp/job_<id>/` cuando un procesamiento falla (depuración). |

- **Validación** (`Config.validate`): proveedor, backend y modelo Whisper deben estar en sus
  listas de valores permitidos; si no, `ExtractorError` con mensaje claro.
- **`ensure_dirs()`** crea las carpetas necesarias al arrancar.
- **`masked_keys()`** enmascara las claves (`abcd...wxyz`) para el comando `--config`; nunca se
  imprime una clave completa.
- **Overrides por CLI**: `--provider`, `--ai-model`, `--model`, `--keep-temp` pisan el `.env`
  solo para esa ejecución.

---

## 7. Modelo de datos

`src/models.py` — `dataclasses` sin dependencias externas:

| Tipo | Contenido |
|---|---|
| `Segment` | `start`, `end` (segundos), `text`; `clean_text()` normaliza espacios. |
| `Transcript` | `segments[]`, `language`, `duration`, `source`; `full_text` concatena. |
| `LanguageInfo` | `code`, `name`, `is_spanish`, `method`, `secondary_code`. |
| `AnalysisReport` | Espejo del JSON de análisis (15 campos) + `parse_warning` interno; `to_dict()`. |
| `MediaSource` / `RemoteMedia` | Origen del audio y metadatos del vídeo. |
| `ProcessingResult` | Resultado del pipeline: id, rutas TXT/PDF, idioma, si hubo traducción, proveedor/modelo, `ok`, `error`, `elapsed_seconds`. |

---

## 8. Seguridad y privacidad

| Mecanismo | Implementación |
|---|---|
| **No se descarga el vídeo** | `yt-dlp` con `format="bestaudio/best"`; el audio va a `temp/job_<id>/` y se borra al terminar (`TempWorkspace.__exit__`). |
| **Solo contenido público** | `yt-dlp` sin `cookiefile` ni credenciales; los errores de contenido privado/restringido se informan sin intentar sortearlos. |
| **Redacción de secretos en logs** | `src/utils.py::SecretFilter` (un `logging.Filter`) sustituye por `[REDACTED]` los patrones de clave: `sk-…`, `AIza…`, `api_key=…`, `Bearer …`. Aplicado a los handlers de archivo y consola. |
| **Claves nunca en pantalla** | `Config.masked_keys()` en `--config` y en el menú. |
| **Anti *path traversal*** | `src/utils.py::safe_output_path` resuelve la ruta y verifica que queda dentro del directorio base; `sanitize_filename` elimina separadores, `..` y caracteres no ASCII simples. |
| **`.env` fuera del repo** | `.gitignore` excluye `.env` y `.env.*` (permitiendo `.env.example`); `*.log`, `logs/`, `output/txt/`, `output/pdf/`, `temp/`, `.venv/` también quedan fuera. |
| **Aviso legal** | El README documenta el uso responsable (contenido público, Términos de Servicio de TikTok, propiedad intelectual). |

---

## 9. Manejo de errores y resiliencia

- **`ExtractorError`** (`src/utils.py`) es la excepción de dominio: mensaje legible para el
  usuario final. `JSONParseError` y toda la jerarquía `AIProviderError` derivan de ella.
- **El pipeline nunca "explota"**: `_process()` captura `ExtractorError` (error controlado) y
  cualquier `Exception` (registrada con *traceback* como *"Error inesperado"*), y siempre
  devuelve un `ProcessingResult` con `ok=False` y `error`.
- **Degradación en cascada** para no perder trabajo ya hecho:
  1. Traducción por lote falla → segmento a segmento → texto original.
  2. Análisis IA sin JSON → reintento → informe de reserva con la respuesta en bruto.
  3. Proveedor IA caído → informe degradado; **el `.txt` ya está en disco**.
- **`KEEP_TEMP_ON_ERROR`** (por defecto `true`): ante un fallo, `temp/job_<id>/` se conserva
  para poder inspeccionar el audio y depurar; en éxito se borra siempre.
- **Modo lote** (`--urls-file`): cada URL se procesa de forma independiente; al final se
  imprime un resumen `OK/FALLO` por elemento y el código de salida refleja si todas fueron bien.
- **Códigos de salida**: `0` correcto · `1` error de configuración / entrada · `2` alguna
  unidad de trabajo falló · `130` interrupción por teclado.

---

## 10. Stack tecnológico

| Dependencia | Versión mínima | Rol en el sistema | Por qué esta y no otra |
|---|---|---|---|
| **yt-dlp** | `2024.8.6` | Obtener la pista de audio de la URL de TikTok. | Extractor mantenido activamente y resistente a cambios de las plataformas. Se usa como librería, no como binario. |
| **imageio-ffmpeg** | `0.5.1` | FFmpeg embebido como *fallback* si no hay uno del sistema. | Permite que el proyecto funcione "sin instalar nada" en Windows. |
| **openai-whisper** | `20231117` | Transcripción local (backend por defecto). Arrastra **PyTorch**, NumPy, tiktoken. | `faster-whisper` / `ctranslate2` **no tienen wheels para Python 3.13** (única versión instalada en la máquina objetivo). |
| **langdetect** | `1.0.9` | Verificación secundaria del idioma sobre el texto. | Ligera, sin dependencias pesadas; suficiente como segunda opinión. |
| **openai** | `1.40.0` | SDK de OpenAI y —vía `base_url`— de DeepSeek; también el backend de transcripción por API. | Un solo SDK cubre dos proveedores. |
| **google-genai** | `0.3.0` | SDK unificado de Google Gemini. | `google-generativeai` quedó deprecado en nov-2025. |
| **reportlab** | `4.1.0` | Generación del PDF (Platypus). | Estándar de facto en Python para PDF con control fino de maquetación y fuentes TTF. |
| **python-dotenv** | `1.0.1` | Cargar `.env`. | — |
| **pytest** | `8.0.0` | Framework de tests (solo desarrollo). | — |

- **Lenguaje**: Python 3.11+ (probado en 3.13.7 de python.org).
- **Plataforma primaria**: Windows 10/11. Funciona en Linux/macOS con ajustes menores.
- **Sistema**: sin base de datos, sin servidor, sin estado persistente más allá de los
  archivos generados y los logs.

---

## 11. Decisiones de diseño y trade-offs

| Decisión | Motivo | Coste que asumimos |
|---|---|---|
| **Nunca descargar el vídeo, solo el audio.** | Privacidad y menor huella; para el análisis solo hace falta la voz. | Si un contenido solo aporta valor visual, no se captura. |
| **`openai-whisper` en vez de `faster-whisper`.** | `faster-whisper`/`ctranslate2` no tienen wheels para Python 3.13. | ~2–2,5 GB de instalación (PyTorch) y transcripción más lenta en CPU. |
| **Leer el WAV con `wave` + NumPy y pasar el ndarray a Whisper.** | Evita que Whisper busque un `ffmpeg.exe` en el PATH (el binario de `imageio-ffmpeg` tiene otro nombre). | Un pequeño remuestreador propio como red de seguridad. |
| **Gemini como proveedor por defecto.** | Es el único con capa gratuita real. | Límites de peticiones por minuto en la capa gratuita. |
| **Traducción y análisis por prompt con reglas explícitas**, no con modelos especializados. | Un solo proveedor cubre ambas tareas; reglas anti-alucinación y de terminología ajustables. | La calidad depende del modelo elegido; hay que revisar el resultado. |
| **Autocorrección de modelo en Gemini.** | Los proveedores retiran modelos con frecuencia; evita que el proyecto "caduque". | Solo cubre el caso en que la API indica el sustituto en el error 404. |
| **`.txt` como etapa intermedia obligatoria**, antes del análisis. | Si la IA falla, el usuario conserva la transcripción. | Escritura de disco adicional siempre. |
| **`dataclasses` simples y módulos desacoplados.** | Testeabilidad y claridad. | Más *boilerplate* que un diseño con objetos ricos. |

---

## 12. Pruebas e integración continua

- **86 tests** con `pytest`, en `tests/`. Usan `MockProvider` y `monkeypatch`: **no** hacen
  descargas reales de TikTok ni llamadas reales a APIs, y **no** requieren PyTorch.

| Archivo | Cubre |
|---|---|
| `test_url_validation.py` | `validate_url` / `is_tiktok_url`: válidas, inválidas, no-TikTok, enlaces `vm./vt.`, dominios parecidos rechazados. |
| `test_utils_filenames.py` | `sanitize_filename`, `safe_output_path` (anti *path traversal*), `extract_video_id`, `format_timestamp`. |
| `test_config.py` | Parseo de `.env`, defaults, validación, creación de carpetas, enmascarado de claves, `resolved_provider()` con/sin *fallback*. |
| `test_language_detector.py` | Detección es/en, nombres de idioma, "Whisper gana" ante discrepancia. |
| `test_translator.py` | Español → no traduce; inglés → traduce conservando nº de segmentos y timestamps; términos técnicos intactos; lotes grandes. |
| `test_txt_writer.py` | Cabeceras exactas, líneas `[MM:SS]`, una o dos secciones según haya traducción. |
| `test_ai_parser.py` | `extract_json` (limpio, entre ```` ``` ````, con ruido, anidado, truncado); `_coerce_report`; `analyze_content` (JSON válido, reintento, doble fallo → reserva, error de proveedor → degradado, `AIAuthError` → propaga). |
| `test_pdf_generator.py` | Genera PDF real en carpeta temporal: empieza por `%PDF`, > 2 KB, acentos, informe vacío, tecnologías como lista de cadenas. |

- **CI**: `.github/workflows/tests.yml` — en cada `push` y `pull_request`, sobre
  `ubuntu-latest` con Python 3.13, instala `requirements.txt` (con caché de pip) y ejecuta
  `pytest -q`.

---

## 13. Rendimiento

- **Transcripción** es la etapa dominante. En CPU, el modelo `small` ofrece el mejor
  compromiso; `medium`/`large` son notablemente más lentos y piden más RAM
  (~2 GB `small`, ~5 GB `medium`, ~10 GB `large`).
- La **primera ejecución** descarga el modelo Whisper (`small` ≈ 460–490 MB) una sola vez.
- El **modelo se cachea en memoria** durante un lote: procesar N URLs no recarga N veces.
- **Traducción/análisis**: latencia de red + límites de la capa gratuita de Gemini. La
  traducción va por lotes de 40 segmentos con reintentos y *backoff*.
- El backend `openai_api` de transcripción no descarga nada pero es de pago y limita a 25 MB.

---

## 14. Limitaciones conocidas

- **Dependencia de `yt-dlp`**: si TikTok cambia sus mecanismos, la obtención de audio puede
  fallar temporalmente. El modo `--file` es el plan B y ejercita todo el pipeline.
- **TikTok puede bloquear la IP** (rate-limit / captcha / 403); es el comportamiento esperado
  en entornos de prueba y la razón de ser de `--file`.
- **Transcripción local en CPU**: lenta frente a GPU.
- **Capa gratuita de Gemini**: límites por minuto; en transcripciones largas se puede alcanzar
  el límite (el `.txt` se genera igual y el `.pdf` sale degradado).
- **Calidad de traducción/análisis**: depende del proveedor y modelo; conviene revisar.
- **Nombres de modelo de IA cambian**: se resuelven con `AI_MODEL` / `--ai-model` (y
  autocorrección en Gemini).
- Whisper `small` puede transcribir mal términos técnicos poco frecuentes con audio de baja
  calidad; subir a `medium` mejora.

---

## 15. Estructura del repositorio

```
Extractor_texto_tiktok/
├── main.py                    # CLI (argparse) + menú interactivo + modo lote
├── config.py                  # dataclass Config: carga y validación de .env
├── requirements.txt
├── .env.example               # plantilla de configuración (sin claves)
├── run.bat                    # lanzador Windows: crea .venv e instala en el primer uso
├── src/
│   ├── models.py              # dataclasses compartidas
│   ├── pipeline.py            # orquestador de las 6 etapas
│   ├── tiktok_downloader.py   # yt-dlp: SOLO audio; validación de URL; errores amigables
│   ├── local_video.py         # validación de archivos locales (--file)
│   ├── audio_extractor.py     # FFmpeg → WAV 16 kHz mono; probe_duration
│   ├── transcriber.py         # openai-whisper local / API OpenAI; caché de modelo
│   ├── language_detector.py   # Whisper + verificación langdetect
│   ├── translator.py          # traducción al español por lotes vía proveedor IA
│   ├── ai_analyzer.py         # análisis técnico → JSON → AnalysisReport
│   ├── txt_writer.py          # generación del .txt
│   ├── pdf_generator.py       # generación del .pdf (ReportLab / Platypus)
│   ├── utils.py               # logging seguro, rutas seguras, FFmpeg, JSON, temp
│   └── ai_providers/          # base (ABC) + gemini / openai / deepseek / mock + fábrica
├── input/urls.txt             # una URL por línea (modo lote)
├── output/{txt,pdf}/          # artefactos generados (ignorados por Git)
├── temp/  ·  logs/            # temporales y registros (ignorados por Git)
├── tests/                     # 86 tests (pytest, con mocks)
└── .github/workflows/tests.yml
```
