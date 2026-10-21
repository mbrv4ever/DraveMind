@echo off
rem === Maak-DraveMind-EXE-CPU.bat - lichte EXE (torch voor de processor, geen CUDA) ===
rem Resultaat: dist-cpu\DraveMind\DraveMind.exe  (~1 map, past op GitHub)
setlocal
cd /d "%~dp0"
set "PY="
for %%V in (3.10 3.11) do ( if not defined PY ( py -%%V -c "import sys" >nul 2>&1 && set "PY=py -%%V" ) )
if not defined PY ( echo Python 3.10 of 3.11 nodig. & pause & exit /b 1 )
set "BV=.build-cpu-venv"
if not exist "%BV%\Scripts\python.exe" ( %PY% -m venv "%BV%" )
set "VPY=%BV%\Scripts\python.exe"
"%VPY%" -m pip install --upgrade pip >nul 2>&1
"%VPY%" -m pip install torch==2.1.2 torchvision==0.16.2 --index-url https://download.pytorch.org/whl/cpu
if errorlevel 1 ( echo torch CPU installeren mislukt. & pause & exit /b 1 )
"%VPY%" -m pip install --prefer-binary --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/avx2 llama-cpp-python
"%VPY%" -m pip install "numpy<2" -r requirements.txt -r requirements-beeld.txt pyinstaller
if errorlevel 1 ( echo Installeren mislukt. & pause & exit /b 1 )
"%VPY%" -m PyInstaller --noconfirm --clean --distpath dist-cpu --workpath build-cpu DraveMind.spec
if not exist "dist-cpu\DraveMind\DraveMind.exe" ( echo Bouwen mislukt. & pause & exit /b 1 )
echo KLAAR: dist-cpu\DraveMind\DraveMind.exe
pause
