@echo off
rem === Herstel-GPU-versie.bat ===
rem Zet DraveMind op de BEWEZEN GPU-combinatie van je Stable Diffusion WebUI:
rem   Python 3.10 + torch 2.1.2 + torchvision 0.16.2 + CUDA 12.1 (cu121).
rem Werkt ook op oudere kaarten (bv. GTX 1050 Ti). Toont de voortgang in dit venster.
setlocal
cd /d "%~dp0"

echo ============================================================
echo  DraveMind - herstellen op de GPU-combinatie van je A1111
echo  (Python 3.10 + torch 2.1.2 + CUDA 12.1)
echo ============================================================
echo.

rem --- Python 3.10 zoeken: eerst de A1111-locatie, dan py-launcher ---
set "PY="
if exist "D:\Python310\python.exe" set "PY=D:\Python310\python.exe"
if not defined PY ( py -3.10 -c "import sys" >nul 2>&1 && set "PY=py -3.10" )
if not defined PY ( py -3.11 -c "import sys" >nul 2>&1 && set "PY=py -3.11" )
if not defined PY (
  echo Geen Python 3.10/3.11 gevonden. Installeer Python 3.10 van python.org
  echo (of pas het pad bovenin dit bestand aan^).
  pause
  exit /b 1
)
echo Python: %PY%
echo.

echo Oude omgeving verwijderen (.venv)...
if exist ".venv" rmdir /s /q ".venv"

echo Nieuwe omgeving op Python 3.10 maken...
%PY% -m venv .venv
if errorlevel 1 ( echo Kon de venv niet maken. & pause & exit /b 1 )
call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip

echo.
echo [1/4] Basispakketten (pygame, whisper, stem, enz.)...
python -m pip install "numpy<2"
rem llama-cpp-python: AVX2-wheel (geen AVX-512 nodig; werkt op Ryzen 5 3600 e.d.)
python -m pip install llama-cpp-python --prefer-binary --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/avx2
python -m pip install --prefer-binary -r requirements.txt

echo.
echo [2/4] Torch 2.1.2 + CUDA 12.1 (zelfde als je A1111)...
echo (Als je A1111 deze al ophaalde, gebruikt pip de cache en gaat dit snel.)
python -m pip install torch==2.1.2 torchvision==0.16.2 --index-url https://download.pytorch.org/whl/cu121

echo.
echo [3/4] Beeld-AI (diffusers 0.30, passend bij torch 2.1.2, laadt ook SDXL)...
python -m pip install "diffusers==0.30.0" "transformers==4.44.2" "accelerate==0.33.0" "huggingface_hub==0.24.6" "safetensors>=0.4.2" "pillow>=10.0"

echo.
echo [4/4] Controle of de GPU gezien wordt...
python -c "import torch;print('CUDA beschikbaar:', torch.cuda.is_available());print('GPU:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'geen')"

echo.
echo ============================================================
echo  Klaar! Start nu Start-DraveMind.bat en ga naar Beeld.
echo ============================================================
pause
endlocal
