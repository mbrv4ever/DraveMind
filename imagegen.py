# -*- coding: utf-8 -*-
"""imagegen.py - tekst -> afbeelding (lokaal) via diffusers (Stable Diffusion).

Zwaar: vereist torch + diffusers + een model van enkele GB. Traag op CPU, snel
met een GPU. Het model downloadt zichzelf bij het eerste gebruik naar
DraveMind-data\\image_model. Standaard: sd-turbo (snel, weinig stappen).

Ontbreekt torch/diffusers, dan meldt available() False en zet ensure() een
foutbestand neer, zodat de app netjes blijft werken.
"""
from __future__ import annotations

import os
import threading


class _Cancelled(Exception):
    """Intern: gebruiker annuleerde het genereren."""


class ImageGen:
    def __init__(self, model_id, data_dir, steps=4, width=512, height=512):
        self.model_id = model_id
        self.data_dir = data_dir
        self.steps = steps
        self.width = width
        self.height = height
        self.pipe = None
        self.is_sdxl = False
        self.failed = False
        self.loading = False
        self.busy = False
        self.error = None
        self.cur_step = 0          # huidige denoise-stap (voor voortgang)
        self.total_steps = 0
        self._device = "cpu"
        self._cuda = None        # None = nog niet gecheckt
        self._lock = threading.Lock()

    def cuda_available(self):
        """True als torch een CUDA-GPU ziet (gecached; eerste keer laadt torch)."""
        if self._cuda is None:
            try:
                import torch
                self._cuda = bool(torch.cuda.is_available())
            except Exception:
                self._cuda = False
        return self._cuda

    def device_label(self):
        if self._cuda is None:
            return "onbekend"
        return "GPU (CUDA)" if self._cuda else "CPU (traag)"

    def available(self):
        return self.pipe is not None

    def model_dir(self):
        d = os.path.join(self.data_dir, "image_model")
        try:
            os.makedirs(d, exist_ok=True)
        except Exception:
            pass
        return d

    def _free_pipe(self):
        """Geef het huidige model + VRAM vrij (voorkomt crash bij modelwissel)."""
        self.pipe = None
        try:
            import gc
            import torch
            gc.collect()
            if torch.cuda.is_available():
                torch.cuda.empty_cache()
        except Exception:
            pass

    def set_model(self, model_id):
        if model_id and model_id != self.model_id:
            self.model_id = model_id
            self._free_pipe()
            self.is_sdxl = False
            self.failed = False
            self.error = None

    def model_present(self, repo=None):
        """Ruwe check of het beeldmodel al gedownload is (diffusers-cache)."""
        repo = repo or self.model_id
        try:
            folder = "models--" + repo.replace("/", "--")
            return os.path.isdir(os.path.join(self.model_dir(), folder))
        except Exception:
            return False

    def ensure(self):
        if self.pipe is not None:
            return True
        if self.failed:
            return False
        with self._lock:
            if self.pipe is not None:
                return True
            if self.failed:
                return False
            self.loading = True
            try:
                import torch
                self._device = "cuda" if torch.cuda.is_available() else "cpu"
                dtype = torch.float16 if self._device == "cuda" else torch.float32
                mid = self.model_id or ""
                is_file = (os.path.isfile(mid) and
                           mid.lower().endswith((".safetensors", ".ckpt")))
                # VRAM en bestandsgrootte bepalen (vangnet tegen crashes)
                gb = 99.0
                if self._device == "cuda":
                    try:
                        gb = torch.cuda.get_device_properties(0).total_memory / 1024 ** 3
                    except Exception:
                        gb = 99.0
                size_gb = 0.0
                if is_file:
                    try:
                        size_gb = os.path.getsize(mid) / 1024 ** 3
                    except Exception:
                        size_gb = 0.0
                # te groot om te laden (past niet in werkgeheugen/VRAM) -> netjes weigeren
                if size_gb > 12:
                    self.failed = True
                    self.error = ("Dit model is %.0f GB - veel te groot voor deze pc "
                                  "(zoals Flux of grote AIO/Qwen-modellen). Kies een "
                                  "SD 1.5-model (~2-4 GB); die werkt snel op je kaart."
                                  % size_gb)
                    return False
                low = mid.lower()
                looks_sdxl = ("xl" in os.path.basename(low)) or ("sdxl" in low)
                big = size_gb > 4.5            # SDXL/zwaar -> offload nodig
                self.is_sdxl = False
                if is_file:
                    # een eigen, los modelbestand (zoals uit Stable Diffusion WebUI)
                    from diffusers import (StableDiffusionPipeline,
                                           StableDiffusionXLPipeline)
                    name = os.path.basename(mid).lower()
                    sdxl_hint = ("xl" in name or "sdxl" in name)
                    if sdxl_hint:
                        try:
                            pipe = StableDiffusionXLPipeline.from_single_file(
                                mid, torch_dtype=dtype)
                            self.is_sdxl = True
                        except Exception:
                            pipe = StableDiffusionPipeline.from_single_file(
                                mid, torch_dtype=dtype)
                    else:
                        try:
                            pipe = StableDiffusionPipeline.from_single_file(
                                mid, torch_dtype=dtype)
                        except Exception:
                            pipe = StableDiffusionXLPipeline.from_single_file(
                                mid, torch_dtype=dtype)
                            self.is_sdxl = True
                else:
                    from diffusers import AutoPipelineForText2Image
                    # eerst de lichtere fp16-versie proberen (kleiner + minder RAM);
                    # heeft de repo die niet, dan de gewone
                    try:
                        pipe = AutoPipelineForText2Image.from_pretrained(
                            mid, torch_dtype=dtype, variant="fp16",
                            cache_dir=self.model_dir())
                    except Exception:
                        pipe = AutoPipelineForText2Image.from_pretrained(
                            mid, torch_dtype=dtype, cache_dir=self.model_dir())
                try:
                    pipe.set_progress_bar_config(disable=True)
                except Exception:
                    pass
                # zuinig met geheugen (belangrijk bij weinig VRAM, bv. 4 GB)
                for fn in ("enable_attention_slicing", "enable_vae_slicing",
                           "enable_vae_tiling"):
                    try:
                        getattr(pipe, fn)()
                    except Exception:
                        pass
                # geheugenstrategie (zoals A1111's medvram/lowvram)
                placed = False
                if self._device == "cuda" and (self.is_sdxl or big) and gb < 6:
                    # zwaar model op een kleine kaart (bv. 4 GB): submodules apart in/uit
                    # het VRAM schuiven -> past wel, maar traag (zoals A1111 --lowvram).
                    # SD 1.5 passen gewoon in 4 GB en gaan vol op de GPU (snel).
                    for m in ("enable_sequential_cpu_offload",
                              "enable_model_cpu_offload"):
                        try:
                            getattr(pipe, m)()
                            placed = True
                            break
                        except Exception:
                            pass
                if not placed:
                    pipe = pipe.to(self._device)
                self.pipe = pipe
            except Exception as e:
                self.failed = True
                self.error = str(e)
                try:
                    import traceback
                    with open(os.path.join(self.data_dir, "dravemind-image-fout.txt"),
                              "w", encoding="utf-8") as f:
                        f.write("Beeld-AI kon niet laden.\nModel: %s\n\n" % self.model_id)
                        f.write(traceback.format_exc())
                        f.write("\n\nTip: installeer torch + diffusers (zie README).")
                except Exception:
                    pass
            finally:
                self.loading = False
        return self.pipe is not None

    def generate(self, prompt, out_path, negative_prompt=None, should_cancel=None):
        """Genereer een afbeelding en sla op in out_path. Geeft het pad terug.
        negative_prompt: wat NIET in beeld mag (helpt tegen rare anatomie/tekst).
        should_cancel: optionele functie die True geeft als de gebruiker annuleert."""
        if not self.ensure():
            raise RuntimeError("beeld-AI niet beschikbaar: %s" % (self.error or "?"))
        name = (self.model_id or "").lower()
        # guidance hangt af van het modeltype; het AANTAL STAPPEN bepaalt de
        # gebruiker zelf (self.steps), zodat je zelf kwaliteit/snelheid kiest.
        if "turbo" in name:
            g = 0.0                                  # turbo: geen guidance
        elif any(k in name for k in ("hyper", "lightning", "lcm")):
            g = 1.5                                  # hyper/lightning: lage guidance
        else:
            g = 7.5                                  # gewone modellen
        steps = max(1, int(self.steps))
        kwargs = {"num_inference_steps": steps, "guidance_scale": g}
        # afmeting (veelvouden van 8 vereist door de modellen)
        try:
            kwargs["width"] = int(self.width) // 8 * 8
            kwargs["height"] = int(self.height) // 8 * 8
        except Exception:
            pass
        # voortgang + annuleren via callback per stap
        self.cur_step = 0
        self.total_steps = steps

        def _cb(pipe, step, timestep, cbkw):
            self.cur_step = step + 1
            if should_cancel and should_cancel():
                raise _Cancelled()
            return cbkw
        try:
            kwargs["callback_on_step_end"] = _cb
            out = self.pipe(prompt, **kwargs)
        except _Cancelled:
            raise RuntimeError("CANCELLED")
        except TypeError:
            # oudere pipeline zonder callback_on_step_end: zonder voortgang/annuleren
            kwargs.pop("callback_on_step_end", None)
            out = self.pipe(prompt, **kwargs)
        image = out.images[0]
        image.save(out_path)
        return out_path
