@echo off
rem === Start-DraveMind.bat - zelf-installerende launcher voor DraveAI ===
rem Eerste keer: zet de omgeving op (zichtbare voortgang). Daarna: meteen en
rem zonder console starten. De beeld-AI (torch) installeert de app zelf op
rem aanvraag in deze omgeving (Beeld -> Beeld-AI installeren).
setlocal
cd /d "%~dp0"

rem --- Python kiezen (voorkeur 3.10/3.11: nodig voor torch 2.1.2 / beeld) ---
set PY=
if exist "D:\Python310\python.exe" set "PY=D:\Python310\python.exe"
if not defined PY (
  for %%V in (3.10 3.11 3.12 3.13) do (
    if not defined PY ( py -%%V -c "import sys" >nul 2>&1 && set "PY=py -%%V" )
  )
)
if not defined PY ( py -3 -c "import sys" >nul 2>&1 && set "PY=py -3" )
if not defined PY ( python -c "import sys" >nul 2>&1 && set "PY=python" )
if not defined PY (
  echo ============================================================
  echo   DraveAI heeft eenmalig Python nodig ^(gratis, van python.org^).
  echo   Dit installeren we NIET zelf - jij beslist.
  echo ============================================================
  echo Tip: zet bij de installatie een vinkje bij "Add Python to PATH",
  echo kies bij voorkeur versie 3.10 of 3.11, en start dit bestand daarna opnieuw.
  echo.
  set /p OPENPY="Wil je de download-pagina van Python nu openen? (J/N): "
  if /i "%OPENPY%"=="J" start "" https://www.python.org/downloads/release/python-3119/
  exit /b 1
)

if not exist ".venv" (
  echo ============================================================
  echo   DraveAI - eenmalige installatie ^(dit kan een paar minuten duren^)
  echo ============================================================
  %PY% -m venv .venv
  call ".venv\Scripts\activate.bat"
  python -m pip install --upgrade pip
  rem llama-cpp als kant-en-klare AVX2-wheel (cpu/standaard crasht op sommige CPU's)
  python -m pip install --prefer-binary --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/avx2 llama-cpp-python
  if errorlevel 1 python -m pip install --prefer-binary --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/basic llama-cpp-python
  python -m pip install --prefer-binary -r requirements.txt
  echo.
  echo Klaar met installeren! DraveAI start nu.
) else (
  call ".venv\Scripts\activate.bat"
)

rem starten zonder console (de app heeft een eigen splashscherm)
start "" ".venv\Scripts\pythonw.exe" DraveMind.py
endlocal
