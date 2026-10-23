@echo off
rem === Fix-Beeld-versies.bat ===
rem Zet diffusers/transformers op de geteste, veilige versies (zie requirements-beeld.txt).
rem Klein en snel: alleen deze pakketten, GEEN torch opnieuw.
setlocal
cd /d "%~dp0"

if not exist ".venv" (
  echo Geen .venv gevonden. Draai eerst Herstel-GPU-versie.bat of Start-DraveMind.bat.
  pause
  exit /b 1
)
call ".venv\Scripts\activate.bat"

echo Beeld-pakketten op de geteste versies zetten...
python -m pip install -r requirements-beeld.txt

echo.
echo Klaar! Start DraveMind, ga naar Beeld - Maken en klik Genereer.
pause
endlocal
