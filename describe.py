# -*- coding: utf-8 -*-
"""describe.py - afbeelding -> tekst: beschrijven en vragen beantwoorden.

Gebruikt BLIP (transformers): een licht model dat een foto in woorden omschrijft
(captioning) en simpele vragen over een afbeelding beantwoordt (VQA). Werkt op
CPU; met een GPU sneller. De modellen downloaden zichzelf bij eerste gebruik naar
DraveMind-data\\caption_model.

Vereist torch + transformers + pillow (zie Installeer-Beeld-AI.bat). Ontbreken
die, dan geeft de functie een nette fout en schrijft een foutbestand.
"""
from __future__ import annotations

import os
import threading


class ImageDescriber:
    def __init__(self, data_dir,
                 caption_model="Salesforce/blip-image-captioning-base",
                 vqa_model="Salesforce/blip-vqa-base"):
        self.data_dir = data_dir
        self.caption_model = caption_model
        self.vqa_model = vqa_model
        self._cap = None        # (processor, model)
        self._vqa = None        # (processor, model)
        self.error = None
        self._lock = threading.Lock()

    def model_dir(self):
        d = os.path.join(self.data_dir, "caption_model")
        try:
            os.makedirs(d, exist_ok=True)
        except Exception:
            pass
        return d

    def _device(self):
        try:
            import torch
            return "cuda" if torch.cuda.is_available() else "cpu"
        except Exception:
            return "cpu"

    def _log(self):
        try:
            import traceback
            with open(os.path.join(self.data_dir, "dravemind-beschrijf-fout.txt"),
                      "w", encoding="utf-8") as f:
                f.write("Beeld-beschrijven kon niet laden.\n\n")
                f.write(traceback.format_exc())
                f.write("\n\nTip: draai Installeer-Beeld-AI.bat (torch + transformers).")
        except Exception:
            pass

    def _load_cap(self):
        if self._cap is not None:
            return True
        with self._lock:
            if self._cap is not None:
                return True
            try:
                from transformers import (BlipProcessor,
                                          BlipForConditionalGeneration)
                proc = BlipProcessor.from_pretrained(
                    self.caption_model, cache_dir=self.model_dir())
                mdl = BlipForConditionalGeneration.from_pretrained(
                    self.caption_model, cache_dir=self.model_dir())
                mdl = mdl.to(self._device())
                self._cap = (proc, mdl)
            except Exception as e:
                self.error = str(e)
                self._log()
        return self._cap is not None

    def _load_vqa(self):
        if self._vqa is not None:
            return True
        with self._lock:
            if self._vqa is not None:
                return True
            try:
                from transformers import (BlipProcessor,
                                          BlipForQuestionAnswering)
                proc = BlipProcessor.from_pretrained(
                    self.vqa_model, cache_dir=self.model_dir())
                mdl = BlipForQuestionAnswering.from_pretrained(
                    self.vqa_model, cache_dir=self.model_dir())
                mdl = mdl.to(self._device())
                self._vqa = (proc, mdl)
            except Exception as e:
                self.error = str(e)
                self._log()
        return self._vqa is not None

    def caption(self, path):
        """Geef een korte (Engelse) omschrijving van de afbeelding."""
        if not self._load_cap():
            raise RuntimeError("beschrijf-model niet beschikbaar: %s"
                               % (self.error or "?"))
        from PIL import Image
        proc, mdl = self._cap
        img = Image.open(path).convert("RGB")
        inputs = proc(img, return_tensors="pt").to(self._device())
        out = mdl.generate(**inputs, max_new_tokens=40)
        return proc.decode(out[0], skip_special_tokens=True).strip()

    def answer(self, path, question):
        """Beantwoord een (Engelse) vraag over de afbeelding."""
        if not self._load_vqa():
            raise RuntimeError("vraag-model niet beschikbaar: %s"
                               % (self.error or "?"))
        from PIL import Image
        proc, mdl = self._vqa
        img = Image.open(path).convert("RGB")
        inputs = proc(img, question, return_tensors="pt").to(self._device())
        out = mdl.generate(**inputs, max_new_tokens=40)
        return proc.decode(out[0], skip_special_tokens=True).strip()
