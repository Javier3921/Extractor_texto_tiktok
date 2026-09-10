@echo off
REM ======================================================================
REM  Extractor_texto_tiktok - lanzador para Windows
REM  Crea el entorno virtual la primera vez y ejecuta la aplicacion.
REM  Uso:
REM     run.bat                         -> menu interactivo
REM     run.bat --url "URL_TIKTOK"      -> procesar un TikTok
REM     run.bat --file "C:\v\video.mp4" -> procesar un video local
REM ======================================================================
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [SETUP] Creando entorno virtual .venv ...
    where py >nul 2>nul
    if %ERRORLEVEL%==0 (
        py -3 -m venv .venv
    ) else (
        python -m venv .venv
    )
    if not exist ".venv\Scripts\python.exe" (
        echo [ERROR] No se pudo crear el entorno virtual. Instala Python 3.11+ desde python.org
        exit /b 1
    )
    echo [SETUP] Instalando dependencias (puede tardar varios minutos la primera vez)...
    ".venv\Scripts\python.exe" -m pip install --upgrade pip
    ".venv\Scripts\python.exe" -m pip install -r requirements.txt
)

".venv\Scripts\python.exe" main.py %*
endlocal
