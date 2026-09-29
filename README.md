# Extractor_texto_tiktok

<p align="center">
  <img alt="Python" src="https://img.shields.io/badge/Python-3.11%2B-3776AB?logo=python&logoColor=white">
  <img alt="Licencia MIT" src="https://img.shields.io/badge/Licencia-MIT-green">
  <img alt="Tests" src="https://github.com/Javier3921/Extractor_texto_tiktok/actions/workflows/tests.yml/badge.svg">
  <img alt="Whisper" src="https://img.shields.io/badge/Transcripci%C3%B3n-Whisper-8A2BE2">
  <img alt="Gemini" src="https://img.shields.io/badge/IA-Google%20Gemini-4285F4?logo=googlegemini&logoColor=white">
  <img alt="Claude" src="https://img.shields.io/badge/IA-Claude%20Code-D97757?logo=claude&logoColor=white">
  <img alt="Markdown" src="https://img.shields.io/badge/Informe-HTML%20%7C%20Markdown-000000?logo=markdown&logoColor=white">
  <img alt="Plataforma" src="https://img.shields.io/badge/Plataforma-Windows%20%7C%20Linux%20%7C%20macOS-lightgrey">
</p>

Convierte un vídeo de **TikTok** (o un archivo de vídeo local) en un **informe
técnico profesional redactado íntegramente en español**, en el formato que
prefieras:

- **HTML** — página autónoma con gráficos y una insignia de dificultad, para leerla tú.
- **Markdown** — texto estructurado con metadatos YAML, ideal para pasárselo a
  otra IA, guardarlo en tus notas o versionarlo en un repositorio.
- **Ambos** a la vez.

La traducción y el análisis los hace la IA que elijas: **Google Gemini** (capa
gratuita con clave de API) o **Claude** a través del CLI de Claude Code (usa
tu suscripción de Claude, sin clave de API), entre otras. Úsalo desde la línea
de comandos o desde una pequeña **interfaz gráfica** — solo pega el enlace y,
si quieres, dile a la IA qué priorizar en el informe.

> **Privacidad por diseño:** nunca se descarga ni se guarda el vídeo. Solo
> se obtiene el **audio**, en un archivo temporal que se borra al terminar.

```mermaid
flowchart TD
    A(["URL de TikTok<br/>o archivo local"]) --> B["Obtener audio<br/><sub>yt-dlp · SOLO audio, nunca vídeo</sub>"]
    B --> C["Normalizar audio<br/><sub>FFmpeg → WAV 16 kHz mono</sub>"]
    C --> D["Transcribir<br/><sub>Whisper (local u API)</sub>"]
    D --> E{"¿Idioma<br/>original?"}
    E -- Español --> G["Generar .txt"]
    E -- "Inglés / otro" --> F["Traducir al español<br/><sub>IA · conserva el original</sub>"]
    F --> G
    G --> H["Analizar contenido<br/><sub>IA · anti-alucinación</sub>"]
    H --> I(["Informe .html<br/><sub>autónomo, con gráficos</sub>"])
    H --> J(["Informe .md<br/><sub>legible por otra IA</sub>"])

    classDef entrada fill:#4285F4,stroke:#1a56c4,color:#fff
    classDef proceso fill:#f4f6fb,stroke:#4285F4,color:#1a1a1a
    classDef ia fill:#8A2BE2,stroke:#5b1a99,color:#fff
    classDef salida fill:#34A853,stroke:#1e7a34,color:#fff
    class A entrada
    class B,C,D,G proceso
    class F,H ia
    class I,J salida
```

---

## Índice

1. [Requisitos](#requisitos)
2. [Instalación](#instalación)
3. [Configuración (`.env`)](#configuración-env)
4. [Uso](#uso)
5. [Detección de idioma y traducción](#detección-de-idioma-y-traducción)
6. [Proveedores de IA](#proveedores-de-ia)
7. [Arquitectura del sistema](#arquitectura-del-sistema)
8. [Seguridad](#seguridad)
9. [Archivos generados](#archivos-generados)
10. [Estructura del proyecto](#estructura-del-proyecto)
11. [Modelos de Whisper](#modelos-de-whisper)
12. [Problemas comunes](#problemas-comunes)
13. [Limitaciones](#limitaciones)
14. [Consideraciones legales y de uso](#consideraciones-legales-y-de-uso)

---

## Requisitos

| Componente | Detalle |
|---|---|
| **Sistema** | Windows 10/11 (también funciona en Linux/macOS con ajustes menores). |
| **Python** | 3.11 o superior. Probado en 3.13. |
| **FFmpeg** | Necesario para extraer el audio. Si no hay uno en el sistema, se usa automáticamente el que incluye el paquete `imageio-ffmpeg` (se instala con las dependencias). |
| **IA** | Para traducción y análisis, una de estas dos opciones: una clave de **Gemini** (capa gratuita: https://aistudio.google.com/apikey) **o** el [CLI de Claude Code](https://docs.claude.com/en/docs/claude-code) instalado y con sesión iniciada (sin clave de API; ver [Proveedores de IA](#proveedores-de-ia)). |
| **Espacio en disco** | ~2–2,5 GB para PyTorch + Whisper (backend de transcripción local por defecto). El modelo `small` añade ~490 MB la primera vez. |

---

## Instalación

### 1. Instalar Python

Descarga Python 3.11+ desde <https://www.python.org/downloads/windows/> y marca
**"Add python.exe to PATH"** durante la instalación.

Comprueba: `py -3 --version`

### 2. Crear el entorno virtual e instalar dependencias

**Opción rápida (Windows):** ejecuta `run.bat`. La primera vez crea `.venv` e
instala todo automáticamente.

**Opción manual:**

```bat
cd Extractor_texto_tiktok
py -3 -m venv .venv
.venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
```

La instalación descarga PyTorch (varios minutos la primera vez).

### 3. FFmpeg (opcional pero recomendado)

El proyecto funciona sin hacer nada gracias a `imageio-ffmpeg`. Si quieres un
FFmpeg del sistema (más rápido y completo):

```bat
winget install --id Gyan.FFmpeg -e
```

o descarga manual desde <https://www.gyan.dev/ffmpeg/builds/> y añade la carpeta
`bin` al `PATH`.

### 4. Configurar credenciales

```bat
copy .env.example .env
```

Edita `.env`: elige el proveedor (`AI_PROVIDER`) y el formato del informe
(`REPORT_FORMAT`), y rellena la clave del proveedor si la necesita (ver abajo).

---

## Configuración (`.env`)

| Variable | Valores | Por defecto | Descripción |
|---|---|---|---|
| `AI_PROVIDER` | `openai` `gemini` `deepseek` `claude_cli` `mock` | `gemini` | Proveedor para traducción y análisis. |
| `AI_MODEL` | texto | *(vacío)* | Modelo concreto. Vacío = modelo por defecto del proveedor. |
| `GEMINI_FALLBACK_MODEL` | texto | `gemini-flash-lite-latest` | Solo Gemini: si el modelo principal se sobrecarga (503) y se agotan los reintentos, se prueba una vez con este antes de degradar el informe. Vacío = desactivado. |
| `CLAUDE_CLI_CMD` | comando o ruta | `claude` | Solo `claude_cli`: ejecutable del CLI de Claude Code. |
| `CLAUDE_CLI_TIMEOUT` | entero (s) | `600` | Solo `claude_cli`: tiempo máximo por llamada al CLI. |
| `REPORT_FORMAT` | `html` `markdown` `both` | `html` | Formato del informe técnico. |
| `OPENAI_API_KEY` | texto | — | Clave de OpenAI. |
| `GEMINI_API_KEY` | texto | — | Clave de Google AI Studio (gratuita). |
| `DEEPSEEK_API_KEY` | texto | — | Clave de DeepSeek. |
| `TRANSCRIPTION_BACKEND` | `local` `openai_api` | `local` | `local` = Whisper en tu PC; `openai_api` = API de OpenAI. |
| `TRANSCRIPTION_MODEL` | `tiny`…`large-v3` | `small` | Tamaño del modelo Whisper (backend local). |
| `OUTPUT_DIRECTORY` | ruta | `output` | Carpeta de resultados. |
| `TEMP_DIRECTORY` | ruta | `temp` | Carpeta temporal. |
| `LOGS_DIRECTORY` | ruta | `logs` | Carpeta de logs. |
| `NETWORK_TIMEOUT` | entero (s) | `30` | Timeout de red para `yt-dlp` **y** para las llamadas HTTP al proveedor de IA (`claude_cli` usa `CLAUDE_CLI_TIMEOUT`). |
| `MAX_VIDEO_MB` | entero | `200` | Límite de tamaño para archivos locales **y** para el audio descargado de TikTok. |
| `ALLOW_MOCK_FALLBACK` | `true`/`false` | `false` | Si el proveedor elegido no tiene clave, usar `mock` en vez de fallar. |
| `KEEP_TEMP_ON_ERROR` | `true`/`false` | `true` | Conservar la carpeta temporal cuando un procesamiento falla (debug). |

Las claves **nunca** se escriben en logs ni se muestran por pantalla (se
enmascaran como `AIza…3456`).

---

## Uso

### Menú interactivo

```bat
python main.py
```

```
==============================================
        EXTRACTOR DE TEXTO DE TIKTOK
==============================================
  1. Procesar un TikTok
  2. Procesar múltiples TikToks (input/urls.txt)
  3. Procesar archivo de video local
  4. Cambiar proveedor de IA
  5. Cambiar formato del informe
  6. Ver configuración
  7. Salir
```

### Una URL

```bat
python main.py --url "https://www.tiktok.com/@usuario/video/1234567890123456789"
```

### Varias URLs

Edita `input/urls.txt` (una URL por línea; las líneas vacías y las que empiezan
por `#` se ignoran) y ejecuta:

```bat
python main.py --urls-file
```

### Archivo de vídeo local (fallback si TikTok bloquea la descarga)

```bat
python main.py --file "C:\Videos\clip.mp4"
```

Formatos aceptados: `mp4, mov, mkv, webm, avi, m4v, flv` (y audio suelto:
`mp3, wav, m4a, aac, ogg, flac`).

### Opciones útiles

| Opción | Efecto |
|---|---|
| `--provider gemini\|claude_cli\|openai\|deepseek\|mock` | Fuerza el proveedor de IA (ignora `.env`). |
| `--ai-model NOMBRE` | Fuerza el modelo del proveedor de IA (ignora `AI_MODEL`). |
| `--model small\|medium\|…` | Fuerza el modelo de Whisper. |
| `--format html\|markdown\|both` | Formato del informe (ignora `REPORT_FORMAT`). |
| `--no-report` | Genera solo el `.txt` (alias antiguo: `--no-html`). |
| `--keep-temp` | Conserva la carpeta temporal aunque el procesamiento termine bien (por defecto se borra en éxito). |
| `--instructions "TEXTO"` | Indicaciones para la IA sobre qué priorizar o incluir en el informe (ver [más abajo](#instrucciones-personalizadas-para-la-ia)). |
| `--config` | Muestra la configuración y sale. |
| `--gui` | Abre la interfaz gráfica (Tkinter) en vez de la CLI. |

Progreso mostrado:

```
[1/6] Obteniendo audio del TikTok (no se descarga el video)...
[2/6] Extrayendo audio (WAV 16 kHz mono)...
[3/6] Transcribiendo con Whisper (local:small)...
[4/6] Detectando idioma...
[INFO] Idioma detectado: English
[5/6] Traduciendo/analizando con IA...
[INFO] Traduciendo contenido al español...
[OK] Traducción completada.
[6/6] Generando informe (MARKDOWN)...
```

Ejemplo con Claude y ambos formatos:

```bat
python main.py --url "https://www.tiktok.com/@u/video/123" --provider claude_cli --format both
```

### Interfaz gráfica

```bat
python main.py --gui
```

Abre una ventana (Tkinter, sin dependencias adicionales) con un campo para la
**URL de TikTok**, un cuadro de texto para **indicaciones a la IA** sobre qué
priorizar en el informe y dos desplegables para elegir **proveedor de IA** y
**formato del informe** (parten de los valores del `.env`). El procesamiento
corre en segundo plano (no se congela la ventana) y, al terminar, muestra un
mensaje con **dónde quedaron guardados el `.txt` y el informe (`.html`/`.md`),
y con qué nombres**.

### Instrucciones personalizadas para la IA

Tanto en la CLI (`--instructions "TEXTO"`), el menú interactivo como la GUI
puedes indicarle al análisis técnico qué enfatizar, por ejemplo:

```bat
python main.py --url "https://www.tiktok.com/@u/video/123" ^
  --instructions "Enfocate en los riesgos de seguridad y compara con buenas practicas de OWASP"
```

Estas indicaciones **guían el énfasis** del informe (qué ampliar, resumir o
destacar dentro de las mismas 12 secciones), pero no le dan permiso a la IA
para inventar información que no esté en la transcripción ni para cambiar el
formato de salida.

---

## Detección de idioma y traducción

1. **Transcripción** con Whisper (detecta el idioma a partir del audio).
2. **Verificación** con `langdetect` sobre el texto. Si discrepan, se registra
   el aviso pero se confía en Whisper.
3. **Si el idioma es español** → se usa la transcripción tal cual. No se traduce.
4. **Si es inglés u otro idioma** → la IA traduce **toda** la transcripción al
   español y **se conserva la versión original** en el `.txt`.

La traducción respeta la terminología técnica: **no** traduce nombres de
tecnologías, lenguajes, frameworks, librerías, APIs, productos ni herramientas
(`React`, `Node.js`, `REST API`, `OAuth 2.0`, `Docker`, `Kubernetes`,
`PostgreSQL`, …).

---

## Proveedores de IA

| Proveedor | SDK | Coste | Notas |
|---|---|---|---|
| **Gemini** | `google-genai` | **Capa gratuita** | Recomendado para empezar. Clave: <https://aistudio.google.com/apikey> |
| **Claude** (`claude_cli`) | CLI de Claude Code | Incluido en tu suscripción de Claude | Sin clave de API: usa la sesión del CLI ya iniciada en el equipo. Ver abajo. |
| **OpenAI** | `openai` | De pago | Requiere facturación activa. |
| **DeepSeek** | `openai` (con `base_url`) | De pago (bajo coste) | API compatible con OpenAI. |
| **mock** | — | Gratis | Proveedor simulado: **no hace análisis real**. Para probar el pipeline sin claves. |

Cambiar de proveedor: edita `AI_PROVIDER` en `.env`, usa `--provider`, o la
opción 4 del menú. La arquitectura (`src/ai_providers/`) está desacoplada:
todos implementan la misma interfaz `AIProvider`.

Modelos por defecto (si `AI_MODEL` está vacío): `gpt-4o-mini` (OpenAI),
`gemini-3.6-flash` (Gemini), `sonnet` (Claude), `deepseek-chat` (DeepSeek). Los proveedores retiran
modelos con el tiempo; si uno deja de funcionar, pon el nombre nuevo en
`AI_MODEL` (o usa `--ai-model NOMBRE`). El proveedor Gemini además intenta
**autocorregir** el modelo si la API indica el sustituto en el error.

Si el análisis con IA falla (límite de cuota, modelo caído, red), el `.txt` con
la transcripción se genera igualmente y el informe sale en modo degradado dejando
constancia del motivo, en vez de abortar todo el procesamiento.

### Claude vía Claude Code (`claude_cli`)

En lugar de una API de pago por token, este proveedor invoca el CLI de
[Claude Code](https://docs.claude.com/en/docs/claude-code) en modo no
interactivo (`claude -p`), aprovechando la sesión que ya tengas iniciada con
tu cuenta de Claude.

1. Instala el CLI (requiere Node.js): `npm install -g @anthropic-ai/claude-code`
2. Ejecuta `claude` una vez en una terminal e inicia sesión.
3. En `.env`: `AI_PROVIDER=claude_cli` (opcional: `AI_MODEL=opus`, `haiku`…).

Cada llamada se lanza **sin herramientas** (`--tools ""`), con un *system
prompt* propio (`--system-prompt`) y con la forma de la respuesta forzada por
un esquema JSON (`--json-schema`); la transcripción se entrega por la entrada
estándar. Es más lento que una llamada HTTP (unos segundos por petición) y
consume de los límites de uso de tu plan.

---

## Arquitectura del sistema

El proyecto es un **pipeline lineal desacoplado**: cada etapa es un módulo
independiente que recibe y devuelve `dataclasses` simples, sin estado global.
Cambiar de proveedor de IA no requiere tocar el resto del programa (patrón
*Strategy* en `src/ai_providers/`).

```mermaid
flowchart LR
    subgraph CLI["Entrada"]
        M["main.py<br/><sub>argparse + menú</sub>"]
        CFG["config.py<br/><sub>.env → Config</sub>"]
    end

    subgraph PIPE["src/pipeline.py — orquestador"]
        direction TB
        S1["tiktok_downloader /<br/>local_video"]
        S2["audio_extractor<br/><sub>FFmpeg</sub>"]
        S3["transcriber<br/><sub>Whisper</sub>"]
        S4["language_detector"]
        S5["translator"]
        S6["ai_analyzer"]
        S7["txt_writer /<br/>html_generator /<br/>markdown_generator"]
        S1 --> S2 --> S3 --> S4 --> S5 --> S6 --> S7
    end

    subgraph AI["src/ai_providers/ (Strategy)"]
        BASE["base.py<br/><sub>AIProvider (ABC)<br/>reintentos + backoff</sub>"]
        GEM["gemini_provider.py<br/><sub>en uso — capa gratuita</sub>"]
        CLA["claude_cli_provider.py<br/><sub>Claude Code CLI</sub>"]
        OAI["openai_provider.py"]
        DS["deepseek_provider.py"]
        MOCK["mock_provider.py<br/><sub>offline, para tests</sub>"]
        BASE -.-> GEM
        BASE -.-> CLA
        BASE -.-> OAI
        BASE -.-> DS
        BASE -.-> MOCK
    end

    UTILS["utils.py<br/><sub>logging seguro · rutas seguras<br/>temp workspace · JSON tolerante</sub>"]

    M --> CFG --> PIPE
    S5 -.usa.-> AI
    S6 -.usa.-> AI
    PIPE -.-> UTILS

    classDef entrada fill:#f4f6fb,stroke:#4285F4,color:#1a1a1a
    classDef ia fill:#8A2BE2,stroke:#5b1a99,color:#fff
    classDef activo fill:#34A853,stroke:#1e7a34,color:#fff
    classDef util fill:#fff3cd,stroke:#b38600,color:#1a1a1a
    class M,CFG entrada
    class BASE,OAI,DS,MOCK ia
    class GEM,CLA activo
    class UTILS util
```

| Capa | Módulos | Responsabilidad |
|---|---|---|
| **Entrada** | `main.py`, `config.py` | CLI, menú interactivo, carga/validación de `.env`. |
| **Orquestador** | `src/pipeline.py` | Encadena las 6 etapas y decide si continuar en modo degradado ante un fallo de IA. |
| **Proveedores de IA** | `src/ai_providers/` | Interfaz común `AIProvider`; cada proveedor solo implementa `_complete_raw()`. Reintentos/backoff centralizados en la clase base. |
| **Transversal** | `src/utils.py` | Logging con redacción de secretos, rutas seguras (anti *path traversal*), carpeta temporal, parseo de JSON tolerante. |

---

## Seguridad

El proyecto procesa contenido de terceros desconocidos (vídeos públicos) y
usa una API de IA externa, así que se tomaron medidas concretas en ambos
frentes:

| Medida | Dónde | Por qué |
|---|---|---|
| **Redacción de secretos en logs** | `utils.py::SecretFilter` | Las claves (`sk-…`, `AIza…`, `Bearer …`) se sustituyen por `[REDACTED]` en consola y archivo de log; `--config` solo muestra la clave enmascarada (`AIza…3456`). |
| **Anti *path traversal*** | `utils.py::safe_output_path` | Los nombres de archivo derivados de datos externos (título del vídeo, id) nunca pueden escribir fuera de `output/`. |
| **Solo contenido público** | `tiktok_downloader.py` | `yt-dlp` se usa sin cookies ni credenciales; nunca se intenta sortear un vídeo privado o con captcha. |
| **Límite de tamaño de descarga** | `tiktok_downloader.py` / `local_video.py` | `MAX_VIDEO_MB` limita tanto los archivos locales como el audio descargado de TikTok (`max_filesize` de yt-dlp), evitando descargas desproporcionadas. |
| **Timeout en las llamadas a la IA** | `ai_providers/gemini_provider.py`, `ai_providers/claude_cli_provider.py` | Las llamadas a Gemini usan `NETWORK_TIMEOUT` y las del CLI de Claude `CLAUDE_CLI_TIMEOUT` (`.env`); sin esto, una llamada colgada bloquearía el pipeline indefinidamente. |
| **Guardas contra inyección de instrucciones** | `translator.py`, `ai_analyzer.py` | La transcripción es contenido de un tercero no confiable. Los *system prompts* indican explícitamente al modelo que ese texto es **dato a procesar, nunca una instrucción**, aunque contenga frases como "ignora tus reglas". |
| **Claude sin herramientas** | `ai_providers/claude_cli_provider.py` | El CLI de Claude Code se invoca con `--tools ""` y fuera de la carpeta del proyecto: aunque una transcripción intentara dar órdenes, el modelo no tiene forma de ejecutar comandos ni leer archivos. |
| **Markdown sin estructura inyectable** | `markdown_generator.py` | Los metadatos van como cadenas JSON en el bloque YAML y el texto se neutraliza (encabezados, separadores, `<`, `\|` en tablas) para que el contenido de un tercero no pueda falsear la estructura del documento. |
| **Sin persistencia del vídeo** | `tiktok_downloader.py`, `TempWorkspace` | Solo se guarda el audio, en una carpeta temporal por trabajo que se borra al terminar con éxito. |
| **`.env` fuera del repositorio** | `.gitignore` | Las claves de API, `logs/`, `temp/` y `output/` nunca se suben a Git. |

---

## Archivos generados

```
output/
├── txt/
│   └── tiktok_<id>.txt           (o  local_<nombre>_<fecha>.txt)
├── html/                          (REPORT_FORMAT=html o both)
│   └── reporte_tiktok_<id>.html  (o  reporte_local_<nombre>_<fecha>.html)
└── markdown/                      (REPORT_FORMAT=markdown o both)
    └── reporte_tiktok_<id>.md    (o  reporte_local_<nombre>_<fecha>.md)
```

### `.txt`

```
==================================================
INFORMACION DEL VIDEO
=====================
URL:                     ...
FECHA DE PROCESAMIENTO:  ...
IDIOMA ORIGINAL:         English (en)
IDIOMA DEL REPORTE:      Espanol
TRADUCCION REALIZADA:    Si
DURACION:                00:42
ID DEL VIDEO:            123456789

==================================================
TRANSCRIPCION ORIGINAL
======================
[00:00] Today we're going to build a REST API...

==================================================
TRANSCRIPCION EN ESPANOL
========================
[00:00] Hoy vamos a construir una REST API...
```

(Si el vídeo ya está en español, solo aparece la sección **TRANSCRIPCION EN
ESPANOL** con el texto original.)

### `.html`

Un único archivo **autónomo** (CSS y SVG inline, sin JavaScript, sin
peticiones externas — se abre con doble clic en cualquier navegador, incluso
sin internet) con 12 secciones: **A** Resumen ejecutivo · **B** Explicación
detallada · **C** Tecnologías (tabla + **gráfico de barras** por categoría) ·
**D** Conceptos técnicos · **E** Arquitectura · **F** Análisis de código ·
**G** Buenas prácticas · **H** Riesgos · **I** Recomendaciones · **J** Nivel
de dificultad (insignia con color) · **K** Aplicaciones · **L** Conclusión.

Pesa una fracción de lo que pesaba el PDF anterior (unos ~8 KB para un
informe típico, frente a ~100 KB) y admite imprimirse o "Guardar como PDF"
desde el navegador si aún necesitas un archivo PDF puntual (incluye estilos
de impresión).

### `.md`

Las mismas 12 secciones (`## A. Resumen ejecutivo` … `## L. Conclusión`), sin
estilos ni gráficos, precedidas de un bloque de metadatos YAML que otra IA o un
script pueden leer directamente:

```markdown
---
tipo: informe_tecnico_video
titulo: "Construcción de una REST API con Python, FastAPI y Docker"
origen: "https://www.tiktok.com/@u/video/123"
idioma_original: "English"
traducido_al_espanol: true
duracion: "00:42"
proveedor_ia: "claude_cli"
modelo_ia: "sonnet"
dificultad: "Básico"
---

# Construcción de una REST API con Python, FastAPI y Docker

## A. Resumen ejecutivo
...
```

El análisis distingue explícitamente **información explícita**,
**inferencia técnica** y **recomendación**, y evita inventar tecnologías,
arquitecturas o código que no estén en el contenido.

---

## Estructura del proyecto

```
Extractor_texto_tiktok/
├── main.py                 # CLI + menú interactivo
├── gui.py                  # interfaz gráfica (Tkinter), --gui
├── config.py               # carga y validación de .env
├── requirements.txt
├── .env.example
├── run.bat
├── src/
│   ├── models.py           # dataclasses compartidas
│   ├── pipeline.py         # orquestador de las 6 etapas
│   ├── tiktok_downloader.py# yt-dlp: SOLO audio, nunca vídeo
│   ├── local_video.py      # validación de archivos locales
│   ├── audio_extractor.py  # FFmpeg -> WAV 16 kHz mono
│   ├── transcriber.py      # Whisper local / API de OpenAI
│   ├── language_detector.py# idioma (Whisper + langdetect)
│   ├── translator.py       # traducción al español vía IA
│   ├── ai_analyzer.py      # análisis técnico -> JSON -> AnalysisReport
│   ├── txt_writer.py       # generación del .txt
│   ├── html_generator.py   # generación del .html (autónomo, sin dependencias)
│   ├── markdown_generator.py # generación del .md (metadatos YAML + secciones)
│   ├── utils.py            # logging seguro, rutas, JSON, FFmpeg, temp
│   └── ai_providers/       # Gemini / Claude (CLI) / OpenAI / DeepSeek / mock
├── input/urls.txt
├── output/{txt,html,markdown}/
├── temp/  · logs/
└── tests/
```

### Tests

```bat
.venv\Scripts\activate
pytest -q
```

Los tests usan mocks: **no** hacen descargas reales de TikTok ni llamadas reales
a APIs (ni al CLI de Claude), y no necesitan PyTorch. Incluyen la
clasificación de errores y el autocambio de modelo del proveedor Gemini, y la
invocación y clasificación de errores del proveedor `claude_cli`.

---

## Modelos de Whisper

| Modelo | RAM aprox. | Velocidad (CPU) | Precisión |
|---|---|---|---|
| `tiny` | ~1 GB | Muy rápida | Baja |
| `base` | ~1 GB | Rápida | Media-baja |
| `small` | ~2 GB | Media | **Buena (recomendado)** |
| `medium` | ~5 GB | Lenta | Alta |
| `large` / `large-v3` | ~10 GB | Muy lenta | Máxima |

Sin GPU, `medium` y `large` pueden tardar mucho. Empieza con `small`.

El backend `openai_api` (`TRANSCRIPTION_BACKEND=openai_api`) no descarga nada
pero es de pago y limita a 25 MB por archivo de audio.

---

## Problemas comunes

| Síntoma | Solución |
|---|---|
| `FFmpeg no esta disponible` | Instala `imageio-ffmpeg` (`pip install -r requirements.txt`) o FFmpeg del sistema (`winget install Gyan.FFmpeg`). |
| `TikTok ha bloqueado o limitado la peticion` | Actualiza yt-dlp (`pip install -U yt-dlp`), espera un rato, o usa `--file` con el vídeo descargado a mano. |
| `Unexpected response from webpage request` (con el aviso `attempting impersonation, but no impersonate target is available`) | Falta `curl_cffi`, necesario para que yt-dlp imite el TLS de un navegador (TikTok bloquea peticiones sin esto). Instálalo con `pip install -U curl_cffi` (ya está en `requirements.txt`). |
| `El video es privado, restringido…` | El contenido no es público. La aplicación no accede a contenido no público. |
| Descarga enorme al instalar | Es PyTorch (backend Whisper local). Alternativa: `TRANSCRIPTION_BACKEND=openai_api`. |
| `faster-whisper` no instala | No se usa: no tiene soporte para Python 3.13. Este proyecto usa `openai-whisper`. |
| `Falta la clave de API para gemini` | Rellena `GEMINI_API_KEY` en `.env` o usa `--provider mock`. |
| Informe degradado con `error 503 UNAVAILABLE` / `high demand` | La capa gratuita de Gemini está saturada por demanda alta (temporal, no es un problema de configuración). El sistema ya reintenta con espera creciente y, si el modelo principal sigue sobrecargado, cae automáticamente a `GEMINI_FALLBACK_MODEL` (por defecto `gemini-flash-lite-latest`, con más margen libre). Si aun así falla, espera unos minutos y reprocesa el mismo video (el `.txt` no se pierde). |
| `No se encontro el CLI de Claude Code` | Instala el CLI (`npm install -g @anthropic-ai/claude-code`) o pon su ruta completa en `CLAUDE_CLI_CMD`. |
| `el CLI de Claude Code no tiene una sesion valida` | Ejecuta `claude` en una terminal e inicia sesión con tu cuenta. |
| Informe degradado con `limite de uso de Claude alcanzado` | Se agotó el cupo de tu plan de Claude por ahora. Espera a que se renueve o usa otro proveedor (`--provider gemini`); el `.txt` no se pierde. |
| La 1.ª transcripción tarda | Descarga el modelo Whisper (`small` ≈ 490 MB). Solo la primera vez. |

Los logs detallados están en `logs/run_AAAAMMDD.log`.

---

## Limitaciones

- **Dependencia de TikTok:** la obtención de audio usa `yt-dlp`; si TikTok cambia
  sus mecanismos, puede dejar de funcionar temporalmente. El modo `--file` es el
  plan B y ejercita todo el pipeline.
- **Transcripción local en CPU:** más lenta que con GPU. El modelo `small` es el
  compromiso recomendado.
- **Capa gratuita de Gemini:** tiene límites de peticiones. Para transcripciones
  largas, la traducción se hace por lotes y con reintentos, pero puedes toparte
  con el límite.
- **Claude vía CLI (`claude_cli`):** cada llamada lanza un proceso del CLI
  (unos 5–10 s) y consume de los límites de uso de tu plan de Claude; si se
  agotan, el `.txt` se genera igual y el informe sale en modo degradado.
- **Calidad de la traducción/análisis:** depende del proveedor y modelo elegidos.
- El backend `openai_api` de transcripción no admite audios de más de 25 MB.

---

## Consideraciones legales y de uso

- Usa esta herramienta **solo con contenido público** y para el que tengas
  derecho de acceso. No accede a cuentas privadas ni elude autenticación,
  captchas o controles de acceso.
- Respeta los **Términos de Servicio de TikTok** y la legislación de propiedad
  intelectual aplicable en tu país. La responsabilidad del uso es de quien
  ejecuta la herramienta.
- El audio descargado es **temporal** y se elimina tras el procesamiento. No se
  almacena el vídeo.
- Las transcripciones y análisis generados por IA pueden contener errores;
  revísalos antes de darles un uso relevante.

---

## Licencia

Este proyecto se distribuye bajo la licencia **MIT**. Consulta el archivo
[LICENSE](LICENSE).
