@echo off
rem === Herstel-GPU-versie.bat ===
rem Zet DraveMind op de GPU-combinatie (veiligheidskeuring 23-10-2026):
rem   Python 3.13 + torch 2.14.1 + CUDA 12.6 (cu126).
rem Werkt ook op oudere kaarten (getest op een GTX 1050 Ti). Toont de voortgang in dit venster.
setlocal
cd /d "%~dp0"

echo ============================================================
echo  DraveMind - GPU-versie (Python 3.13 + torch 2.14.1 + CUDA 12.6)
echo ============================================================
echo.

set "PY="
for %%V in (3.13 3.12) do ( if not defined PY ( py -%%V -c "import sys" >nul 2>&1 && set "PY=py -%%V" ) )
if not defined PY (
  echo Geen Python 3.13/3.12 gevonden. Installeer Python 3.13 van python.org.
  pause
  exit /b 1
)
echo Python: %PY%
echo.

rem De oude omgeving wordt NIET weggegooid, alleen opzij gezet (.venv-oud).
if exist ".venv" (
  if exist ".venv-oud" ( echo Er staat al een .venv-oud. Verplaats of verwijder die eerst zelf. & pause & exit /b 1 )
  echo Oude omgeving opzij zetten als .venv-oud ...
  ren ".venv" ".venv-oud"
)

echo Nieuwe omgeving maken...
%PY% -m venv .venv
if errorlevel 1 ( echo Kon de venv niet maken. & pause & exit /b 1 )
call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip

echo.
echo [1/4] Basispakketten (pygame, whisper, stem, enz.)...
python -m pip install llama-cpp-python --prefer-binary --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/avx2
python -m pip install --prefer-binary -r requirements.txt

echo.
echo [2/4] Torch 2.14.1 + CUDA 12.6 (grote download, ~2,6 GB)...
python -m pip install torch==2.14.1 torchvision --index-url https://download.pytorch.org/whl/cu126

echo.
echo [3/4] Beeld-AI (diffusers, transformers)...
python -m pip install -r requirements-beeld.txt

echo.
echo [4/4] Controle of de GPU gezien wordt...
python -c "import torch;print('CUDA beschikbaar:', torch.cuda.is_available());print('GPU:', torch.cuda.get_device_name(0) if torch.cuda.is_available() else 'geen')"

echo.
echo ============================================================
echo  Klaar! Start nu Start-DraveMind.bat en ga naar Beeld.
echo  Werkt alles? Dan mag je de map .venv-oud zelf weggooien.
echo ============================================================
pause
endlocal
