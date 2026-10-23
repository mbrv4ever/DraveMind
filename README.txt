DraveAI - je eigen, lokale AI-werkplek (Dravenlock)
===================================================
(voorheen DraveMind. De datamap heet nog "DraveMind-data" zodat je instellingen,
modellen en geheugen behouden blijven.)

Wat is het?
-----------
Een chatapp met een AI die volledig LOKAAL op je pc draait (geen Ollama nodig).
Je kunt typen of inspreken, DraveMind kan gesproken antwoorden geven, online
zoeken en onthoudt gesprekken (lerend geheugen). Je kiest zelf welk taalmodel
hij gebruikt en kunt er andere downloaden.

Bediening
---------
- Typ een bericht onderaan en druk Enter (of klik Stuur).
- Klik op "Mic" om in te spreken; klik nog eens om te stoppen (spraak-naar-tekst).
- "Stem: aan/uit" zet gesproken antwoorden aan of uit.
- "Bestand": kies een bestand (tekst/code/CSV/JSON of PDF) om mee te sturen;
  DraveMind leest de inhoud en beantwoordt je vraag erover. Boven de invoerbalk
  zie je de bijlage; klik op [X] om hem te verwijderen.
- "Bewaar" (bovenbalk): sla het hele gesprek op als .txt (je kiest waar).
- "Geheugen" (bovenbalk): schrijf hier vaste richtlijnen - wat DraveMind wel/niet
  mag, je voorkeuren, gewenste stijl, enz. Die worden altijd gevolgd en blijven
  bewaard. 'Opslaan & terug' bewaart ze; 'Wis geleerde weetjes' wist de
  automatisch onthouden feiten (je richtlijnen blijven staan).
- Hernoemen: zeg of typ 'ik noem je X' / 'je heet nu X' en DraveMind heet
  voortaan X (blijft bewaard, ook na herstart).
- "Beeld": maak een afbeelding uit tekst (zie 'Beeld' hieronder).
- "Modellen": kies/download een taalmodel (zie hieronder).
- "Instellingen": stem kiezen, snelheid, toonhoogte, volume.
- "Nieuw": begin een nieuw gesprek (wist de korte-termijn context).
- Muiswiel: door de chat scrollen. Esc: terug / afsluiten.
- Knoppen "Gids" en "Doneer" staan altijd linksboven. Gids opent de snelgids;
  Doneer opent PayPal (paypal.me/roger076). Contact: service@dravenlock.nl.

Snel starten (Windows)
----------------------
1. Dubbelklik op Start-DraveMind.bat (installeert alles eenmalig, incl. de
   kant-en-klare llama-cpp-wheel).
2. Ga naar "Modellen" en kies een model. De eerste keer wordt het gedownload
   naar DraveMind-data\model (eenmalig; Qwen2.5 3B is ~2,1 GB).
3. Stel je vraag.

Modellen
--------
- Snelkeuze: Qwen2.5 3B (aanbevolen), 1.5B (licht), 0.5B (heel licht). Klik om te
  downloaden/kiezen. Het actieve model is groen.
- Zoeken op HuggingFace: typ in het zoekveld een term (bv. 'llama 8b', 'phi',
  'mistral', 'gemma') en klik Zoek. Je krijgt een lijst GGUF-modellen
  (populairste eerst). Klik op een model -> je ziet de beschikbare GGUF-bestanden
  (de aanrader 'q4_k_m' staat bovenaan). Klik op een bestand om het te downloaden
  en meteen te gebruiken. Geen HuggingFace-account nodig voor publieke modellen.
  Scroll door de lijst met het muiswiel.
- Tip: grotere modellen vragen meer geheugen/rekenkracht. Kies een "q4_k_m" GGUF
  voor een goede balans. Heel grote modellen zijn soms in delen gesplitst
  (...-of-...gguf); die laden niet altijd - kies bij voorkeur een enkel bestand.

Beeld (afbeeldingen maken EN beschrijven)
-----------------------------------------
De tab "Beeld" heeft bovenin drie knoppen: "Maken", "Beschrijven" en "Model".
De beeld-AI (torch + Stable Diffusion) is zwaar (paar GB), dus die zit er niet
standaard in. De APP installeert het zelf: ga naar Beeld -> Maken en klik op
"Beeld-AI installeren". De app kiest automatisch de CUDA-versie als je een
NVIDIA-GPU hebt (anders CPU). Eenmalig; daarna werken Maken en Beschrijven.
(De losse Installeer-Beeld-AI.bat bestaat nog als handmatige terugval.)

Maken (tekst -> beeld):
1. Kies "Maken", typ een beschrijving (bv. "een rode vos in een besneeuwd bos,
   digitale kunst") en druk Enter of klik Genereer.
2. Gemaakte afbeeldingen komen in een EIGEN map naast het programma:
   DraveMind-afbeeldingen (knop "Open map" onderaan). Alleen de laatste ~12
   blijven bewaard - geen opstapeling. Wil je er een echt houden, klik dan
   "Bewaar afbeelding" en kies zelf een plek/naam.
3. Formaat: rechts bij "Maken" kies je met < / > de afmeting (512x512 t/m
   768x768). Groter = meer detail maar zwaarder; bij 4 GB VRAM is 512 het veiligst.
4. Stappen: ook rechts, met < / >. Meer stappen = mooier/gedetailleerder maar
   trager. ~20-30 voor gewone modellen; voor 'turbo'- of 'hyper/lightning'-modellen
   juist weinig (4-8). De guidance stelt DraveMind zelf passend in per modeltype.
4. Een ander beeldmodel kies je in de Beeld-tab: klik op "Model". Daar heb je:
   - EIGEN MODELLEN: zet je eigen .safetensors/.ckpt (bijv. uit Stable Diffusion
     WebUI) in de map DraveMind-data\eigen-modellen (knop "Open map"), dan
     verschijnen ze vanzelf in de lijst - klik om te kiezen. Of klik
     "Bestand kiezen..." om er eentje los te selecteren.
   - SNELKEUZE: kant-en-klare modellen (sd-turbo, SD 1.5, SDXL-turbo) om te
     downloaden.
   - ZOEKEN op HuggingFace naar tekst->beeld modellen.
   Gedownloade modellen komen in DraveMind-data\image_model, los van de
   taalmodellen. (De "Modellen"-tab bovenin is alleen voor chat-taalmodellen.)
   Let op: de eerste afbeelding na het opstarten laadt het model in (~10-30s op
   GPU); daarna gaat elke volgende snel.

Beschrijven (beeld -> tekst):
1. Kies "Beschrijven" en klik "Kies afbeelding".
2. Klik "Beschrijf" voor een omschrijving, of typ een vraag ("hoeveel mensen
   staan er?") en druk Enter. Is er een taalmodel geladen, dan vertaalt DraveMind
   het antwoord automatisch naar het Nederlands.

GPU of CPU? In de Beeld-tab staat "Rekent op: GPU (CUDA)" of "CPU (traag)".
- Op de GPU is het snel en blijft je systeem-RAM laag (zoals Stable Diffusion
  WebUI). Op de CPU is het VEEL trager en loopt je RAM vol - dat wil je niet.
- Staat er "CPU" terwijl je een NVIDIA-kaart hebt? Dan is per ongeluk de
  CPU-versie van torch geinstalleerd. Klik op de knop "Installeer GPU (CUDA)"
  (verschijnt dan rechtsboven in Beeld) - die vervangt torch door de CUDA-versie.
  Herstart daarna DraveMind.
Tip bij 4 GB VRAM (bijv. GTX 1050 Ti): blijf bij sd-turbo of
stable-diffusion-v1-5 op 512px; SDXL is te groot voor 4 GB. Video maken zit er
bewust niet in (lokaal niet praktisch).

Een EXE maken
-------------
Dubbelklik op Maak-DraveMind-EXE.bat -> dist\DraveMind\DraveMind.exe (map-versie,
houd de hele map bij elkaar). De modellen zitten NIET in de build; die downloaden
zichzelf bij gebruik. herstel.bat ruimt .venv/build/dist op.

Instellingen (DraveMind-data\config.json)
-----------------------------------------
  "backend"        : "local" (eigen model) of "ollama"
  "repo" / "file"  : het actieve GGUF-model (ook via 'Modellen' te wijzigen)
  "voice_name/speed/pitch/volume" : stem (ook via 'Instellingen')
  "speak_answers"  : antwoorden uitspreken (true/false)
  "online_search"  : online zoeken aan/uit ; "search_engine": startpage/duckduckgo
  "auto_learn"     : na elk gesprek zelf een weetje opslaan
  "whisper_size"   : tiny/base/small/medium (spraakherkenning)
  "image_model"    : beeldmodel voor de Beeld-tab (diffusers-repo, def. sd-turbo)
  "image_steps"    : aantal stappen bij beeld maken (def. 4; meer = beter/trager)

Werkt iets niet?
----------------
- Geen model: ga naar 'Modellen' en download er een.
- "Mic" grijs: geen microfoon/sounddevice of geen whisper -> typ gewoon.
- Bij een crash: zie DraveMind-data\dravemind-fout.txt (of -model-fout.txt voor
  het laden van het model).
