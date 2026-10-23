# -*- coding: utf-8 -*-
"""models.py - de keuzelijst van taalmodellen voor DraveMind.

Een paar geteste, lichte GGUF-modellen (consistente Qwen-naamgeving, hoge kans
op een schone download), plus de mogelijkheid om in de app zelf een eigen
HuggingFace-repo + bestandsnaam in te typen. Modellen worden door localbrain
naar DraveMind-data\\model gedownload.
"""
from __future__ import annotations

import json
import urllib.parse
import urllib.request

_HF = "https://huggingface.co"
_UA = {"User-Agent": "DraveMind"}


def search_hf(query, limit=25, kind="gguf"):
    """Zoek modellen op HuggingFace; geeft een lijst repo-ids terug (populairste
    eerst). kind='gguf' = taalmodellen voor chat; kind='image' = tekst->beeld
    modellen (diffusers). Geen account/sleutel nodig voor publieke modellen."""
    q = (query or "").strip()
    if not q:
        return []
    try:
        params = {"search": q, "limit": limit,
                  "sort": "downloads", "direction": "-1"}
        if kind == "image":
            params["pipeline_tag"] = "text-to-image"
        else:
            params["filter"] = "gguf"
        url = _HF + "/api/models?" + urllib.parse.urlencode(params)
        req = urllib.request.Request(url, headers=_UA)
        with urllib.request.urlopen(req, timeout=12) as r:
            data = json.loads(r.read().decode("utf-8"))
        return [m.get("id", "") for m in data if m.get("id")]
    except Exception:
        return []


def list_gguf_files(repo, limit=60):
    """Geef de GGUF-bestanden in een repo terug (aanrader q4_k_m bovenaan)."""
    try:
        url = _HF + "/api/models/" + urllib.parse.quote(repo, safe="/")
        req = urllib.request.Request(url, headers=_UA)
        with urllib.request.urlopen(req, timeout=12) as r:
            data = json.loads(r.read().decode("utf-8"))
        files = [s.get("rfilename", "") for s in data.get("siblings", [])]
        ggufs = [f for f in files if f.lower().endswith(".gguf")]
        # vision-/hulpprojectorbestanden eruit: dat zijn GEEN taalmodellen en
        # geven 'Failed to load model' als je ze probeert te laden
        ggufs = [f for f in ggufs if "mmproj" not in f.lower()]
        # losse (niet-gesplitste) q4_k_m bestanden bovenaan: makkelijkst te laden
        def rank(f):
            lo = f.lower()
            split = "-of-" in lo
            return (1 if split else 0, 0 if "q4_k_m" in lo else 1, lo)
        ggufs.sort(key=rank)
        return ggufs[:limit]
    except Exception:
        return []


# Elk item: naam (weergave), repo (HuggingFace), file (GGUF-bestand), size (info).
CURATED = [
    {"name": "Qwen2.5 3B  (aanbevolen, sterk in NL)",
     "repo": "Qwen/Qwen2.5-3B-Instruct-GGUF",
     "file": "qwen2.5-3b-instruct-q4_k_m.gguf", "size": "~2.1 GB"},
    {"name": "Qwen2.5 1.5B  (licht en snel)",
     "repo": "Qwen/Qwen2.5-1.5B-Instruct-GGUF",
     "file": "qwen2.5-1.5b-instruct-q4_k_m.gguf", "size": "~1.1 GB"},
    {"name": "Qwen2.5 0.5B  (heel licht)",
     "repo": "Qwen/Qwen2.5-0.5B-Instruct-GGUF",
     "file": "qwen2.5-0.5b-instruct-q4_k_m.gguf", "size": "~0.5 GB"},
]


def find(repo, file):
    for m in CURATED:
        if m["repo"] == repo and m["file"] == file:
            return m
    return None


# Beeldmodellen (diffusers-repo's) voor de Beeld-tab. Eigen lijst, los van de
# taalmodellen hierboven. Worden in een EIGEN map gezet (DraveMind-data\image_model).
IMAGE_CURATED = [
    {"name": "DreamShaper 8  (klein EN mooi - AANBEVOLEN, ~25 stappen)",
     "repo": "Lykon/dreamshaper-8", "size": "~2 GB"},
    {"name": "Stable Diffusion 1.5  (klassiek, ~25-30 stappen)",
     "repo": "stable-diffusion-v1-5/stable-diffusion-v1-5", "size": "~2 GB (fp16)"},
]
