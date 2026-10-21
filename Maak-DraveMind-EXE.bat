@echo off
rem === Maak-DraveMind-EXE.bat - bouwt dist\DraveMind\DraveMind.exe ===
setlocal
cd /d "%~dp0"

set PY=
for %%V in (3.13 3.12 3.11 3.10) do (
  if not defined PY ( py -%%V -c "import sys" >nul 2>&1 && set "PY=py -%%V" )
)
if not defined PY ( py -3 -c "import sys" >nul 2>&1 && set "PY=py -3" )
if not defined PY ( python -c "import sys" >nul 2>&1 && set "PY=python" )
if not defined PY ( echo Geen Python gevonden. & pause & exit /b 1 )

if not exist ".venv" ( %PY% -m venv .venv )
call ".venv\Scripts\activate.bat"

python -m pip install --upgrade pip
rem llama-cpp-python als kant-en-klare AVX2-wheel (de cpu/standaard crasht op
rem sommige CPU's met "illegal instruction"; AVX2 werkt o.a. op Ryzen 5 3600)
python -m pip install --prefer-binary --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/avx2 llama-cpp-python
if errorlevel 1 python -m pip install --prefer-binary --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/basic llama-cpp-python
python -m pip install -r requirements.txt
python -m pip install pyinstaller

echo.
echo === Bouwen met PyInstaller... ===
pyinstaller --noconfirm DraveMind.spec

echo.
echo Klaar! De app staat in:  dist\DraveMind\DraveMind.exe
echo Modellen downloaden bij gebruik naar dist\DraveMind\DraveMind-data.
echo.
pause
endlocal
