# -*- coding: utf-8 -*-
"""localbrain.py - lokaal taalmodel in de app zelf (llama-cpp-python).

Draait een GGUF-model rechtstreeks, zonder externe server. Het modelbestand
staat in de data-map (DraveMind-data\\model). Je kunt van model wisselen met
set_model(); ensure() laadt (en downloadt zo nodig) het actieve model.
Kapotte HIP_PATH/CUDA_PATH (oude AMD/NVIDIA-resten) worden vooraf weggehaald.
"""
from __future__ import annotations

import os
import threading


class LocalBackend:
    def __init__(self, repo, filename, data_dir, n_ctx=4096):
        self.repo = repo
        self.filename = filename
        self.data_dir = data_dir
        self.n_ctx = n_ctx
        self.llm = None
        self.failed = False
        self.loading = False
        self.error = None
        self._lock = threading.Lock()

    def available(self):
        return self.llm is not None

    def model_dir(self):
        d = os.path.join(self.data_dir, "model")
        try:
            os.makedirs(d, exist_ok=True)
        except Exception:
            pass
        return d

    def set_model(self, repo, filename):
        """Wissel van model; volgende ensure() laadt het nieuwe."""
        if repo == self.repo and filename == self.filename and self.llm is not None:
            return
        self.repo = repo
        self.filename = filename
        self.llm = None
        self.failed = False
        self.error = None

    def model_present(self, file=None, filename=None):
        return self.local_path(file or filename) is not None

    def local_path(self, filename=None):
        """Volledig pad naar het modelbestand als het lokaal aanwezig is, anders None."""
        filename = filename or self.filename
        md = self.model_dir()
        try:
            p = os.path.join(md, filename)
            if os.path.isfile(p):
                return p
            for root, _dirs, files in os.walk(md):
                if filename in files:
                    return os.path.join(root, filename)
        except Exception:
            pass
        return None

    def ensure(self):
        if self.llm is not None:
            return True
        if self.failed:
            return False
        with self._lock:
            if self.llm is not None:
                return True
            if self.failed:
                return False
            self.loading = True
            try:
                for _var in ("HIP_PATH", "HIP_PATH_57", "HIPSDK_PATH", "CUDA_PATH"):
                    _p = os.environ.get(_var)
                    if _p and not os.path.isdir(os.path.join(_p, "bin")):
                        os.environ.pop(_var, None)
                from llama_cpp import Llama
                local = self.local_path()
                if local:
                    # al gedownload: rechtstreeks laden (geen netwerk-check bij HF,
                    # die kan blijven hangen bij wisselen van model / offline)
                    self.llm = Llama(model_path=local, n_ctx=self.n_ctx,
                                     verbose=False)
                else:
                    self.llm = Llama.from_pretrained(
                        repo_id=self.repo, filename=self.filename,
                        local_dir=self.model_dir(), n_ctx=self.n_ctx, verbose=False)
            except Exception as e:
                self.failed = True
                self.error = str(e)
                try:
                    import traceback
                    with open(os.path.join(self.data_dir, "dravemind-model-fout.txt"),
                              "w", encoding="utf-8") as f:
                        f.write("Model kon niet laden.\nRepo: %s\nBestand: %s\n\n"
                                % (self.repo, self.filename))
                        f.write(traceback.format_exc())
                except Exception:
                    pass
            finally:
                self.loading = False
        return self.llm is not None

    def chat(self, messages):
        if not self.ensure():
            raise RuntimeError("lokaal model niet beschikbaar: %s" % (self.error or "?"))
        out = self.llm.create_chat_completion(messages=messages, temperature=0.7,
                                              max_tokens=512)
        try:
            return (out["choices"][0]["message"]["content"] or "").strip()
        except Exception:
            return ""

    def close(self):
        self.llm = None
