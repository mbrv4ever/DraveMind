@echo off
rem === herstel.bat - verwijdert .venv, build en dist voor een schone herstart ===
setlocal
cd /d "%~dp0"
echo Dit verwijdert .venv, build en dist. Je instellingen, modellen en geheugen
echo (DraveMind-data) blijven staan.
pause
if exist ".venv" rmdir /s /q ".venv"
if exist "build" rmdir /s /q "build"
if exist "dist" rmdir /s /q "dist"
echo Klaar.
pause
endlocal
