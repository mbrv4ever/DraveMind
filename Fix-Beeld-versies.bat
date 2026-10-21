@echo off
rem === Fix-Beeld-versies.bat ===
rem Zet diffusers/transformers op de versies die passen bij torch 2.1.2.
rem (De nieuwste diffusers vereist torch.xpu uit torch 2.4+, wat wij niet gebruiken.)
rem Klein en snel: alleen deze pakketten, GEEN torch opnieuw.
setlocal
cd /d "%~dp0"

if not exist ".venv" (
  echo Geen .venv gevonden. Draai eerst Herstel-GPU-versie.bat of Start-DraveMind.bat.
  pause
  exit /b 1
)
call ".venv\Scripts\activate.bat"

echo Beeld-pakketten op de juiste (torch 2.1.2-)versies zetten...
echo (diffusers 0.30 laadt ook moderne SDXL-modellen, werkt nog met torch 2.1.2)
python -m pip install "diffusers==0.30.0" "transformers==4.44.2" "accelerate==0.33.0" "huggingface_hub==0.24.6" "safetensors>=0.4.2" "pillow>=10.0"

echo.
echo Klaar! Start DraveMind, ga naar Beeld - Maken en klik Genereer.
echo (Rekent op: GPU CUDA - de eerste afbeelding laadt het model even in.)
pause
endlocal
