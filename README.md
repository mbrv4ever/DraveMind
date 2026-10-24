# DraveMind

Je eigen, lokale AI-werkplek (DraveAI).

## ⚡ Snelle plaatjes met een NVIDIA-videokaart (optioneel)

De gewone download hieronder is de **lichte versie**: één bestand, werkt op elke Windows-pc.
Praten, luisteren en chatten gaan net zo snel. Alleen **plaatjes maken** gebeurt op de
processor, en dat duurt een paar minuten per plaatje.

Heb je een **NVIDIA-videokaart** (bijvoorbeeld een GTX 1050 Ti of nieuwer)? Dan kun je de
**snelle versie** zelf installeren. Plaatjes zijn dan in seconden klaar:

1. Installeer **Python 3.10** van [python.org](https://www.python.org/downloads/release/python-31011/).
   Zet bij het installeren het vinkje **"Add Python to PATH"** aan.
2. Download deze broncode: groene knop **Code** → **Download ZIP**. Pak hem uit.
3. Dubbelklik op **`Herstel-GPU-versie.bat`**. Die installeert alles voor je videokaart
   (torch met CUDA, ± 3,5 GB). Dit duurt even, en je ziet de voortgang in het venster.
4. Start daarna met **`Start-DraveMind.bat`**.

> Liever zelf een snelle EXE bouwen? Na stap 3: **`Maak-DraveMind-EXE.bat`**.
> De lichte EXE bouw je met **`Maak-DraveMind-EXE-CPU.bat`**.

## 🎬 Uitlegvideo

[![Uitlegvideo DraveMind](https://dravenlock.nl/video/DraveMind.jpg)](https://dravenlock.nl/video/DraveMind.mp4)

[▶ Bekijk de uitlegvideo](https://dravenlock.nl/video/DraveMind.mp4) (ongeveer 2 minuten, Nederlands)

*Categorie: AI · versie 1.1.1*

## ⬇️ Downloaden (Windows, geen Python nodig)

### [👉 Download DraveMind 1.1.1](https://github.com/mbrv4ever/DraveMind/releases/latest)

1. Klik op de link en download het **.zip**-bestand.
2. Pak het uit: rechtsklik → **Alles uitpakken...**
3. Dubbelklik op **DraveMind.exe**.

> Zie je een blauw scherm "Windows heeft uw pc beschermd"? Klik op **Meer informatie** → **Toch uitvoeren**.

## Vanaf de broncode

Installeer Python 3.10 – 3.13 en de benodigde pakketten (zie `requirements.txt` als die er is), en start het hoofdbestand (`.py`). Eventuele `.bat`-bestanden doen dit voor je.

## Licentie

Vrije software onder de **GNU GPL v3.0** (zie [LICENSE](LICENSE)). Gemaakt door **Dravenlock** (Roger & Claudio). Donaties welkom, nooit verplicht.
