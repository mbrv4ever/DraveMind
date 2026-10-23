# -*- coding: utf-8 -*-
"""speak.py - stem via neuvoice + amplitude-envelope (optioneel, instelbaar)."""
from __future__ import annotations

import threading
import time

try:
    import numpy as np
except Exception:  # pragma: no cover
    np = None
try:
    import pygame
except Exception:  # pragma: no cover
    pygame = None

FRAME_S = 0.03


try:
    from uitspraak import uitspraak as _uitspraak
except Exception:
    try:
        from .uitspraak import uitspraak as _uitspraak
    except Exception:  # zonder uitspraak.py gewoon de tekst zelf
        def _uitspraak(t, taal="nl"):
            return t


class Voice:
    def __init__(self, voice="M1", lang="nl", data_dir=None):
        self.voice = voice
        self.lang = lang
        self.enabled = True
        self.data_dir = data_dir
        self._tts = None
        self._style = None
        self._sr = 24000
        self._ready = False
        self._failed = False
        self._lock = threading.Lock()
        self.voices = []
        self.speed = 1.0
        self.pitch = 1.0
        self.volume = 1.0
        self.speaking = False
        self._env = None
        self._t0 = 0.0
        self._ch = None
        self._level = 0.0

    def warmup(self):
        threading.Thread(target=self._ensure, daemon=True).start()

    def available(self):
        return self._ready and not self._failed

    def _voice_dir(self):
        import os
        import sys
        if self.data_dir:
            try:
                os.makedirs(self.data_dir, exist_ok=True)
                return self.data_dir
            except Exception:
                pass
        if getattr(sys, "frozen", False):
            return os.path.dirname(os.path.abspath(sys.executable))
        return os.path.dirname(os.path.abspath(sys.argv[0])) or os.getcwd()

    def _ensure(self):
        if self._ready or self._failed:
            return
        with self._lock:
            if self._ready or self._failed:
                return
            try:
                from neuvoice import TTS
                tts = TTS(auto_download=True)
                names = list(getattr(tts, "voice_style_names", []) or [])
                want = (self.voice or "").strip().lower()
                pick = None
                for n in names:
                    if n.strip().lower() == want:
                        pick = n
                        break
                if pick is None and "Leon" in names:
                    pick = "Leon"
                if pick is None:
                    for n in names:
                        if n.upper().startswith("M") or "MALE" in n.upper():
                            pick = n
                            break
                if pick is None and names:
                    pick = names[0]
                self.voices = names
                if pick:
                    self.voice = pick
                self._style = tts.get_voice_style(pick) if pick else None
                self._sr = int(getattr(tts, "sample_rate", 24000) or 24000)
                self._tts = tts
                self._ready = True
            except Exception:
                self._failed = True

    def list_voices(self):
        return list(self.voices)

    def set_voice(self, voice):
        if not voice or voice == self.voice:
            return
        self.voice = voice
        if self._tts is not None:
            try:
                self._style = self._tts.get_voice_style(voice)
                return
            except Exception:
                pass
        self._ready = False
        self._failed = False
        self._style = None
        self._tts = None

    def speak(self, text, lang=None):
        if not text or not self.enabled or np is None or pygame is None:
            return
        threading.Thread(target=self._speak_blocking, args=(text, lang), daemon=True).start()

    def speak_sync(self, text, lang=None):
        if not text or not self.enabled or np is None or pygame is None:
            return
        self._speak_blocking(text, lang)

    def _speak_blocking(self, text, lang=None):
        try:
            self._ensure()
            if not self._ready:
                return
            spd = float(self.speed) if 0.5 <= self.speed <= 2.0 else 1.0
            with self._lock:
                wav, _dur = self._tts.synthesize(_uitspraak(text, lang or self.lang), voice_style=self._style,
                                                 total_steps=10, speed=spd,
                                                 lang=(lang or self.lang))
            data = np.asarray(wav, dtype=np.float32).flatten()
            if len(data) < 2:
                return
            data = self._apply_pitch(data)
            self._env = self._envelope(data)
            snd = self._to_sound(data)
            if snd is None or not pygame.mixer.get_init():
                return
            ch = pygame.mixer.find_channel(True)
            if ch is None:
                return
            self._ch = ch
            self._t0 = time.time()
            self.speaking = True
            vol = self.volume if 0.0 <= self.volume <= 1.0 else 1.0
            snd.set_volume(float(vol))
            ch.play(snd)
            while ch.get_busy():
                time.sleep(0.03)
        except Exception:
            pass
        finally:
            self.speaking = False
            self._ch = None

    def stop(self):
        try:
            if self._ch is not None:
                self._ch.stop()
        except Exception:
            pass
        self.speaking = False

    def _apply_pitch(self, data):
        p = float(self.pitch)
        if abs(p - 1.0) < 0.01 or len(data) < 4:
            return data
        p = min(1.4, max(0.7, p))
        n2 = max(2, int(len(data) / p))
        xp = np.linspace(0.0, 1.0, len(data), dtype=np.float32)
        xq = np.linspace(0.0, 1.0, n2, dtype=np.float32)
        return np.interp(xq, xp, data).astype(np.float32)

    def _envelope(self, data):
        n = max(1, int(self._sr * FRAME_S))
        m = len(data) // n
        if m < 1:
            return np.array([float(np.sqrt(np.mean(data ** 2)))], dtype=np.float32)
        trimmed = data[:m * n].reshape(m, n)
        env = np.sqrt(np.mean(trimmed ** 2, axis=1))
        peak = float(env.max()) if env.size else 1.0
        if peak > 1e-6:
            env = env / peak
        return np.clip(env ** 0.7, 0.0, 1.0).astype(np.float32)

    def level(self):
        target = 0.0
        if self.speaking and self._env is not None:
            idx = int((time.time() - self._t0) / FRAME_S)
            if 0 <= idx < len(self._env):
                target = float(self._env[idx])
        self._level += (target - self._level) * 0.5
        return self._level

    def _to_sound(self, data):
        try:
            init = pygame.mixer.get_init()
            mr = init[0] if init else 44100
            if self._sr != mr and len(data) > 1:
                nn = int(len(data) * mr / float(self._sr))
                xp = np.linspace(0.0, 1.0, len(data), dtype=np.float32)
                xq = np.linspace(0.0, 1.0, nn, dtype=np.float32)
                data = np.interp(xq, xp, data).astype(np.float32)
            data = np.clip(data, -1.0, 1.0)
            pcm = (data * 32767.0 * 0.9).astype(np.int16)
            stereo = np.column_stack([pcm, pcm])
            return pygame.sndarray.make_sound(np.ascontiguousarray(stereo))
        except Exception:
            return None
