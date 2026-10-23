@echo off
rem === Maak-DraveMind-EXE-CPU.bat - lichte EXE (torch voor de processor, geen CUDA) ===
rem Resultaat: dist-cpu\DraveMind\DraveMind.exe  (~1 map, past op GitHub)
rem Veiligheidskeuring 23-10-2026: Python 3.13 + torch 2.14 + transformers 5 + diffusers 0.38.
setlocal
cd /d "%~dp0"
set "PY="
for %%V in (3.13 3.12) do ( if not defined PY ( py -%%V -c "import sys" >nul 2>&1 && set "PY=py -%%V" ) )
if not defined PY ( echo Python 3.13 of 3.12 nodig. & pause & exit /b 1 )
set "BV=.build-cpu-venv"
if not exist "%BV%\Scripts\python.exe" ( %PY% -m venv "%BV%" )
set "VPY=%BV%\Scripts\python.exe"
"%VPY%" -m pip install --upgrade pip >nul 2>&1
"%VPY%" -m pip install torch==2.14.1 --index-url https://download.pytorch.org/whl/cpu
rem torchvision is niet nodig en breekt in de exe (operator torchvision::nms) - dus weg
"%VPY%" -m pip uninstall -y torchvision >nul 2>&1
if errorlevel 1 ( echo torch CPU installeren mislukt. & pause & exit /b 1 )
"%VPY%" -m pip install --prefer-binary --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/avx2 llama-cpp-python
"%VPY%" -m pip install -r requirements.txt -r requirements-beeld.txt pyinstaller
if errorlevel 1 ( echo Installeren mislukt. & pause & exit /b 1 )
"%VPY%" -m PyInstaller --noconfirm --clean --distpath dist-cpu --workpath build-cpu DraveMind.spec
if not exist "dist-cpu\DraveMind\DraveMind.exe" ( echo Bouwen mislukt. & pause & exit /b 1 )
rem snelgids mee in de download-map
if exist "DraveMind-Snelgids.pdf" copy /y "DraveMind-Snelgids.pdf" "dist-cpu\DraveMind\" >nul
echo KLAAR: dist-cpu\DraveMind\DraveMind.exe
pause
