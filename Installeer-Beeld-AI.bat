@echo off
rem === Installeer-Beeld-AI.bat - zet de (zware) beeld-AI erbij ===
rem Eenmalig: installeert torch + diffusers in dezelfde .venv als DraveMind.
rem Daarna werkt de tab "Beeld" (tekst -> afbeelding). ~enkele GB download.
setlocal
cd /d "%~dp0"

if not exist ".venv" (
  echo Start eerst Start-DraveMind.bat een keer ^(maakt de .venv aan^).
  pause
  exit /b 1
)
call ".venv\Scripts\activate.bat"

echo.
echo Heb je een NVIDIA-GPU (bv. GTX 1050 Ti)? Dan is de CUDA-versie veel sneller.
set "GPU="
set /p GPU="Type J voor NVIDIA/CUDA, of N voor alleen CPU [J/N]: "

if /i "%GPU%"=="J" (
  echo Installeren van torch met CUDA ^(cu126^) ... grote download.
  python -m pip install torch==2.14.1 torchvision --index-url https://download.pytorch.org/whl/cu126
  if errorlevel 1 (
    echo CUDA-wheel mislukt, val terug op CPU-versie...
    python -m pip install torch --index-url https://download.pytorch.org/whl/cpu
  )
) else (
  echo Installeren van torch ^(CPU-versie^) ... grote download.
  python -m pip install torch==2.14.1 torchvision --index-url https://download.pytorch.org/whl/cpu
  if errorlevel 1 python -m pip install torch
)

python -m pip install -r requirements-beeld.txt

echo.
echo Klaar. Start DraveMind en ga naar de tab "Beeld".
echo Tip bij 4 GB VRAM (1050 Ti): houd het bij sd-turbo of stable-diffusion-v1-5
echo op 512px. SDXL is te groot voor 4 GB.
pause
endlocal
