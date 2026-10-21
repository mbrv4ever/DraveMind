# -*- coding: utf-8 -*-
"""mind.py - DraveMind: een eigen, lokale AI-chatapp (Dravenlock).

Chat-venster met typen + microfoon (push-to-talk via mic-knop), gesproken
antwoorden (neuvoice, uit te zetten), online zoeken en een lerend geheugen.
Lokaal model via llama-cpp-python; modellen kies/download je in het
Modellen-scherm (vaste lijst + zelf een HuggingFace-repo invoeren).
"""
from __future__ import annotations

import importlib.util
import json
import os
import shutil
import subprocess
import sys
import threading
import time
import webbrowser

import pygame

from brain import Brain
from localbrain import LocalBackend
from memory import Memory
from search import Search
from listen import Ears
from speak import Voice
import models as modelreg
from imagegen import ImageGen
from describe import ImageDescriber

WIDTH, HEIGHT = 1200, 820
FPS = 60

DONATE_URL = "https://paypal.me/roger076"
CONTACT_EMAIL = "service@dravenlock.nl"

BG = (16, 17, 22)
BAR = (26, 28, 36)
PANEL = (30, 32, 41)
LINE = (52, 55, 66)
TEXT = (224, 226, 232)
MUTE = (140, 144, 156)
ACCENT = (108, 162, 214)
GREEN = (104, 196, 120)
AMBER = (210, 180, 96)
USERCOL = (150, 200, 255)
AICOL = (210, 212, 220)
RED = (210, 90, 80)


def beeld_installed():
    """True als torch + diffusers + transformers beschikbaar zijn."""
    for mod in ("torch", "diffusers", "transformers"):
        try:
            if importlib.util.find_spec(mod) is None:
                return False
        except Exception:
            return False
    return True


def _no_window():
    return {"creationflags": 0x08000000} if os.name == "nt" else {}


def has_nvidia():
    """Robuuste check op een NVIDIA-GPU: nvidia-smi (PATH + System32), en anders
    de Windows-videokaartlijst (wmic / PowerShell). Zo wordt de kaart ook gevonden
    als nvidia-smi niet in het PATH staat."""
    try:
        if shutil.which("nvidia-smi"):
            return True
        win = os.environ.get("WINDIR", r"C:\Windows")
        if os.path.isfile(os.path.join(win, "System32", "nvidia-smi.exe")):
            return True
    except Exception:
        pass
    if os.name == "nt":
        for cmd in (["wmic", "path", "win32_VideoController", "get", "name"],
                    ["powershell", "-NoProfile", "-Command",
                     "(Get-CimInstance Win32_VideoController).Name"]):
            try:
                out = subprocess.run(cmd, capture_output=True, text=True,
                                     timeout=10, **_no_window())
                if "nvidia" in (out.stdout or "").lower():
                    return True
            except Exception:
                pass
    return False


def data_dir():
    if getattr(sys, "frozen", False):
        base = os.path.dirname(os.path.abspath(sys.executable))
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    d = os.path.join(base, "DraveMind-data")
    try:
        os.makedirs(d, exist_ok=True)
    except Exception:
        pass
    return d


# afmetingen om uit te kiezen (veelvouden van 8; modest voor 4 GB VRAM)
SIZE_PRESETS = [(512, 512), (512, 768), (768, 512), (768, 768)]


def output_dir():
    """Eigen, vindbare map voor gemaakte afbeeldingen (naast de exe/het script)."""
    if getattr(sys, "frozen", False):
        base = os.path.dirname(os.path.abspath(sys.executable))
    else:
        base = os.path.dirname(os.path.abspath(__file__))
    d = os.path.join(base, "DraveMind-afbeeldingen")
    try:
        os.makedirs(d, exist_ok=True)
    except Exception:
        pass
    return d


def prune_outputs(keep=12):
    """Houd alleen de nieuwste 'keep' gemaakte afbeeldingen; ruim oudere op."""
    try:
        d = output_dir()
        files = [os.path.join(d, f) for f in os.listdir(d)
                 if f.lower().startswith("beeld-") and f.lower().endswith(".png")]
        files.sort(key=lambda p: os.path.getmtime(p), reverse=True)
        for p in files[keep:]:
            try:
                os.remove(p)
            except Exception:
                pass
    except Exception:
        pass


def eigen_models_dir():
    """Map waar de gebruiker eigen modelbestanden (.safetensors/.ckpt) kan zetten."""
    d = os.path.join(data_dir(), "eigen-modellen")
    try:
        os.makedirs(d, exist_ok=True)
    except Exception:
        pass
    return d


def list_eigen_models():
    """Eigen modelbestanden in de map, als (naam, pad, grootte_in_GB)."""
    out = []
    try:
        for f in sorted(os.listdir(eigen_models_dir())):
            if f.lower().endswith((".safetensors", ".ckpt")):
                p = os.path.join(eigen_models_dir(), f)
                try:
                    gb = os.path.getsize(p) / 1024 ** 3
                except Exception:
                    gb = 0.0
                out.append((f, p, gb))
    except Exception:
        pass
    return out


def load_config():
    cfg = {
        "backend": "local",
        "repo": "Qwen/Qwen2.5-3B-Instruct-GGUF",
        "file": "qwen2.5-3b-instruct-q4_k_m.gguf",
        "ollama_host": "http://localhost:11434",
        "model": "llama3.2",
        "voice_name": "M1", "voice_speed": 1.0, "voice_pitch": 1.0,
        "voice_volume": 1.0, "speak_answers": True,
        "lang": "nl", "whisper_size": "base",
        "online_search": True, "search_engine": "startpage", "auto_learn": True,
        "instructions": "",
        "image_model": "Lykon/dreamshaper-8", "image_steps": 25,
        "image_width": 512, "image_height": 512,
        "image_negative": ("ugly, deformed, disfigured, bad anatomy, wrong "
                           "proportions, extra limbs, extra fingers, mutated hands, "
                           "blurry, low quality, lowres, watermark, text, signature, "
                           "jpeg artifacts, cropped"),
        "ui_scale": 1.0,
    }
    try:
        with open(os.path.join(data_dir(), "config.json"), "r", encoding="utf-8") as f:
            cfg.update(json.load(f))
    except Exception:
        pass
    return cfg


def save_config(cfg):
    try:
        with open(os.path.join(data_dir(), "config.json"), "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=2)
    except Exception:
        pass


def wrap_text(text, font, maxw):
    lines = []
    for para in (text or "").split("\n"):
        words = para.split(" ")
        line = ""
        for w in words:
            test = (line + " " + w).strip()
            if font.size(test)[0] > maxw and line:
                lines.append(line)
                line = w
            else:
                line = test
        lines.append(line)
    return lines


class App:
    def __init__(self, screen):
        self.screen = screen
        self.clock = pygame.time.Clock()
        self.running = True
        self.cfg = load_config()
        self.screen_name = "chat"        # chat / models / settings
        self.show_help = False           # snelgids-overlay (F1)
        self.zones = []                  # (rect, action) klikzones per frame

        self.voice = Voice(self.cfg["voice_name"], self.cfg["lang"], data_dir())
        self.voice.speed = self.cfg.get("voice_speed", 1.0)
        self.voice.pitch = self.cfg.get("voice_pitch", 1.0)
        self.voice.volume = self.cfg.get("voice_volume", 1.0)
        self.speak_answers = self.cfg.get("speak_answers", True)

        self.brain = Brain(host=self.cfg["ollama_host"], model=self.cfg["model"])
        if self.cfg.get("backend", "local") == "local":
            self.brain.local = LocalBackend(self.cfg["repo"], self.cfg["file"], data_dir())
        self.memory = Memory(os.path.join(data_dir(), "dravemind-geheugen.db"))
        self.brain.memory = self.memory
        # bij opstart de database lezen: eerder gegeven naam meteen kennen
        self.brain.assistant_name = self.memory.get_meta("assistant_name", "")
        self.brain.user_name = self.memory.get_meta("user_name", "")
        self.brain.auto_learn = self.cfg.get("auto_learn", True)
        self.instructions = self.cfg.get("instructions", "")
        self.brain.instructions = self.instructions
        if self.cfg.get("online_search", True):
            self.brain.search = Search(engine=self.cfg.get("search_engine", "startpage"))
        self.ears = Ears(self.cfg["whisper_size"], self.cfg["lang"])
        self.imagegen = ImageGen(self.cfg.get("image_model", "stabilityai/sd-turbo"),
                                 data_dir(), steps=self.cfg.get("image_steps", 4),
                                 width=self.cfg.get("image_width", 512),
                                 height=self.cfg.get("image_height", 512))
        # huidige formaat-keuze (index in SIZE_PRESETS)
        cur_size = (self.cfg.get("image_width", 512), self.cfg.get("image_height", 512))
        self.size_idx = SIZE_PRESETS.index(cur_size) if cur_size in SIZE_PRESETS else 0
        self.describer = ImageDescriber(data_dir())
        if beeld_installed():
            # op de achtergrond bepalen of we op GPU of CPU rekenen (torch laden duurt even)
            threading.Thread(target=self.imagegen.cuda_available, daemon=True).start()

        self.msgs = [("ai", "Hallo! Stel je vraag - typ of gebruik de microfoon. "
                            "Kies eerst een model bij 'Modellen'.")]
        self.input = ""
        self.caret = 0                   # cursorpositie in het actieve tekstveld
        self.attached = None             # (bestandsnaam, tekst) bijlage voor volgende bericht
        self.scroll = 0                  # regels omhoog vanaf de bodem
        self.state = "idle"              # idle/thinking/searching/listening/speaking
        self.busy = False
        self.loading = False
        self.load_msg = ""
        self.recording = False

        # modellen-scherm: HuggingFace-zoeken
        self.hf_query = ""
        self.hf_kind = "gguf"            # "gguf" (chat) of "image" (tekst->beeld)
        self.hf_focus = False
        self.hf_results = []             # gevonden repo-ids
        self.hf_repo = ""                # gekozen repo
        self.hf_files = []               # GGUF-bestanden in die repo
        self.hf_busy = False
        self.hf_msg = ""
        self.mm_scroll = 0               # scroll in resultaten/bestanden
        # afbeelding-tab (maken)
        self.img_mode = "make"           # "make", "describe" of "model"
        self.img_prompt = ""
        self.img_neg = self.cfg.get("image_negative", "")   # negatieve prompt
        self.img_focus_field = "prompt"  # welk tekstvak actief is: "prompt" of "neg"
        self.img_focus = False
        self.img_busy = False
        self.img_cancel = False
        self.img_tr_busy = False         # bezig met prompt vertalen
        self.img_msg = ""
        self.img_path = None
        self.img_surface = None
        self._img_loaded = None
        # afbeelding-tab (beschrijven)
        self.desc_path = None
        self.desc_surface = None
        self._desc_loaded = None
        self.desc_text = ""
        self.desc_q = ""
        self.desc_busy = False
        # beeld-AI installatie (in-app, eenmalig)
        self.img_install_busy = False
        self.img_install_msg = ""
        # afbeelding-tab (model kiezen) - eigen HuggingFace-zoekstatus
        self.img_hf_query = ""
        self.img_hf_focus = False
        self.img_hf_results = []
        self.img_hf_busy = False
        self.img_hf_msg = ""
        self.img_hf_scroll = 0
        # instellingen
        self.set_idx = 0

        self.ui_scale = float(self.cfg.get("ui_scale", 1.0))
        self._build_fonts()

        self.ready = False           # klaar met opstarten (voor het splashscherm)
        threading.Thread(target=self._startup, daemon=True).start()

    def _build_fonts(self):
        """(Her)maak de lettertypes op basis van ui_scale (toegankelijkheid)."""
        sc = self.ui_scale
        self.f_title = pygame.font.Font(None, max(20, int(38 * sc)))
        self.f = pygame.font.Font(None, max(16, int(26 * sc)))
        self.fs = pygame.font.Font(None, max(14, int(22 * sc)))
        self.fi = pygame.font.Font(None, max(20, int(30 * sc)))  # invoervelden, groter
        self.f_bar = pygame.font.Font(None, 22)    # bovenbalk-knoppen: VAST
        self.f_bartitle = pygame.font.Font(None, 32)  # bovenbalk-titel: VAST

    # ---------- opstart / model ----------
    def _startup(self):
        # stem voorbereiden op de achtergrond (afgedekt door het splashscherm)
        try:
            self.voice.warmup()
        except Exception:
            pass
        if self.brain.local is not None:
            present = self.brain.local.model_present()
            self.load_msg = ("Model laden..." if present
                             else "Model nog niet gedownload - ga naar 'Modellen'")
            if present:
                self.loading = True
                self.brain.local.ensure()
                self.loading = False
                self.load_msg = ""
        self.ready = True            # opstarten klaar -> splashscherm mag sluiten

    def _set_model(self, repo, file):
        """Wissel/download een model (op de achtergrond)."""
        self.cfg["repo"] = repo
        self.cfg["file"] = file
        save_config(self.cfg)
        if self.brain.local is None:
            self.brain.local = LocalBackend(repo, file, data_dir())
        else:
            self.brain.local.set_model(repo, file)

        def work():
            present = self.brain.local.model_present(file=file)
            self.load_msg = "Model laden..." if present else "Model downloaden... (kan even duren)"
            self.loading = True
            ok = self.brain.local.ensure()
            self.loading = False
            self.load_msg = "" if ok else "Model laden mislukt (zie data-map)"
            if ok:
                self._add("ai", "Model geladen: %s. Waar kan ik mee helpen?" % file)
        threading.Thread(target=work, daemon=True).start()

    def _set_image_model(self, repo):
        """Kies een beeldmodel (diffusers-repo OF pad naar een eigen bestand)."""
        if self.img_busy or self.img_install_busy:
            self.img_msg = "Wacht even tot de huidige actie klaar is voor je wisselt."
            return
        self.cfg["image_model"] = repo
        save_config(self.cfg)
        self.imagegen.set_model(repo)
        naam = os.path.basename(repo) if ("\\" in repo or "/" in repo) else repo
        self.img_msg = "Beeldmodel ingesteld: %s" % naam
        self.screen_name = "image"
        self.img_mode = "make"

    def _pick_image_model(self):
        """Kies een eigen modelbestand (.safetensors / .ckpt), bv. uit je A1111."""
        path = None
        try:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            initial = r"D:\stable-diffusion-webui-master\models\Stable-diffusion"
            if not os.path.isdir(initial):
                initial = None
            path = filedialog.askopenfilename(
                title="Kies een beeldmodel (.safetensors of .ckpt)",
                initialdir=initial,
                filetypes=[("Modelbestanden", "*.safetensors *.ckpt"),
                           ("Alle bestanden", "*.*")])
            root.destroy()
        except Exception:
            path = None
        if path:
            self._set_image_model(path)

    def _img_hf_search(self):
        if self.img_hf_busy:
            return
        q = self.img_hf_query.strip()
        if not q:
            return
        self.img_hf_busy = True
        self.img_hf_results = []
        self.img_hf_msg = "Zoeken op HuggingFace..."
        self.img_hf_scroll = 0

        def work():
            res = modelreg.search_hf(self.img_hf_query, kind="image")
            self.img_hf_results = res
            self.img_hf_msg = "" if res else "Niets gevonden (of geen internet)."
            self.img_hf_busy = False
        threading.Thread(target=work, daemon=True).start()

    # ---------- chat ----------
    def _add(self, role, text):
        self.msgs.append((role, text))
        self.scroll = 0

    def _send(self, text):
        text = (text or "").strip()
        if self.busy or (not text and not self.attached):
            return
        prompt = text
        shown = text
        if self.attached:
            name, content = self.attached
            self.attached = None
            prompt = ("Hieronder de inhoud van een bestand '%s'. Gebruik dit om te "
                      "antwoorden.\n\n%s\n\nVraag: %s"
                      % (name, content, text or "Vat dit bestand kort samen."))
            shown = ("[bestand: %s] " % name) + (text or "(samenvatten)")
        self._add("user", shown)
        self.busy = True
        self.state = "thinking"
        threading.Thread(target=self._worker, args=(prompt,), daemon=True).start()

    # ---------- bestand uploaden / gesprek opslaan ----------
    def _pick_file(self):
        if self.busy:
            return
        path = None
        try:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            path = filedialog.askopenfilename(
                title="Kies een bestand",
                filetypes=[("Tekst en code", "*.txt *.md *.py *.csv *.json *.log *.html *.xml"),
                           ("PDF", "*.pdf"), ("Alle bestanden", "*.*")])
            root.destroy()
        except Exception:
            self._add("ai", "Bestandskiezer niet beschikbaar op deze pc.")
            return
        if not path:
            return
        text = self._read_file_text(path)
        if text:
            self.attached = (os.path.basename(path), text[:6000])
        else:
            self._add("ai", "Kon dit bestand niet lezen (leeg of niet-tekst).")

    def _read_file_text(self, path):
        try:
            if path.lower().endswith(".pdf"):
                try:
                    import pdfplumber
                    out = []
                    with pdfplumber.open(path) as pdf:
                        for pg in pdf.pages[:20]:
                            out.append(pg.extract_text() or "")
                    return "\n".join(out).strip()
                except Exception:
                    return ""
            with open(path, "r", encoding="utf-8", errors="ignore") as f:
                return f.read()
        except Exception:
            return ""

    def _save_chat(self):
        lines = []
        for role, txt in self.msgs:
            who = "Jij" if role == "user" else (self.brain.assistant_name or "DraveAI")
            lines.append("%s: %s" % (who, txt))
        content = "\n\n".join(lines)
        default = "gesprek-" + time.strftime("%Y%m%d-%H%M%S") + ".txt"
        path = None
        try:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            path = filedialog.asksaveasfilename(
                title="Gesprek opslaan", defaultextension=".txt",
                initialfile=default, filetypes=[("Tekstbestand", "*.txt")])
            root.destroy()
        except Exception:
            path = None
        if not path:
            path = os.path.join(data_dir(), default)
        try:
            with open(path, "w", encoding="utf-8") as f:
                f.write(content)
            self._add("ai", "Gesprek opgeslagen: " + path)
        except Exception:
            self._add("ai", "Opslaan van het gesprek is mislukt.")

    def _worker(self, text):
        try:
            reply = self.brain.ask(text, on_status=self._on_status)
            self._add("ai", reply)
            if self.speak_answers and self.voice.enabled:
                self.state = "speaking"
                self.voice.speak_sync(reply)
        except Exception:
            self._add("ai", "(er ging iets mis)")
        finally:
            self.state = "idle"
            self.busy = False

    def _on_status(self, status):
        if status in ("searching", "thinking", "speaking"):
            self.state = status

    # ---------- microfoon ----------
    def _toggle_mic(self):
        if not self.ears.available() or self.busy:
            return
        if not self.recording:
            self.ears.start()
            if self.ears.recording():
                self.recording = True
                self.state = "listening"
        else:
            self.recording = False
            audio = self.ears.stop()
            self.busy = True
            self.state = "thinking"
            threading.Thread(target=self._mic_worker, args=(audio,), daemon=True).start()

    def _mic_worker(self, audio):
        try:
            txt = self.ears.transcribe(audio)
            if txt:
                self._add("user", txt)
                reply = self.brain.ask(txt, on_status=self._on_status)
                self._add("ai", reply)
                if self.speak_answers and self.voice.enabled:
                    self.state = "speaking"
                    self.voice.speak_sync(reply)
            else:
                self._add("ai", "(niets verstaan)")
        except Exception:
            pass
        finally:
            self.state = "idle"
            self.busy = False

    # ---------- events ----------
    def run(self):
        try:
            while self.running:
                self.clock.tick(FPS)
                t = pygame.time.get_ticks() / 1000.0
                for e in pygame.event.get():
                    if e.type == pygame.QUIT:
                        self.running = False
                    elif e.type == pygame.KEYDOWN:
                        self._keydown(e)
                    elif e.type == pygame.TEXTINPUT:
                        self._textinput(e.text)
                    elif e.type == pygame.MOUSEBUTTONDOWN:
                        if e.button == 1:
                            self._click(e.pos)
                        elif e.button == 4:
                            if self.screen_name == "models":
                                self.mm_scroll = max(0, self.mm_scroll - 2)
                            elif self.screen_name == "image" and self.img_mode == "model":
                                self.img_hf_scroll = max(0, self.img_hf_scroll - 2)
                            else:
                                self.scroll += 3
                        elif e.button == 5:
                            if self.screen_name == "models":
                                self.mm_scroll += 2
                            elif self.screen_name == "image" and self.img_mode == "model":
                                self.img_hf_scroll += 2
                            else:
                                self.scroll = max(0, self.scroll - 3)
                self._draw(t)
                pygame.display.flip()
        finally:
            self._shutdown()

    def _focused_field(self):
        if self.screen_name == "models" and self.hf_focus:
            return "hf"
        if self.screen_name == "image":
            if self.img_mode == "describe":
                return "descq"
            if self.img_mode == "model":
                return "imghf"
            return "imgneg" if self.img_focus_field == "neg" else "img"
        return "chat" if self.screen_name == "chat" else None

    # ---------- HuggingFace zoeken ----------
    def _hf_search(self):
        if self.hf_busy:
            return
        self.hf_busy = True
        self.hf_repo = ""
        self.hf_files = []
        self.hf_results = []
        self.hf_msg = "Zoeken op HuggingFace..."
        self.mm_scroll = 0

        def work():
            res = modelreg.search_hf(self.hf_query, kind="gguf")
            self.hf_results = res
            self.hf_msg = "" if res else "Niets gevonden (of geen internet)."
            self.hf_busy = False
        threading.Thread(target=work, daemon=True).start()

    def _hf_open_repo(self, repo):
        if self.hf_busy:
            return
        self.hf_busy = True
        self.hf_repo = repo
        self.hf_files = []
        self.hf_msg = "Bestanden ophalen..."
        self.mm_scroll = 0

        def work():
            files = modelreg.list_gguf_files(repo)
            self.hf_files = files
            self.hf_msg = "" if files else "Geen GGUF-bestanden in deze repo."
            self.hf_busy = False
        threading.Thread(target=work, daemon=True).start()

    # ---- beeld-AI installeren (in een APART venster met live voortgang) ----
    def _install_beeld(self, force_cuda=False):
        if self.img_install_busy:
            return
        if getattr(sys, "frozen", False):
            self.img_install_msg = ("Kan niet vanuit de EXE installeren. Start via "
                                    "Start-DraveMind.bat (launcher-versie).")
            return
        self.img_install_busy = True
        gpu = force_cuda or has_nvidia()
        self.img_install_msg = ("Installatie gestart in een APART venster - volg daar de "
                                "voortgang (download ~2,7 GB). Ik meld het hier zodra klaar.")

        def work():
            try:
                py = sys.executable
                # cu121 + torch 2.1.2 = bewezen combinatie (zelfde als A1111),
                # werkt ook op oudere kaarten zoals de GTX 1050 Ti.
                cu = "https://download.pytorch.org/whl/cu121"
                cpu = "https://download.pytorch.org/whl/cpu"
                d = data_dir()
                marker = os.path.join(d, "beeld-install-klaar.txt")
                try:
                    if os.path.exists(marker):
                        os.remove(marker)
                except Exception:
                    pass
                force = " --force-reinstall" if force_cuda else ""
                bat = os.path.join(d, "_beeld_install.bat")
                if gpu:
                    torch_lines = [
                        # eerst de bewezen versie (vereist Python 3.10/3.11)
                        '"%s" -m pip install torch==2.1.2 torchvision==0.16.2 '
                        '--index-url %s%s' % (py, cu, force),
                        # lukt dat niet (nieuwere Python): nieuwste CUDA-torch
                        'if errorlevel 1 "%s" -m pip install torch torchvision '
                        '--index-url %s' % (py, cu),
                        # uiterste terugval: CPU
                        'if errorlevel 1 "%s" -m pip install torch --index-url %s' % (py, cpu),
                    ]
                else:
                    torch_lines = [
                        '"%s" -m pip install torch --index-url %s' % (py, cpu),
                    ]
                lines = [
                    "@echo off",
                    "title DraveAI - Beeld-AI installeren",
                    "echo ==== DraveAI: Beeld-AI installeren ====",
                    "echo Dit kan enkele minuten duren. Even geduld...",
                    "echo.",
                    '"%s" -m pip install "numpy<2"' % py,
                ] + torch_lines + [
                    '"%s" -m pip install "diffusers==0.30.0" "transformers==4.44.2" '
                    '"accelerate==0.33.0" "huggingface_hub==0.24.6" '
                    '"safetensors>=0.4.2" "pillow>=10.0"' % py,
                    'echo done> "%s"' % marker,
                    "echo.",
                    "echo Klaar! Sluit dit venster en ga terug naar DraveAI.",
                    "pause",
                ]
                with open(bat, "w", encoding="utf-8") as f:
                    f.write("\r\n".join(lines))
                if os.name == "nt":
                    subprocess.Popen(["cmd", "/c", bat], creationflags=0x00000010)  # CREATE_NEW_CONSOLE
                else:
                    subprocess.Popen(["bash", bat])
                # wachten tot het venster klaar is (marker verschijnt)
                import time as _t
                t0 = _t.time()
                while not os.path.exists(marker) and _t.time() - t0 < 3600:
                    _t.sleep(1.0)
                importlib.invalidate_caches()
                self.imagegen._cuda = None       # opnieuw bepalen GPU/CPU
                self.imagegen.pipe = None        # herlaad model op het juiste apparaat
                if not beeld_installed():
                    self.img_install_msg = ("Installatie lijkt niet gelukt. Kijk in het "
                                            "venster naar de foutmelding.")
                    return
                self.imagegen.failed = False
                self.describer = ImageDescriber(data_dir())
                # in een VERS proces checken of CUDA nu echt beschikbaar is
                gpu_ok = False
                try:
                    chk = subprocess.run(
                        [py, "-c", "import torch;print(torch.cuda.is_available())"],
                        capture_output=True, text=True, timeout=120, **_no_window())
                    gpu_ok = "true" in (chk.stdout or "").lower()
                except Exception:
                    pass
                if gpu_ok:
                    self.img_install_msg = ("Klaar! GPU (CUDA) gevonden. SLUIT DraveAI "
                                            "en start opnieuw - daarna rekent hij op de GPU.")
                else:
                    self.img_install_msg = ("Klaar, maar GEEN CUDA-GPU gevonden - "
                                            "waarschijnlijk een verouderde NVIDIA-driver. "
                                            "Werk je driver bij (nvidia.com) en klik daarna "
                                            "opnieuw op 'Installeer GPU (CUDA)'. Tot dan: CPU.")
            except Exception as e:
                self.img_install_msg = "Installatie mislukt: %s" % str(e)[:80]
            finally:
                self.img_install_busy = False
        threading.Thread(target=work, daemon=True).start()

    # ---- beeld (tekst -> afbeelding) ----
    def _img_generate(self):
        prompt = self.img_prompt.strip()
        if not prompt or self.img_busy:
            return
        neg = self.img_neg.strip()
        # negatieve prompt onthouden voor volgende keer
        self.cfg["image_negative"] = self.img_neg
        save_config(self.cfg)
        self.img_busy = True
        self.img_cancel = False
        # vorige afbeelding weghalen, zodat je ziet dat hij bezig is
        self.img_surface = None
        self.img_path = None
        self._img_loaded = None
        present = self.imagegen.model_present()
        self.img_msg = ("Beeldmodel laden..." if present else
                        "Beeldmodel downloaden (eenmalig, enkele GB)... dit kan lang "
                        "duren, vooral op CPU. Even geduld.")

        def work():
            try:
                import time as _t
                if not self.imagegen.ensure():
                    err = self.imagegen.error or ""
                    if "SDXL" in err or "VRAM" in err:
                        self.img_msg = err          # nette uitleg (SDXL te zwaar)
                    else:
                        self.img_msg = ("Mislukt. Draai eerst Installeer-Beeld-AI.bat "
                                        "(torch + diffusers). Details in DraveMind-data"
                                        "\\dravemind-image-fout.txt")
                    return
                self.img_msg = "Afbeelding genereren..."
                out = os.path.join(output_dir(),
                                   "beeld-%s.png" % _t.strftime("%Y%m%d-%H%M%S"))
                self.imagegen.generate(prompt, out, negative_prompt=(neg or None),
                                       should_cancel=lambda: self.img_cancel)
                self.img_path = out
                self.img_msg = ""
                prune_outputs(12)     # alleen de laatste ~12 bewaren (geen opstapeling)
            except Exception as e:
                if "CANCELLED" in str(e):
                    self.img_msg = "Geannuleerd."
                else:
                    self.img_msg = ("Mislukt: %s. Tip: kies een SD 1.5-model; SDXL is "
                                    "te zwaar voor deze kaart." % str(e)[:80])
            finally:
                self.img_busy = False
        threading.Thread(target=work, daemon=True).start()

    def _translate_prompt(self):
        """Vertaal het promptvak naar het Engels (via het lokale taalmodel) en zet
        het resultaat terug in het vak. Engels geeft betere beelden."""
        txt = self.img_prompt.strip()
        if not txt or self.img_busy or self.img_tr_busy:
            return
        self.img_tr_busy = True
        self.img_msg = "Prompt vertalen naar Engels..."

        def work():
            try:
                out = self.brain._post([
                    {"role": "system", "content":
                     "Translate the user's text to English. It is an image-generation "
                     "prompt. Reply with ONLY the English translation - no quotes, no "
                     "explanation, keep it concise."},
                    {"role": "user", "content": txt}])
                out = (out or "").strip().strip('"').strip()
                if out:
                    self.img_prompt = out
                    if self.img_focus_field == "prompt":
                        self.caret = len(out)
                    self.img_msg = ""
                else:
                    self.img_msg = "Vertalen mislukt."
            except Exception:
                self.img_msg = ("Vertalen mislukt - is er een taalmodel geladen? "
                                "(kies er een bij 'Modellen')")
            finally:
                self.img_tr_busy = False
        threading.Thread(target=work, daemon=True).start()

    def _img_save(self):
        if not self.img_path or not os.path.isfile(self.img_path):
            return
        dest = None
        try:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            dest = filedialog.asksaveasfilename(
                defaultextension=".png",
                initialfile=os.path.basename(self.img_path),
                filetypes=[("PNG-afbeelding", "*.png")])
            root.destroy()
        except Exception:
            dest = None
        if dest:
            try:
                import shutil
                shutil.copyfile(self.img_path, dest)
                self.img_msg = "Opgeslagen: " + os.path.basename(dest)
            except Exception:
                self.img_msg = "Opslaan mislukt."

    # ---- beeld (beschrijven / vragen) ----
    def _desc_pick(self):
        path = None
        try:
            import tkinter as tk
            from tkinter import filedialog
            root = tk.Tk()
            root.withdraw()
            root.attributes("-topmost", True)
            path = filedialog.askopenfilename(filetypes=[
                ("Afbeeldingen", "*.png *.jpg *.jpeg *.bmp *.gif *.webp"),
                ("Alle bestanden", "*.*")])
            root.destroy()
        except Exception:
            path = None
        if path:
            self.desc_path = path
            self.desc_text = ""
            self._desc_loaded = None

    def _to_dutch(self, text):
        text = (text or "").strip()
        if not text:
            return "(geen beschrijving)"
        try:
            if self.brain.local and self.brain.local.model_present():
                msgs = [{"role": "system", "content":
                         "Je bent een vertaler. Antwoord uitsluitend met de "
                         "Nederlandse vertaling, zonder uitleg of aanhalingstekens."},
                        {"role": "user", "content":
                         "Vertaal naar natuurlijk Nederlands: " + text}]
                nl = self.brain.local.chat(msgs)
                if nl:
                    return nl.strip()
        except Exception:
            pass
        return text + "  (Engels; kies een taalmodel voor automatische vertaling)"

    def _desc_caption(self):
        if not self.desc_path or self.desc_busy:
            return
        self.desc_busy = True
        self.desc_text = "Bezig met beschrijven... (eerste keer downloadt het model)"

        def work():
            try:
                cap = self.describer.caption(self.desc_path)
                self.desc_text = self._to_dutch(cap)
            except Exception:
                self.desc_text = ("Mislukt. Draai eerst Installeer-Beeld-AI.bat. "
                                  "Details: DraveMind-data\\dravemind-beschrijf-fout.txt")
            finally:
                self.desc_busy = False
        threading.Thread(target=work, daemon=True).start()

    def _desc_ask(self):
        q = self.desc_q.strip()
        if not self.desc_path or not q or self.desc_busy:
            return
        self.desc_busy = True
        self.desc_text = "Bezig met antwoorden..."

        def work():
            try:
                ans = self.describer.answer(self.desc_path, q)
                self.desc_text = self._to_dutch(ans)
            except Exception:
                self.desc_text = ("Mislukt. Draai eerst Installeer-Beeld-AI.bat. "
                                  "Details: DraveMind-data\\dravemind-beschrijf-fout.txt")
            finally:
                self.desc_busy = False
        threading.Thread(target=work, daemon=True).start()

    # --- tekstcursor: één generieke editor voor alle invoervakken ---
    _FIELD_ATTR = {
        "chat": "input", "hf": "hf_query", "img": "img_prompt",
        "imgneg": "img_neg", "descq": "desc_q", "imghf": "img_hf_query",
    }

    def _focus_attr(self):
        """Naam van het attribuut dat het actieve tekstveld bevat (of None)."""
        if self.screen_name == "memory":
            return "instructions"
        return self._FIELD_ATTR.get(self._focused_field())

    def _set_caret_end(self):
        """Zet de cursor aan het eind van het actieve veld (bij wisselen van veld)."""
        a = self._focus_attr()
        self.caret = len(getattr(self, a)) if a else 0

    @staticmethod
    def _word_left(text, c):
        i = c
        while i > 0 and text[i - 1] == " ":
            i -= 1
        while i > 0 and text[i - 1] != " ":
            i -= 1
        return i

    @staticmethod
    def _word_right(text, c):
        n = len(text)
        i = c
        while i < n and text[i] != " ":
            i += 1
        while i < n and text[i] == " ":
            i += 1
        return i

    @staticmethod
    def _wrap_pos(text, font, maxw):
        """Breek tekst af zoals wrap_text, maar BEHOUD spaties en geef per regel
        de start-index in de oorspronkelijke tekst terug. Zo loopt de cursor wel
        mee bij een spatie (anders lijkt de spatiebalk niets te doen)."""
        out = []                       # (regeltekst, startindex)
        pos = 0
        for para in text.split("\n"):
            words = para.split(" ")
            line = ""
            line_start = pos
            idx = pos
            for wi, w in enumerate(words):
                piece = w if wi == len(words) - 1 else w + " "
                cand = line + piece
                if line and font.size(cand.rstrip())[0] > maxw:
                    out.append((line, line_start))
                    line = piece
                    line_start = idx
                else:
                    line = cand
                idx += len(w) + 1      # woord + scheidingsspatie
            out.append((line, line_start))
            pos = idx                  # idx telt ook de \n mee
        return out or [("", 0)]

    def _caret_line_x(self, lines, font, caret):
        """Welke regel + x-pixel hoort bij cursorpositie 'caret'?"""
        c = max(0, caret)
        cline, cx = 0, 0
        for li, (ln, st) in enumerate(lines):
            if st <= c:
                cline = li
                cx = font.size(ln[:max(0, c - st)])[0]
            else:
                break
        return cline, cx

    def _textinput(self, text):
        """Getypte tekens (pygame TEXTINPUT) - betrouwbaarder dan KEYDOWN.unicode."""
        if not text or self.show_help:
            return
        a = self._focus_attr()
        if not a:
            return
        cur = getattr(self, a)
        c = max(0, min(self.caret, len(cur)))
        setattr(self, a, cur[:c] + text + cur[c:])
        self.caret = c + len(text)

    def _keydown(self, e):
        # snelgids-overlay heeft voorrang
        if e.key == pygame.K_F1:
            self.show_help = not self.show_help
            return
        if self.show_help:
            if e.key == pygame.K_ESCAPE:
                self.show_help = False
            return
        if e.key == pygame.K_ESCAPE:
            if self.screen_name == "memory":
                self._save_instructions()
                self.screen_name = "chat"
                self._set_caret_end()
            elif self.screen_name != "chat":
                self.screen_name = "chat"
                self._set_caret_end()
            else:
                self.running = False
            return
        if self.screen_name == "settings":
            self._settings_key(e)
            return
        a = self._focus_attr()
        if a is None:
            return
        text = getattr(self, a)
        c = max(0, min(self.caret, len(text)))
        shift = bool(e.mod & pygame.KMOD_SHIFT)
        ctrl = bool(e.mod & pygame.KMOD_CTRL)
        if e.key == pygame.K_RETURN:
            # 'instructions' en multiline-velden: Shift+Enter (of in geheugen: Enter)
            # = nieuwe regel; anders de actie van dat veld uitvoeren.
            if a == "instructions" or (shift and a in ("input", "img_prompt",
                                                       "img_neg", "desc_q")):
                setattr(self, a, text[:c] + "\n" + text[c:])
                self.caret = c + 1
            elif a == "input":
                self._send(self.input)
                self.input = ""
                self.caret = 0
            elif a == "img_prompt" or a == "img_neg":
                self._img_generate()
            elif a == "desc_q":
                self._desc_ask()
            elif a == "hf_query":
                self._hf_search()
            elif a == "img_hf_query":
                self._img_hf_search()
            return
        if e.key == pygame.K_BACKSPACE:
            if c > 0:
                setattr(self, a, text[:c - 1] + text[c:])
                self.caret = c - 1
            return
        if e.key == pygame.K_DELETE:
            if c < len(text):
                setattr(self, a, text[:c] + text[c + 1:])
                self.caret = c
            return
        if e.key == pygame.K_LEFT:
            self.caret = self._word_left(text, c) if ctrl else max(0, c - 1)
            return
        if e.key == pygame.K_RIGHT:
            self.caret = self._word_right(text, c) if ctrl else min(len(text), c + 1)
            return
        if e.key == pygame.K_HOME:
            self.caret = 0
            return
        if e.key == pygame.K_END:
            self.caret = len(text)
            return

    def _click(self, pos):
        for rect, act in self.zones:
            if rect.collidepoint(pos):
                self._do(act)
                return

    def _do(self, act):
        kind = act[0]
        if kind == "screen":
            # verlaat je de Geheugen-tab, bewaar dan eerst je richtlijnen
            if self.screen_name == "memory" and act[1] != "memory":
                self._save_instructions()
            self.screen_name = act[1]
            if act[1] == "models":
                self.hf_focus = False
            self._set_caret_end()
        elif kind == "send":
            self._send(self.input)
            self.input = ""
            self.caret = 0
        elif kind == "mic":
            self._toggle_mic()
        elif kind == "speak_toggle":
            self.speak_answers = not self.speak_answers
            self.cfg["speak_answers"] = self.speak_answers
            save_config(self.cfg)
        elif kind == "model_pick":
            m = modelreg.CURATED[act[1]]
            self._set_model(m["repo"], m["file"])
            self.screen_name = "chat"
        elif kind == "hf_focus":
            self.hf_focus = True
            self.caret = len(self.hf_query)
        elif kind == "hf_search":
            self._hf_search()
        elif kind == "hf_repo":
            self._hf_open_repo(act[1])
        elif kind == "hf_back":
            self.hf_repo = ""
            self.hf_files = []
            self.mm_scroll = 0
        elif kind == "hf_pick":
            self._set_model(self.hf_repo, act[1])
            self.screen_name = "chat"
        elif kind == "help":
            self.show_help = True
        elif kind == "help_close":
            self.show_help = False
        elif kind == "donate":
            try:
                webbrowser.open(DONATE_URL)
            except Exception:
                pass
        elif kind == "install_beeld":
            self._install_beeld()
        elif kind == "install_beeld_cuda":
            self._install_beeld(force_cuda=True)
        elif kind == "img_gen":
            self._img_generate()
        elif kind == "img_translate":
            self._translate_prompt()
        elif kind == "img_focus_prompt":
            self.img_focus_field = "prompt"
            self.caret = len(self.img_prompt)
        elif kind == "img_focus_neg":
            self.img_focus_field = "neg"
            self.caret = len(self.img_neg)
        elif kind == "img_cancel":
            self.img_cancel = True
            self.img_msg = "Annuleren..."
        elif kind == "img_save":
            self._img_save()
        elif kind == "img_mode":
            self.img_mode = act[1]
            self._set_caret_end()
        elif kind == "desc_pick":
            self._desc_pick()
        elif kind == "desc_caption":
            self._desc_caption()
        elif kind == "desc_ask":
            self._desc_ask()
        elif kind == "imghf_focus":
            self.img_hf_focus = True
            self.caret = len(self.img_hf_query)
        elif kind == "imghf_search":
            self._img_hf_search()
        elif kind == "img_curated":
            self._set_image_model(modelreg.IMAGE_CURATED[act[1]]["repo"])
        elif kind == "img_pick":
            self._set_image_model(act[1])
        elif kind == "img_own":
            self._set_image_model(act[1])           # eigen model uit de map
        elif kind == "img_pick_file":
            self._pick_image_model()
        elif kind == "open_eigen_map":
            try:
                os.startfile(eigen_models_dir())
            except Exception:
                pass
        elif kind == "open_output_map":
            try:
                os.startfile(output_dir())
            except Exception:
                pass
        elif kind == "img_size":
            self.size_idx = (self.size_idx + act[1]) % len(SIZE_PRESETS)
            w, h = SIZE_PRESETS[self.size_idx]
            self.imagegen.width, self.imagegen.height = w, h
            self.cfg["image_width"], self.cfg["image_height"] = w, h
            save_config(self.cfg)
        elif kind == "img_steps":
            self.imagegen.steps = max(2, min(50, self.imagegen.steps + act[1]))
            self.cfg["image_steps"] = self.imagegen.steps
            save_config(self.cfg)
        elif kind == "set_adj":
            self.set_idx = act[1]
            self._settings_adjust(act[2])
        elif kind == "newchat":
            self.brain.reset()
            self.msgs = [("ai", "Nieuw gesprek gestart.")]
            self.scroll = 0
        elif kind == "pick_file":
            self._pick_file()
        elif kind == "rm_attach":
            self.attached = None
        elif kind == "save_chat":
            self._save_chat()
        elif kind == "mem_back":
            self._save_instructions()
            self.screen_name = "chat"
        elif kind == "forget_facts":
            if self.memory:
                self.memory.forget_all()
            self._add("ai", "Geleerde weetjes gewist. Je vaste richtlijnen blijven staan.")
        elif kind == "del_fact":
            if self.memory:
                self.memory.delete_fact(act[1])

    # ---------- instellingen ----------
    def _settings_key(self, e):
        if e.key in (pygame.K_UP, pygame.K_w):
            self.set_idx = (self.set_idx - 1) % 6
        elif e.key in (pygame.K_DOWN, pygame.K_s):
            self.set_idx = (self.set_idx + 1) % 6
        elif e.key in (pygame.K_LEFT, pygame.K_a):
            self._settings_adjust(-1)
        elif e.key in (pygame.K_RIGHT, pygame.K_d):
            self._settings_adjust(1)

    def _settings_adjust(self, d):
        i = self.set_idx
        if i == 0:
            vs = self.voice.list_voices()
            if vs:
                try:
                    cur = vs.index(self.voice.voice)
                except ValueError:
                    cur = 0
                self.voice.set_voice(vs[(cur + d) % len(vs)])
        elif i == 1:
            self.voice.speed = round(min(1.6, max(0.6, self.voice.speed + 0.05 * d)), 2)
        elif i == 2:
            self.voice.pitch = round(min(1.3, max(0.8, self.voice.pitch + 0.05 * d)), 2)
        elif i == 3:
            self.voice.volume = round(min(1.0, max(0.0, self.voice.volume + 0.1 * d)), 2)
        elif i == 4:
            self.speak_answers = not self.speak_answers
        elif i == 5:
            scales = [1.0, 1.25, 1.5]
            try:
                idx = scales.index(round(self.ui_scale, 2))
            except ValueError:
                idx = 0
            self.ui_scale = scales[(idx + d) % len(scales)]
            self._build_fonts()
            self.cfg["ui_scale"] = self.ui_scale
        self._save_voice_cfg()

    def _save_instructions(self):
        self.cfg["instructions"] = self.instructions
        save_config(self.cfg)
        self.brain.instructions = self.instructions

    def _save_voice_cfg(self):
        self.cfg.update({"voice_name": self.voice.voice, "voice_speed": self.voice.speed,
                         "voice_pitch": self.voice.pitch, "voice_volume": self.voice.volume,
                         "speak_answers": self.speak_answers})
        save_config(self.cfg)

    # ---------- tekenen ----------
    def _zone(self, rect, act):
        self.zones.append((rect, act))

    def _btn(self, rect, label, font, fg=TEXT, border=LINE, fill=PANEL):
        pygame.draw.rect(self.screen, fill, rect, border_radius=8)
        pygame.draw.rect(self.screen, border, rect, width=2, border_radius=8)
        img = font.render(label, True, fg)
        self.screen.blit(img, img.get_rect(center=rect.center))

    def _bar(self, x, y, w, t, h=10):
        """Animerende (indeterminate) voortgangsbalk voor 'bezig'-acties."""
        s = self.screen
        track = pygame.Rect(x, y, w, h)
        pygame.draw.rect(s, PANEL, track, border_radius=h // 2)
        pygame.draw.rect(s, LINE, track, width=1, border_radius=h // 2)
        seg = max(40, int(w * 0.3))
        phase = (t * 0.7) % 2.0
        if phase > 1.0:
            phase = 2.0 - phase           # heen en weer
        px = x + int((w - seg) * phase)
        pygame.draw.rect(s, ACCENT, (px, y, seg, h), border_radius=h // 2)

    def _draw(self, t):
        self.zones = []
        self.screen.fill(BG)
        self._topbar()
        if self.screen_name == "chat":
            self._draw_chat(t)
        elif self.screen_name == "models":
            self._draw_models(t)
        elif self.screen_name == "memory":
            self._draw_memory(t)
        elif self.screen_name == "image":
            self._draw_image(t)
        elif self.screen_name == "settings":
            self._draw_settings()
        if self.show_help:
            self._draw_help(t)

    def _draw_help(self, t):
        s = self.screen
        ov = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        ov.fill((0, 0, 0, 215))
        s.blit(ov, (0, 0))
        self.zones = []          # alleen de gids is nu klikbaar
        s.blit(self.f_title.render("Snelgids - DraveAI", True, ACCENT), (40, 40))
        lines = [
            "Typ onderaan je bericht en druk Enter (of klik Stuur).",
            "Mic: klik om in te spreken, nog eens om te stoppen.",
            "Stem: aan/uit zet gesproken antwoorden aan of uit.",
            "Bestand: stuur een tekst/PDF mee; Bewaar: sla het gesprek op.",
            "Modellen: kies/download een taalmodel (chat).",
            "Beeld: maak of beschrijf afbeeldingen (knop 'Model' voor beeldmodel).",
            "Geheugen: schrijf vaste richtlijnen + beheer onthouden weetjes.",
            "Hernoemen: 'ik noem je X'. Je naam: 'ik heet X'.",
            "Instellingen: stem, snelheid, toonhoogte, volume.",
            "F1 = deze gids aan/uit. Esc = terug/sluiten.",
        ]
        y = 96
        for ln in lines:
            s.blit(self.f.render("- " + ln, True, TEXT), (44, y))
            y += 30
        y += 10
        s.blit(self.fs.render("Bevalt DraveAI? Steun de ontwikkeling met een "
                              "kleine donatie - dank je wel!", True, MUTE), (44, y))
        y += 30
        dr = pygame.Rect(44, y, 250, 46)
        self._btn(dr, "Doneer via PayPal", self.f, fg=GREEN, border=GREEN)
        self._zone(dr, ("donate",))
        s.blit(self.fs.render("Contact: " + CONTACT_EMAIL, True, MUTE), (dr.right + 24, y + 14))
        cl = pygame.Rect(WIDTH - 160, HEIGHT - 64, 130, 44)
        self._btn(cl, "Sluiten", self.f, fg=ACCENT)
        self._zone(cl, ("help_close",))

    def _topbar(self):
        s = self.screen
        pygame.draw.rect(s, BAR, (0, 0, WIDTH, 50))
        s.blit(self.f_bartitle.render("DraveAI", True, ACCENT), (16, 12))
        # altijd zichtbaar links: Gids + Doneer (geen sneltoetsen nodig)
        gx = 168
        for label, act, col in (("Gids", ("help",), ACCENT),
                                ("Doneer", ("donate",), GREEN)):
            w = self.f_bar.size(label)[0] + 16
            r = pygame.Rect(gx, 8, w, 34)
            self._btn(r, label, self.f_bar, fg=col, border=col)
            self._zone(r, act)
            gx += w + 8
        # knoppen rechtsboven (compact) - tabs + chat-acties
        x = WIDTH - 12
        for label, act in (("Instellingen", ("screen", "settings")),
                           ("Geheugen", ("screen", "memory")),
                           ("Modellen", ("screen", "models")),
                           ("Beeld", ("screen", "image")),
                           ("Bewaar", ("save_chat",)),
                           ("Nieuw", ("newchat",))):
            w = self.f_bar.size(label)[0] + 14
            r = pygame.Rect(x - w, 8, w, 34)
            act_screen = (act[0] == "screen" and act[1] == self.screen_name)
            self._btn(r, label, self.f_bar, fg=ACCENT if act_screen else TEXT,
                      border=ACCENT if act_screen else LINE)
            self._zone(r, act)
            x -= w + 6
        sp = "Stem: aan" if self.speak_answers else "Stem: uit"
        w = self.f_bar.size(sp)[0] + 14
        r = pygame.Rect(x - w, 8, w, 34)
        self._btn(r, sp, self.f_bar, fg=GREEN if self.speak_answers else MUTE)
        self._zone(r, ("speak_toggle",))

    def _draw_chat(self, t):
        s = self.screen
        top = 60
        line_h_in = self.fi.get_height() + 2
        input_h = line_h_in * 3 + 14          # 3 regels, meerregelig
        input_y = HEIGHT - input_h - 14
        status_y = input_y - (self.fs.get_height() + 6)
        area_h = status_y - top - 6
        maxw = WIDTH - 60
        # alle regels opbouwen
        flat = []
        for role, text in self.msgs:
            who = ("Jij: " if role == "user"
                   else (self.brain.assistant_name or "DraveAI") + ": ")
            col = USERCOL if role == "user" else AICOL
            for ln in wrap_text(who + text, self.f, maxw):
                flat.append((col, ln))
            flat.append((None, ""))  # lege regel tussen berichten
        line_h = self.f.get_height() + 4
        vis = max(1, area_h // line_h)
        self.scroll = max(0, min(self.scroll, max(0, len(flat) - vis)))
        start = max(0, len(flat) - vis - self.scroll)
        end = min(len(flat), start + vis)
        y = top
        for col, ln in flat[start:end]:
            if col and ln:
                s.blit(self.f.render(ln, True, col), (24, y))
            y += line_h
        # statusregel (+ bijlage-indicator)
        if self.attached:
            name, content = self.attached
            txt = "Bijlage: %s (%d tekens)   [X = verwijderen]" % (name, len(content))
            r = self._draw_text(s, txt, self.fs, GREEN, 24, status_y)
            self._zone(r, ("rm_attach",))
        else:
            labels = {"idle": "", "thinking": "Denken...", "searching": "Online zoeken...",
                      "listening": "Luisteren... (klik mic om te stoppen)",
                      "speaking": "Spreken..."}
            msg = self.load_msg or labels.get(self.state, "")
            if msg:
                s.blit(self.fs.render(msg, True, AMBER), (24, status_y))
        # voortgangsbalk bovenaan bij lange acties (model laden/denken/zoeken)
        if self.loading or self.state in ("thinking", "searching"):
            self._bar(16, 54, WIDTH - 32, t, h=5)
        # knoppen rechts: [Bestand] [Mic] [Stuur] (ruim, hoogte = invoervak)
        sendr = pygame.Rect(WIDTH - 16 - 110, input_y, 110, input_h)
        micr = pygame.Rect(sendr.x - 8 - 90, input_y, 90, input_h)
        filer = pygame.Rect(micr.x - 8 - 120, input_y, 120, input_h)
        # meerregelig invoervak (vult de rest links)
        box = pygame.Rect(16, input_y, filer.x - 8 - 16, input_h)
        self._draw_input_box(box, self.input,
                             "Typ een bericht... (Enter = sturen, Shift+Enter = nieuwe regel)", t)
        self._btn(filer, "Bestand", self.fs, fg=ACCENT)
        self._zone(filer, ("pick_file",))
        self._btn(micr, "Mic", self.fs,
                  fg=RED if self.recording else (GREEN if self.ears.available() else MUTE))
        self._zone(micr, ("mic",))
        self._btn(sendr, "Stuur", self.fs, fg=ACCENT)
        self._zone(sendr, ("send",))

    def _draw_text(self, surf, txt, font, color, x, y):
        img = font.render(txt, True, color)
        surf.blit(img, (x, y))
        return pygame.Rect(x, y, img.get_width(), img.get_height())

    def _draw_models(self, t=0.0):
        s = self.screen
        s.blit(self.f_title.render("Modellen", True, ACCENT), (24, 60))
        # --- snelkeuze (vaste lijst) ---
        s.blit(self.fs.render("Snelkeuze:", True, MUTE), (24, 100))
        y = 122
        for i, m in enumerate(modelreg.CURATED):
            r = pygame.Rect(24, y, WIDTH - 48, 40)
            active = self.cfg.get("file") == m["file"]
            present = self.brain.local is not None and self.brain.local.model_present(file=m["file"])
            pygame.draw.rect(s, (34, 44, 38) if active else PANEL, r, border_radius=8)
            pygame.draw.rect(s, GREEN if active else LINE, r, width=2, border_radius=8)
            s.blit(self.fs.render(m["name"], True, TEXT), (r.x + 12, r.y + 5))
            tag = "actief" if active else ("gedownload" if present else "download")
            s.blit(self.fs.render("%s  -  %s" % (m["size"], tag), True, MUTE), (r.x + 12, r.y + 22))
            self._zone(r, ("model_pick", i))
            y += 44
        # --- HuggingFace zoeken (taalmodellen) ---
        y += 8
        s.blit(self.fs.render("Zoek op HuggingFace (GGUF) - bv. 'llama 8b', 'phi', "
                              "'mistral':", True, MUTE), (24, y))
        y += 26
        fld = pygame.Rect(24, y, WIDTH - 24 - 130 - 16, 38)
        self._field(fld, (self.hf_query or "typ een zoekterm..."), self.hf_focus,
                    bool(self.hf_query), t)
        self._zone(fld, ("hf_focus",))
        zr = pygame.Rect(fld.right + 12, y, 118, 38)
        self._btn(zr, "Zoek", self.fs, fg=ACCENT)
        self._zone(zr, ("hf_search",))
        y += 48
        # --- resultaten / bestanden (scrolbaar met muiswiel) ---
        list_top = y
        list_bottom = HEIGHT - 64
        row_h = 30
        if self.hf_msg:
            s.blit(self.fs.render(self.hf_msg, True, AMBER), (24, list_top))
        if self.hf_repo:
            # bestanden in de gekozen repo
            br2 = pygame.Rect(24, list_top, 120, 28)
            self._btn(br2, "< terug", self.fs)
            self._zone(br2, ("hf_back",))
            s.blit(self.fs.render(self.hf_repo, True, TEXT), (156, list_top + 4))
            yy = list_top + 36
            items = self.hf_files
            kind = "hf_pick"
        else:
            yy = list_top + (24 if self.hf_msg else 0)
            items = self.hf_results
            kind = "hf_repo"
        maxrows = max(1, (list_bottom - yy) // row_h)
        self.mm_scroll = max(0, min(self.mm_scroll, max(0, len(items) - maxrows)))
        for it in items[self.mm_scroll:self.mm_scroll + maxrows]:
            r = pygame.Rect(24, yy, WIDTH - 48, row_h - 4)
            pygame.draw.rect(s, PANEL, r, border_radius=6)
            pygame.draw.rect(s, LINE, r, width=1, border_radius=6)
            label = it if self.fs.size(it)[0] < WIDTH - 80 else it[:78] + "..."
            s.blit(self.fs.render(label, True, TEXT), (r.x + 10, r.y + 3))
            self._zone(r, (kind, it))
            yy += row_h
        if len(items) > maxrows:
            s.blit(self.fs.render("(muiswiel om te scrollen)", True, MUTE), (WIDTH - 240, list_bottom + 2))
        # terug + statusmelding
        br = pygame.Rect(WIDTH - 140, HEIGHT - 56, 120, 40)
        self._btn(br, "Terug", self.fs)
        self._zone(br, ("screen", "chat"))
        if self.load_msg:
            s.blit(self.fs.render(self.load_msg, True, AMBER), (24, HEIGHT - 48))
        if self.loading or self.hf_busy:
            self._bar(24, HEIGHT - 30, WIDTH - 180, t, h=8)

    def _field(self, rect, text, focus, filled, t=None):
        s = self.screen
        pygame.draw.rect(s, PANEL, rect, border_radius=6)
        pygame.draw.rect(s, ACCENT if focus else LINE, rect, width=2, border_radius=6)
        f = self.fi
        cw = f.size("|")[0]
        # tekst die niet past: toon het rechter (laatste) deel. We reserveren altijd
        # ruimte voor de cursor, zodat de tekst NIET heen en weer schuift bij knipperen.
        shown = text
        while shown and f.size(shown)[0] > rect.w - 16 - cw and len(shown) > 1:
            shown = shown[1:]
        ty = rect.y + (rect.h - f.get_height()) // 2
        s.blit(f.render(shown, True, TEXT if filled else MUTE), (rect.x + 10, ty))
        if focus and t is not None and (t % 1.0) < 0.5:
            c = max(0, min(self.caret, len(text)))
            ci = max(0, c - (len(text) - len(shown)))   # cursor binnen het zichtbare deel
            cx = rect.x + 10 + f.size(shown[:ci])[0]
            pygame.draw.line(s, TEXT, (cx, ty), (cx, ty + f.get_height()), 2)

    def _draw_input_box(self, box, text, placeholder, t, focused=True):
        """Groot, MEERREGELIG invoervak (toegankelijk). Tekst loopt door op
        nieuwe regels; de laatste regels worden getoond met een knipperende cursor.
        focused: dik gekleurde rand + knipperende cursor alleen in het actieve vak."""
        s = self.screen
        f = self.fi
        pygame.draw.rect(s, PANEL, box, border_radius=8)
        pygame.draw.rect(s, ACCENT if focused else LINE, box, width=2, border_radius=8)
        line_h = f.get_height() + 2
        rows = max(1, (box.h - 12) // line_h)
        blink = focused and (t % 1.0) < 0.5
        if text:
            # afbreken mét behoud van spaties (cursor loopt zo netjes mee)
            lines = self._wrap_pos(text, f, box.w - 20)
            cline, cx = 0, 0
            if focused:
                cline, cx = self._caret_line_x(
                    lines, f, max(0, min(self.caret, len(text))))
            # zichtbaar venster: laatste 'rows' regels, maar houd de cursor in beeld
            start = max(0, len(lines) - rows)
            if focused and cline < start:
                start = cline
            for i, (ln, _st) in enumerate(lines[start:start + rows]):
                s.blit(f.render(ln, True, TEXT), (box.x + 10, box.y + 8 + i * line_h))
            if blink and start <= cline < start + rows:
                cy = box.y + 8 + (cline - start) * line_h
                pygame.draw.line(s, TEXT, (box.x + 10 + cx, cy),
                                 (box.x + 10 + cx, cy + f.get_height()), 2)
        else:
            wrapped = wrap_text(placeholder, f, box.w - 20)[:rows] or [""]
            for i, ln in enumerate(wrapped):
                s.blit(f.render(ln, True, MUTE), (box.x + 10, box.y + 8 + i * line_h))
            if blink:
                cy = box.y + 8
                pygame.draw.line(s, TEXT, (box.x + 10, cy),
                                 (box.x + 10, cy + f.get_height()), 2)

    def _draw_memory(self, t):
        s = self.screen
        s.blit(self.f_title.render("Geheugen", True, ACCENT), (24, 60))
        # --- 1) vaste richtlijnen (bewerkbaar tekstveld) ---
        s.blit(self.fs.render("Vaste richtlijnen - wat ik wel/niet mag, voorkeuren, stijl "
                              "(Enter = nieuwe regel):", True, MUTE), (24, 96))
        box = pygame.Rect(24, 120, WIDTH - 48, 168)
        pygame.draw.rect(s, PANEL, box, border_radius=8)
        pygame.draw.rect(s, ACCENT, box, width=2, border_radius=8)
        f = self.f
        line_h = f.get_height() + 4
        vis = max(1, (box.h - 16) // line_h)
        lines = self._wrap_pos(self.instructions, f, box.w - 20)
        cline, cx = self._caret_line_x(
            lines, f, max(0, min(self.caret, len(self.instructions))))
        start = max(0, len(lines) - vis)
        if cline < start:
            start = cline
        for i, (ln, _st) in enumerate(lines[start:start + vis]):
            s.blit(f.render(ln, True, TEXT), (box.x + 10, box.y + 8 + i * line_h))
        if (t % 1.0) < 0.5 and start <= cline < start + vis:
            cy = box.y + 8 + (cline - start) * line_h
            pygame.draw.line(s, TEXT, (box.x + 10 + cx, cy),
                             (box.x + 10 + cx, cy + f.get_height()), 2)
        # --- 2) opgeslagen weetjes (per stuk verwijderen) ---
        s.blit(self.fs.render("Onthouden weetjes (klik op X om te verwijderen):",
                              True, MUTE), (24, 300))
        facts = self.memory.list_facts() if self.memory else []
        ly = 326
        bottom = HEIGHT - 70
        if not facts:
            s.blit(self.fs.render("(nog niets onthouden)", True, MUTE), (40, ly))
        for rowid, txt in facts:
            if ly > bottom - 30:
                s.blit(self.fs.render("...en meer", True, MUTE), (40, ly))
                break
            xr = pygame.Rect(24, ly, 30, 26)
            self._btn(xr, "X", self.fs, fg=RED)
            self._zone(xr, ("del_fact", rowid))
            line = txt if self.fs.size(txt)[0] < WIDTH - 90 else txt[:90] + "..."
            s.blit(self.fs.render(line, True, TEXT), (64, ly + 3))
            ly += 32
        # --- knoppen onderaan ---
        fr = pygame.Rect(24, HEIGHT - 58, 210, 42)
        self._btn(fr, "Wis ALLE weetjes", self.fs, fg=RED)
        self._zone(fr, ("forget_facts",))
        br = pygame.Rect(WIDTH - 200, HEIGHT - 58, 176, 42)
        self._btn(br, "Opslaan & terug", self.fs, fg=GREEN)
        self._zone(br, ("mem_back",))

    def _draw_image(self, t):
        s = self.screen
        s.blit(self.f_title.render("Beeld", True, ACCENT), (24, 58))
        mk = pygame.Rect(150, 60, 100, 34)
        ds = pygame.Rect(256, 60, 130, 34)
        mo = pygame.Rect(392, 60, 100, 34)
        self._btn(mk, "Maken", self.fs,
                  fg=ACCENT if self.img_mode == "make" else TEXT,
                  border=ACCENT if self.img_mode == "make" else LINE)
        self._btn(ds, "Beschrijven", self.fs,
                  fg=ACCENT if self.img_mode == "describe" else TEXT,
                  border=ACCENT if self.img_mode == "describe" else LINE)
        self._btn(mo, "Model", self.fs,
                  fg=ACCENT if self.img_mode == "model" else TEXT,
                  border=ACCENT if self.img_mode == "model" else LINE)
        self._zone(mk, ("img_mode", "make"))
        self._zone(ds, ("img_mode", "describe"))
        self._zone(mo, ("img_mode", "model"))
        if self.img_mode == "make":
            self._draw_image_make(t)
        elif self.img_mode == "describe":
            self._draw_image_describe(t)
        else:
            self._draw_image_model(t)

    def _draw_install_in_rect(self, area, t=0.0):
        """Toon een installatie-uitnodiging voor de beeld-AI midden in een vlak."""
        s = self.screen
        cx = area.centerx
        if self.img_install_busy:
            im = self.fs.render("Beeld-AI installeren... eenmalig ~2,7 GB. "
                                "Balk beweegt = bezig.", True, AMBER)
            s.blit(im, im.get_rect(center=(cx, area.centery - 24)))
            self._bar(cx - 150, area.centery, 300, t, h=10)
            for ln in wrap_text(self.img_install_msg, self.fs, area.w - 40)[:1]:
                l = self.fs.render(ln, True, MUTE)
                s.blit(l, l.get_rect(center=(cx, area.centery + 22)))
        else:
            im = self.fs.render("Beeld-AI is nog niet geinstalleerd (eenmalig, "
                                "paar GB - de app doet het zelf).", True, TEXT)
            s.blit(im, im.get_rect(center=(cx, area.centery - 30)))
            if self.img_install_msg:
                for ln in wrap_text(self.img_install_msg, self.fs, area.w - 40)[:1]:
                    l = self.fs.render(ln, True, MUTE)
                    s.blit(l, l.get_rect(center=(cx, area.centery - 6)))
            btn = pygame.Rect(0, 0, 240, 42)
            btn.center = (cx, area.centery + 28)
            self._btn(btn, "Beeld-AI installeren", self.fs, fg=GREEN)
            self._zone(btn, ("install_beeld",))

    def _draw_image_make(self, t):
        s = self.screen
        LW = 560                       # breedte van de linkerkolom (langere tekstvakken)
        # ===== LINKS: info + instellingen + tekstvakken + knoppen =====
        dev = self.imagegen.device_label()
        dev_col = GREEN if self.imagegen._cuda else (AMBER if self.imagegen._cuda is False else MUTE)
        mid = self.imagegen.model_id or ""
        mid_disp = os.path.basename(mid) if ("\\" in mid or "/" in mid) else mid
        mlabel = "Model: " + mid_disp
        while self.fs.size(mlabel)[0] > LW and len(mlabel) > 12:
            mlabel = mlabel[:-2]
        s.blit(self.fs.render(mlabel, True, MUTE), (24, 92))
        s.blit(self.fs.render("Rekent op: %s" % dev, True, dev_col), (24, 114))
        if (beeld_installed() and self.imagegen._cuda is False
                and not self.img_install_busy):
            gb = pygame.Rect(24, 138, 250, 30)
            self._btn(gb, "Installeer GPU (CUDA)", self.fs, fg=GREEN, border=GREEN)
            self._zone(gb, ("install_beeld_cuda",))
        # stappen
        s.blit(self.fs.render("Stappen: %d" % self.imagegen.steps, True, TEXT), (24, 180))
        sl = pygame.Rect(194, 176, 30, 28)
        sr = pygame.Rect(230, 176, 30, 28)
        self._btn(sl, "<", self.fs)
        self._btn(sr, ">", self.fs)
        self._zone(sl, ("img_steps", -2))
        self._zone(sr, ("img_steps", 2))
        # formaat
        w0, h0 = SIZE_PRESETS[self.size_idx]
        s.blit(self.fs.render("Formaat: %dx%d" % (w0, h0), True, TEXT), (24, 214))
        lb = pygame.Rect(224, 210, 30, 28)
        rb = pygame.Rect(260, 210, 30, 28)
        self._btn(lb, "<", self.fs)
        self._btn(rb, ">", self.fs)
        self._zone(lb, ("img_size", -1))
        self._zone(rb, ("img_size", 1))
        # prompt
        s.blit(self.fs.render("Beschrijf (Engels werkt het best):",
                              True, MUTE), (24, 248))
        # knop: typ in het Nederlands, vertaal met 1 klik naar Engels
        tb = pygame.Rect(24 + LW - 150, 244, 150, 26)
        self._btn(tb, "Naar Engels", self.fs,
                  fg=MUTE if self.img_tr_busy else ACCENT,
                  border=LINE if self.img_tr_busy else ACCENT)
        if not self.img_tr_busy and not self.img_busy:
            self._zone(tb, ("img_translate",))
        pph = (self.fi.get_height() + 2) * 3 + 12
        pbox = pygame.Rect(24, 272, LW, pph)
        self._draw_input_box(pbox, self.img_prompt,
                             "typ hier... (bv. een dappere dwerg-strijder, D&D, "
                             "digitale kunst)", t,
                             focused=(self.img_focus_field == "prompt"))
        self._zone(pbox, ("img_focus_prompt",))
        # negatieve prompt
        ny = pbox.bottom + 8
        s.blit(self.fs.render("Niet doen (negatief - wat je NIET wilt):",
                              True, MUTE), (24, ny))
        nph = (self.fi.get_height() + 2) * 3 + 12
        nbox = pygame.Rect(24, ny + 24, LW, nph)
        self._draw_input_box(nbox, self.img_neg,
                             "bv. lelijk, misvormd, tekst, watermerk", t,
                             focused=(self.img_focus_field == "neg"))
        self._zone(nbox, ("img_focus_neg",))
        # genereer + annuleren
        by = nbox.bottom + 12
        gr = pygame.Rect(24, by, 225, 48)
        self._btn(gr, "Genereer", self.fs,
                  fg=MUTE if self.img_busy else ACCENT,
                  border=LINE if self.img_busy else ACCENT)
        if not self.img_busy:
            self._zone(gr, ("img_gen",))
        an = pygame.Rect(269, by, 225, 48)
        self._btn(an, "Annuleren", self.fs,
                  fg=RED if self.img_busy else MUTE,
                  border=RED if self.img_busy else LINE)
        if self.img_busy:
            self._zone(an, ("img_cancel",))

        # ===== RECHTS: groot afbeeldingsvlak =====
        ax = 24 + LW + 20
        area = pygame.Rect(ax, 92, WIDTH - 24 - ax, HEIGHT - 92 - 70)
        pygame.draw.rect(s, PANEL, area, border_radius=8)
        pygame.draw.rect(s, LINE, area, width=1, border_radius=8)
        if self.img_path and self._img_loaded != self.img_path:
            try:
                self.img_surface = pygame.image.load(self.img_path).convert()
            except Exception:
                self.img_surface = None
            self._img_loaded = self.img_path
        if self.img_surface:
            iw, ih = self.img_surface.get_size()
            scale = min((area.w - 16) / iw, (area.h - 16) / ih)
            w2, h2 = max(1, int(iw * scale)), max(1, int(ih * scale))
            try:
                surf = pygame.transform.smoothscale(self.img_surface, (w2, h2))
            except Exception:
                surf = pygame.transform.scale(self.img_surface, (w2, h2))
            s.blit(surf, surf.get_rect(center=area.center))
        elif not beeld_installed() or self.img_install_busy:
            self._draw_install_in_rect(area, t)
        elif self.img_busy:
            cx, cy = area.centerx, area.centery
            yy = cy - 60
            for ln in wrap_text(self.img_msg or "Bezig...", self.fs, area.w - 80)[:3]:
                l = self.fs.render(ln, True, AMBER)
                s.blit(l, l.get_rect(center=(cx, yy)))
                yy += self.fs.get_height() + 2
            cs, ts = self.imagegen.cur_step, self.imagegen.total_steps
            bw = min(380, area.w - 60)
            bx, by2 = cx - bw // 2, cy + 14
            if ts and cs:
                track = pygame.Rect(bx, by2, bw, 14)
                pygame.draw.rect(s, PANEL, track, border_radius=7)
                pygame.draw.rect(s, LINE, track, width=1, border_radius=7)
                frac = max(0.02, min(1.0, cs / ts))
                pygame.draw.rect(s, ACCENT, (bx, by2, int(bw * frac), 14),
                                 border_radius=7)
                lbl = self.fs.render("Stap %d / %d" % (cs, ts), True, MUTE)
            else:
                self._bar(bx, by2, bw, t, h=14)
                lbl = self.fs.render("Even geduld...", True, MUTE)
            s.blit(lbl, lbl.get_rect(center=(cx, by2 + 32)))
        else:
            im = self.fs.render("Hier verschijnt je afbeelding.", True, MUTE)
            s.blit(im, im.get_rect(center=(area.centerx, area.centery - 34)))
            tip = ("Eerste afbeelding na het opstarten laadt het model in "
                   "(~10-30 sec). Daarna gaat elke volgende snel.")
            yy = area.centery
            for ln in wrap_text(tip, self.fs, area.w - 80):
                l = self.fs.render(ln, True, MUTE)
                s.blit(l, l.get_rect(center=(area.centerx, yy)))
                yy += self.fs.get_height() + 4
        # ===== onderaan: Open map (links) + Bewaar + Terug =====
        omr = pygame.Rect(24, HEIGHT - 58, 150, 42)
        self._btn(omr, "Open map", self.fs, fg=ACCENT)
        self._zone(omr, ("open_output_map",))
        if self.img_surface:
            sv = pygame.Rect(184, HEIGHT - 58, 230, 42)
            self._btn(sv, "Bewaar afbeelding", self.fs, fg=GREEN)
            self._zone(sv, ("img_save",))
        br = pygame.Rect(WIDTH - 140, HEIGHT - 56, 120, 40)
        self._btn(br, "Terug", self.fs)
        self._zone(br, ("screen", "chat"))

    def _draw_image_describe(self, t):
        s = self.screen
        s.blit(self.fs.render("Laad een afbeelding; ik beschrijf hem of beantwoord een "
                              "vraag erover (eerste keer downloadt het model).",
                              True, MUTE), (24, 100))
        pk = pygame.Rect(24, 128, 180, 38)
        self._btn(pk, "Kies afbeelding", self.fs, fg=ACCENT)
        self._zone(pk, ("desc_pick",))
        if self.desc_path:
            cb = pygame.Rect(216, 128, 150, 38)
            self._btn(cb, "Beschrijf", self.fs,
                      fg=MUTE if self.desc_busy else GREEN)
            if not self.desc_busy:
                self._zone(cb, ("desc_caption",))
            name = os.path.basename(self.desc_path)
            if self.fs.size(name)[0] > 380:
                name = name[:42] + "..."
            s.blit(self.fs.render(name, True, MUTE), (378, 138))
        # vraag-veld
        s.blit(self.fs.render("Of stel een vraag over de afbeelding (Enter):",
                              True, MUTE), (24, 176))
        fld = pygame.Rect(24, 200, WIDTH - 24 - 130 - 16, 38)
        self._field(fld, self.desc_q or "typ hier... (bv. hoeveel mensen staan er?)",
                    True, bool(self.desc_q), t)
        vb = pygame.Rect(fld.right + 12, 200, 118, 38)
        self._btn(vb, "Vraag", self.fs, fg=MUTE if self.desc_busy else ACCENT)
        if not self.desc_busy and self.desc_path:
            self._zone(vb, ("desc_ask",))
        # afbeelding links
        area = pygame.Rect(24, 250, 360, HEIGHT - 250 - 70)
        pygame.draw.rect(s, PANEL, area, border_radius=8)
        pygame.draw.rect(s, LINE, area, width=1, border_radius=8)
        if self.desc_path and self._desc_loaded != self.desc_path:
            try:
                self.desc_surface = pygame.image.load(self.desc_path).convert()
            except Exception:
                self.desc_surface = None
            self._desc_loaded = self.desc_path
        if self.desc_surface:
            iw, ih = self.desc_surface.get_size()
            scale = min((area.w - 16) / iw, (area.h - 16) / ih)
            w2, h2 = max(1, int(iw * scale)), max(1, int(ih * scale))
            try:
                surf = pygame.transform.smoothscale(self.desc_surface, (w2, h2))
            except Exception:
                surf = pygame.transform.scale(self.desc_surface, (w2, h2))
            s.blit(surf, surf.get_rect(center=area.center))
        else:
            im = self.fs.render("Nog geen afbeelding gekozen.", True, MUTE)
            s.blit(im, im.get_rect(center=area.center))
        # tekst rechts
        tx = pygame.Rect(400, 250, WIDTH - 400 - 24, HEIGHT - 250 - 70)
        pygame.draw.rect(s, PANEL, tx, border_radius=8)
        pygame.draw.rect(s, LINE, tx, width=1, border_radius=8)
        if (not beeld_installed() or self.img_install_busy) and not self.desc_text:
            self._draw_install_in_rect(tx, t)
        else:
            txt = self.desc_text or "Hier verschijnt de beschrijving of het antwoord."
            col = TEXT if self.desc_text else MUTE
            yy = tx.y + 10
            for ln in wrap_text(txt, self.f, tx.w - 20):
                if yy > tx.bottom - 24:
                    break
                s.blit(self.f.render(ln, True, col), (tx.x + 10, yy))
                yy += self.f.get_height() + 4
            if self.desc_busy:
                self._bar(tx.x + 12, tx.bottom - 22, tx.w - 24, t, h=8)
        br = pygame.Rect(WIDTH - 140, HEIGHT - 56, 120, 40)
        self._btn(br, "Terug", self.fs)
        self._zone(br, ("screen", "chat"))

    def _draw_image_model(self, t):
        s = self.screen
        cur = self.cfg.get("image_model", "")
        cur_disp = os.path.basename(cur) if (cur and ("\\" in cur or "/" in cur)) else cur
        s.blit(self.fs.render("Huidig beeldmodel: %s" % (cur_disp or "?"), True, MUTE),
               (24, 100))
        if self.img_msg:
            for i, ln in enumerate(wrap_text(self.img_msg, self.fs, WIDTH - 320)[:1]):
                s.blit(self.fs.render(ln, True, AMBER), (24, 120))
        # --- eigen modellen (uit de map DraveMind-data\eigen-modellen) ---
        s.blit(self.fs.render("Eigen modellen (zet je .safetensors / .ckpt in de map):",
                              True, MUTE), (24, 140))
        omr = pygame.Rect(WIDTH - 24 - 120, 136, 120, 28)
        self._btn(omr, "Open map", self.fs, fg=ACCENT)
        self._zone(omr, ("open_eigen_map",))
        bkr = pygame.Rect(omr.x - 8 - 150, 136, 150, 28)
        self._btn(bkr, "Bestand kiezen...", self.fs)
        self._zone(bkr, ("img_pick_file",))
        y = 166
        eigen = list_eigen_models()
        if not eigen:
            s.blit(self.fs.render("(nog geen eigen modellen in de map - klik 'Open map')",
                                  True, MUTE), (40, y))
            y += 30
        for name, path, gb in eigen[:4]:
            r = pygame.Rect(24, y, WIDTH - 48, 34)
            active = (cur == path)
            toobig = gb > 12
            pygame.draw.rect(s, (34, 44, 38) if active else PANEL, r, border_radius=8)
            pygame.draw.rect(s, GREEN if active else (RED if toobig else LINE),
                             r, width=2, border_radius=8)
            label = name if self.fs.size(name)[0] < WIDTH - 200 else name[:54] + "..."
            s.blit(self.fs.render(label, True, TEXT), (r.x + 12, r.y + 7))
            tag = ("%.1f GB - te groot" % gb) if toobig else ("%.1f GB" % gb)
            ti = self.fs.render(tag, True, RED if toobig else MUTE)
            s.blit(ti, (r.right - ti.get_width() - 12, r.y + 7))
            self._zone(r, ("img_own", path))
            y += 38
        if len(eigen) > 4:
            s.blit(self.fs.render("...en %d meer (gebruik 'Bestand kiezen')"
                                  % (len(eigen) - 4), True, MUTE), (40, y))
            y += 24
        # --- snelkeuze (kant-en-klaar, download) ---
        y += 4
        s.blit(self.fs.render("Snelkeuze (download):", True, MUTE), (24, y))
        y += 24
        for i, m in enumerate(modelreg.IMAGE_CURATED):
            r = pygame.Rect(24, y, WIDTH - 48, 36)
            active = (cur == m["repo"])
            pygame.draw.rect(s, (34, 44, 38) if active else PANEL, r, border_radius=8)
            pygame.draw.rect(s, GREEN if active else LINE, r, width=2, border_radius=8)
            s.blit(self.fs.render(m["name"], True, TEXT), (r.x + 12, r.y + 3))
            tag = "actief" if active else "kiezen"
            s.blit(self.fs.render("%s  -  %s" % (m["size"], tag), True, MUTE),
                   (r.x + 12, r.y + 19))
            self._zone(r, ("img_curated", i))
            y += 40
        # HuggingFace zoeken (tekst -> beeld)
        y += 6
        s.blit(self.fs.render("Zoek op HuggingFace (tekst->beeld) - bv. 'stable "
                              "diffusion', 'sdxl', 'flux':", True, MUTE), (24, y))
        y += 26
        fld = pygame.Rect(24, y, WIDTH - 24 - 130 - 16, 38)
        self._field(fld, self.img_hf_query or "typ een zoekterm...", True,
                    bool(self.img_hf_query), t)
        self._zone(fld, ("imghf_focus",))
        zr = pygame.Rect(fld.right + 12, y, 118, 38)
        self._btn(zr, "Zoek", self.fs, fg=ACCENT)
        self._zone(zr, ("imghf_search",))
        y += 48
        # resultaten (scrolbaar met muiswiel)
        list_top = y
        list_bottom = HEIGHT - 64
        row_h = 30
        if self.img_hf_msg:
            s.blit(self.fs.render(self.img_hf_msg, True, AMBER), (24, list_top))
        yy = list_top + (24 if self.img_hf_msg else 0)
        items = self.img_hf_results
        maxrows = max(1, (list_bottom - yy) // row_h)
        self.img_hf_scroll = max(0, min(self.img_hf_scroll,
                                        max(0, len(items) - maxrows)))
        for it in items[self.img_hf_scroll:self.img_hf_scroll + maxrows]:
            r = pygame.Rect(24, yy, WIDTH - 48, row_h - 4)
            pygame.draw.rect(s, PANEL, r, border_radius=6)
            pygame.draw.rect(s, LINE, r, width=1, border_radius=6)
            label = it if self.fs.size(it)[0] < WIDTH - 80 else it[:78] + "..."
            s.blit(self.fs.render(label, True, TEXT), (r.x + 10, r.y + 3))
            self._zone(r, ("img_pick", it))
            yy += row_h
        if len(items) > maxrows:
            s.blit(self.fs.render("(muiswiel om te scrollen)", True, MUTE),
                   (WIDTH - 240, list_bottom + 2))
        br = pygame.Rect(WIDTH - 140, HEIGHT - 56, 120, 40)
        self._btn(br, "Terug", self.fs)
        self._zone(br, ("screen", "chat"))

    def _draw_settings(self):
        s = self.screen
        s.blit(self.f_title.render("Instellingen", True, ACCENT), (24, 64))
        sname = {1.0: "Normaal", 1.25: "Groot",
                 1.5: "Extra groot"}.get(round(self.ui_scale, 2),
                                         "%d%%" % int(self.ui_scale * 100))
        rows = [("Stem", self.voice.voice or "?"),
                ("Snelheid", "%.2f" % self.voice.speed),
                ("Toonhoogte", "%.2f" % self.voice.pitch),
                ("Volume", "%d%%" % int(self.voice.volume * 100)),
                ("Antwoorden uitspreken", "aan" if self.speak_answers else "uit"),
                ("Tekstgrootte", sname)]
        y = 140
        for i, (lab, val) in enumerate(rows):
            sel = i == self.set_idx
            lr = pygame.Rect(WIDTH // 2 - 250, y, 40, 36)
            rr = pygame.Rect(WIDTH // 2 + 210, y, 40, 36)
            self._btn(lr, "<", self.f, border=GREEN if sel else LINE)
            self._btn(rr, ">", self.f, border=GREEN if sel else LINE)
            self._zone(lr, ("set_adj", i, -1))
            self._zone(rr, ("set_adj", i, 1))
            col = AMBER if sel else TEXT
            img = self.f.render("%s:  %s" % (lab, val), True, col)
            s.blit(img, img.get_rect(center=(WIDTH // 2, y + 18)))
            y += 50
        s.blit(self.fs.render("Klik op < / > (of pijltjes). Esc = terug.", True, MUTE),
               (WIDTH // 2 - 170, y + 10))
        # snelgids + donatie
        gr = pygame.Rect(WIDTH // 2 - 250, y + 50, 230, 44)
        dr = pygame.Rect(WIDTH // 2 + 20, y + 50, 230, 44)
        self._btn(gr, "Snelgids (F1)", self.fs, fg=ACCENT)
        self._zone(gr, ("help",))
        self._btn(dr, "Doneer via PayPal", self.fs, fg=GREEN, border=GREEN)
        self._zone(dr, ("donate",))
        s.blit(self.fs.render("Contact: " + CONTACT_EMAIL, True, MUTE),
               (WIDTH // 2 - 250, y + 104))
        br = pygame.Rect(WIDTH - 140, HEIGHT - 56, 120, 40)
        self._btn(br, "Terug", self.fs)
        self._zone(br, ("screen", "chat"))

    def _shutdown(self):
        for fn in (self.voice.stop, self.brain.shutdown, self.memory.close,
                   self._save_voice_cfg):
            try:
                fn()
            except Exception:
                pass


def main():
    if os.name == "nt":
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID("Dravenlock.DraveAI")
        except Exception:
            pass
    pygame.init()
    try:
        pygame.mixer.init()
    except Exception:
        pass
    screen = pygame.display.set_mode((WIDTH, HEIGHT))
    pygame.display.set_caption("DraveAI")
    import splash
    splash.set_window_icon()
    pygame.key.set_repeat(350, 60)
    try:
        pygame.key.start_text_input()
    except Exception:
        pass
    app = App(screen)
    # splashscherm met logo tot de stem + een eventueel aanwezig model klaar zijn
    splash.run_splash(
        screen, app.clock, "DraveAI",
        status_fn=lambda: (app.load_msg if app.loading else "Opstarten"),
        is_ready=lambda: app.ready)
    app.run()
    pygame.quit()


if __name__ == "__main__":
    main()
