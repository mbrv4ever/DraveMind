@echo off
rem === Fix-Chat.bat ===
rem Herstelt de chat-AI (llama-cpp) met een versie die bij je processor past.
rem De standaard wheel gebruikte instructies (AVX-512) die niet elke CPU heeft
rem (Ryzen 5 3600 = AVX2). Daarom installeren we de AVX2-versie.
setlocal
cd /d "%~dp0"

if not exist ".venv" (
  echo Geen .venv gevonden. Draai eerst Start-DraveMind.bat of Herstel-GPU-versie.bat.
  pause
  exit /b 1
)
call ".venv\Scripts\activate.bat"

echo Oude llama-cpp verwijderen...
python -m pip uninstall -y llama-cpp-python

echo.
echo AVX2-versie installeren (past bij Ryzen 5 3600 e.d.)...
python -m pip install llama-cpp-python --no-deps --no-cache-dir --index-url https://abetlen.github.io/llama-cpp-python/whl/avx2
if errorlevel 1 (
  echo AVX2 lukte niet, val terug op de basis-versie (werkt op elke CPU, iets trager)...
  python -m pip install llama-cpp-python --no-deps --no-cache-dir --index-url https://abetlen.github.io/llama-cpp-python/whl/basic
)

echo.
echo Controle...
python -c "import llama_cpp; print('llama-cpp OK, versie', llama_cpp.__version__)"
echo.
echo Klaar. Start DraveMind en kies een model bij 'Modellen'.
pause
endlocal
