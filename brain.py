# -*- coding: utf-8 -*-
"""brain.py - het brein van DraveMind.

Backend: lokaal model (localbrain) of een Ollama-server. Kan online zoeken via
een aparte router-stap, onthoudt gesprekken/feiten (geheugen) en leert zelf
blijvende weetjes. 'onthoud dat ...' slaat iets expliciet op.
Alles via urllib uit de standaardbibliotheek (voor de Ollama-optie).
"""
from __future__ import annotations

import json
import re
import threading
import urllib.parse
import urllib.request

DEFAULT_SYSTEM = (
    "Je bent een behulpzame, vriendelijke AI-assistent (standaardnaam DraveAI). "
    "Geeft de gebruiker je een andere naam, gebruik die dan voortaan, ook als hij "
    "vraagt hoe je heet. Antwoord helder en beknopt in het Nederlands, tenzij de "
    "gebruiker een andere taal gebruikt. Je hebt een geheugen van eerdere "
    "gesprekken; gebruik de herinneringen en feiten uit de context. Krijg je "
    "zoekresultaten mee, gebruik die en geef meteen antwoord - zeg nooit dat je "
    "iets gaat opzoeken."
)

ROUTER_SYSTEM = (
    "Bepaal of er ONLINE opgezocht moet worden om de vraag goed te beantwoorden. "
    "Antwoord met PRECIES één regel: 'NEE' als je het uit eigen kennis of het "
    "geheugen kunt, of 'ZOEK: <zoekterm>' alleen bij echt actuele/externe info "
    "(weer, nieuws, sport, prijzen, recente gebeurtenissen). Vragen over jezelf, "
    "de gebruiker, het gesprek of het geheugen NOOIT opzoeken: antwoord dan 'NEE'. "
    "Geen verdere uitleg."
)

# Woorden die wijzen op een identiteits-/geheugenvraag -> nooit online zoeken.
_NO_SEARCH = ("heet", "naam", "wie ben", "noem ik", "noem je", "wat zei",
              "herinner", "onthoud", "geheugen", "wie bent")

FACT_SYSTEM = (
    "Haal uit het bericht van de gebruiker maximaal één kort, blijvend, "
    "persoonlijk feit (naam, voorkeur, bezit, afspraak, belangrijke datum). "
    "Antwoord met alleen dat feit in één korte zin, of met alleen 'GEEN'."
)

REMEMBER_TRIGGERS = (
    "onthoud dat ", "onthoud dit ", "onthoud even dat ", "onthoud even ",
    "onthoud dit:", "onthoud:", "remember that ", "remember this ", "remember:",
)


class Brain:
    def __init__(self, host="http://localhost:11434", model="llama3.2",
                 system=None, history_len=12, timeout=180):
        self.host = host.rstrip("/")
        self.model = model
        self.system = system or DEFAULT_SYSTEM
        self.history = []
        self.history_len = history_len
        self.timeout = timeout
        self.last_error = None
        self.memory = None
        self.search = None
        self.user_name = ""
        self.assistant_name = ""   # door de gebruiker gegeven naam (blijft bewaard)
        self.instructions = ""     # vaste richtlijnen van de gebruiker (Geheugen-tab)
        self.auto_learn = True
        self.local = None          # localbrain.LocalBackend

    # ---------- backend ----------
    def reachable(self):
        if self.local is not None:
            return self.local.available()
        try:
            with urllib.request.urlopen(self.host + "/api/tags", timeout=4) as r:
                json.loads(r.read().decode("utf-8"))
            return True
        except Exception as e:
            self.last_error = str(e)
            return False

    def ensure_running(self):
        if self.local is not None:
            return self.local.ensure()
        return self.reachable()

    def shutdown(self):
        if self.local is not None:
            self.local.close()

    def _post(self, messages):
        if self.local is not None:
            return self.local.chat(messages)
        payload = {"model": self.model, "messages": messages, "stream": False,
                   "options": {"temperature": 0.7}}
        data = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(self.host + "/api/chat", data=data,
                                     headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=self.timeout) as r:
            out = json.loads(r.read().decode("utf-8"))
        reply = (out.get("message", {}) or {}).get("content", "").strip()
        if not reply:
            reply = out.get("response", "").strip()
        return reply

    # ---------- geheugen-opdrachten ----------
    _RENAME_PATS = (
        r"ik noem je\s+([a-zA-Z][\w-]{1,20})",
        r"noem ik je\s+([a-zA-Z][\w-]{1,20})",
        r"(?:je|jij|jouw)\s+naam\s+is\s+([a-zA-Z][\w-]{1,20})",
        r"(?:je|jij)\s+heet\s+(?:nu\s+|voortaan\s+)?([a-zA-Z][\w-]{1,20})",
        r"heet\s+(?:je|jij)\s+(?:nu\s+|voortaan\s+)?([a-zA-Z][\w-]{1,20})",
        r"heet\s+nu\s+([a-zA-Z][\w-]{1,20})",
        r"(?:vanaf nu|voortaan)\s+heet\s+je\s+([a-zA-Z][\w-]{1,20})",
    )
    _RENAME_BAD = {"nu", "je", "jij", "jou", "jouw", "niet", "ook", "een", "de",
                   "het", "hoe", "wat", "wie", "oke", "oké", "ja", "nee",
                   "voortaan", "naam", "heet"}

    _USERNAME_PATS = (
        r"ik heet\s+([a-zA-Z][\w-]{1,20})",
        r"mijn naam is\s+([a-zA-Z][\w-]{1,20})",
        r"noem (?:mij|me)\s+([a-zA-Z][\w-]{1,20})",
    )
    _BAD_NAMES = {"moe", "blij", "klaar", "benieuwd", "boos", "ziek", "thuis",
                  "weg", "er", "het", "een", "aan", "oke", "oké"}

    def _detect_rename(self, text):
        low = text.lower()
        for p in self._RENAME_PATS:
            m = re.search(p, low)
            if m:
                name = m.group(1)
                if name not in self._RENAME_BAD and len(name) >= 2:
                    return name[:1].upper() + name[1:]
        return None

    def _detect_user_name(self, text):
        """Naam van de GEBRUIKER ('ik heet X' / 'mijn naam is X' / 'ik ben Naam')."""
        low = text.lower()
        for p in self._USERNAME_PATS:
            m = re.search(p, low)
            if m:
                name = m.group(1)
                if name not in self._RENAME_BAD and name not in self._BAD_NAMES and len(name) >= 2:
                    return name[:1].upper() + name[1:]
        # 'ik ben X' alleen als X met een hoofdletter is getypt (waarschijnlijk een naam)
        m = re.search(r"\bik ben\s+([A-Za-z][\w-]{1,20})", text)
        if m:
            name = m.group(1)
            if name[:1].isupper() and name.lower() not in self._BAD_NAMES:
                return name
        return None

    def _try_remember(self, user_text):
        low = user_text.lower()
        fact = None
        # 1) trigger aan het begin van de zin
        for trig in REMEMBER_TRIGGERS:
            if low.startswith(trig):
                fact = user_text[len(trig):].strip(" :")
                break
        # 2) 'onthoud dit/dat/even' of 'remember this/that' ERGENS in de zin
        if fact is None and re.search(r"(onthoud (dit|dat|even)|remember (this|that))", low):
            fact = re.sub(r"(?i)\s*\b(onthoud (dit|dat|even)?|remember (this|that)?)\b\s*[:,\.]?",
                          " ", user_text).strip(" ,.:")
        # 3) los 'onthoud ...' aan het begin (maar geen vraag)
        if fact is None and low.startswith("onthoud ") and not low.startswith(
                ("onthoud jij", "onthoud je", "onthoud jullie", "onthoud u ")):
            fact = user_text[len("onthoud "):].strip(" :")
        if not fact:
            return None
        if self.memory is not None:
            self.memory.remember_fact(fact)
        naam = (", " + self.user_name) if self.user_name else ""
        return "Genoteerd%s. Ik onthoud het." % naam

    def _extract_fact(self, user_text):
        try:
            out = self._post([{"role": "system", "content": FACT_SYSTEM},
                              {"role": "user", "content": user_text}])
            fact = (out or "").strip()
            if fact and fact.upper() != "GEEN" and len(fact) < 200 and self.memory is not None:
                self.memory.remember_fact(fact)
        except Exception:
            pass

    def _should_search(self, user_text):
        if self.search is None:
            return None
        low = user_text.lower()
        if any(k in low for k in _NO_SEARCH):
            return None        # identiteits-/geheugenvraag: niet online zoeken
        try:
            route = self._post([{"role": "system", "content": ROUTER_SYSTEM},
                                {"role": "user", "content": user_text}])
        except Exception:
            return None
        line = (route or "").strip()
        if line.upper().startswith("ZOEK:"):
            q = line.split(":", 1)[1].strip()
            return q or user_text
        return None

    # ---------- echte weergegevens (wttr.in, gratis, geen sleutel) ----------
    _WEATHER_PATS = (
        r"weer(?:bericht)?\s+(?:in|te|voor|van|op)\s+([a-zà-ÿ][\wà-ÿ .'-]{1,40})",
        r"temperatuur\s+(?:in|te|voor|van)\s+([a-zà-ÿ][\wà-ÿ .'-]{1,40})",
        r"hoe\s+(?:warm|koud|heet)\s+.*\bin\s+([a-zà-ÿ][\wà-ÿ .'-]{1,40})",
    )

    def _weather_city(self, text):
        """Haal de plaatsnaam uit een weervraag, of None als het er geen is."""
        low = text.lower()
        if "weer" not in low and "temperatuur" not in low:
            return None
        for p in self._WEATHER_PATS:
            m = re.search(p, low)
            if m:
                city = m.group(1)
                city = re.sub(r"\b(vandaag|nu|morgen|straks|het|is|wordt)\b", " ", city)
                city = city.strip(" ?.!,").strip()
                if len(city) >= 2:
                    return city.title()
        return None

    def _fetch_weather(self, city):
        url = ("https://wttr.in/%s?format=%%C,+%%t+(gevoelstemperatuur+%%f),+"
               "wind+%%w,+luchtvochtigheid+%%h&lang=nl&m"
               % urllib.parse.quote(city.strip()))
        req = urllib.request.Request(url, headers={"User-Agent": "curl/8.0"})
        with urllib.request.urlopen(req, timeout=10) as r:
            txt = r.read().decode("utf-8", "replace").strip()
        for a in "←↑→↓↖↗↘↙":
            txt = txt.replace(a, "")
        return " ".join(txt.split())

    # ---------- vraag beantwoorden ----------
    def ask(self, user_text, on_status=None):
        user_text = (user_text or "").strip()
        if not user_text:
            return ""
        new_name = self._detect_rename(user_text)
        if new_name:
            self.assistant_name = new_name
            if self.memory is not None:
                self.memory.set_meta("assistant_name", new_name)
                self.memory.remember_fact("Jij (de assistent) heet voortaan %s." % new_name)
            return "Begrepen, vanaf nu heet ik %s." % new_name
        uname = self._detect_user_name(user_text)
        if uname:
            self.user_name = uname
            if self.memory is not None:
                self.memory.set_meta("user_name", uname)
                self.memory.remember_fact("De gebruiker heet %s." % uname)
            return "Aangenaam, %s. Ik onthoud je naam." % uname
        conf = self._try_remember(user_text)
        if conf is not None:
            return conf
        # weervraag? echte actuele weergegevens ophalen (niet het model laten gokken)
        city = self._weather_city(user_text)
        if city:
            if on_status:
                on_status("searching")
            try:
                w = self._fetch_weather(city)
            except Exception:
                w = ""
            if w and "unknown location" not in w.lower() and "not found" not in w.lower():
                naam = (", " + self.user_name) if self.user_name else ""
                return "Het actuele weer in %s%s: %s." % (city, naam, w)
        try:
            results = ""
            q = self._should_search(user_text)
            if q:
                if on_status:
                    on_status("searching")
                try:
                    results = self.search.search(q)
                except Exception:
                    results = ""
                if on_status:
                    on_status("thinking")
            ctx = ""
            if self.memory is not None:
                try:
                    facts = self.memory.recent_facts(6)
                except Exception:
                    facts = []
                try:
                    mems = self.memory.recall(user_text)
                except Exception:
                    mems = []
                combined = []
                for x in facts + mems:
                    if x and x not in combined:
                        combined.append(x)
                if combined:
                    ctx = ("Wat je je herinnert (gebruik dit als het relevant is):\n- "
                           + "\n- ".join(combined[:8]))
            name_line = ""
            if self.user_name:
                name_line += ("\n\nDe GEBRUIKER (je gesprekspartner) heet %s. Vraagt "
                              "de gebruiker 'wat is mijn naam' of 'hoe heet ik', "
                              "antwoord dan met %s." % (self.user_name, self.user_name))
            if self.assistant_name:
                name_line += ("\n\nJIJZELF heet %s. Vraagt iemand 'hoe heet jij', "
                              "antwoord met %s. Verwar je eigen naam niet met die van "
                              "de gebruiker." % (self.assistant_name, self.assistant_name))
            search_block = ""
            if results:
                search_block = ("\n\nActuele zoekresultaten (gebruik deze en geef "
                                "meteen antwoord):\n" + results)
            rules = ""
            if self.instructions.strip():
                rules = ("\n\nVASTE RICHTLIJNEN van de gebruiker (volg deze strikt):\n"
                         + self.instructions.strip())
            sys_prompt = self.system + rules + name_line + (("\n\n" + ctx) if ctx else "") + search_block
            messages = ([{"role": "system", "content": sys_prompt}]
                        + self.history[-self.history_len:]
                        + [{"role": "user", "content": user_text}])
            reply = self._post(messages)
            if not reply:
                raise ValueError("leeg antwoord")
            self.history.append({"role": "user", "content": user_text})
            self.history.append({"role": "assistant", "content": reply})
            self.history = self.history[-self.history_len:]
            if self.memory is not None:
                self.memory.add("user", user_text)
                self.memory.add("assistant", reply)
                if self.auto_learn:
                    threading.Thread(target=self._extract_fact,
                                     args=(user_text,), daemon=True).start()
            self.last_error = None
            return reply
        except Exception as e:
            self.last_error = str(e)
            return ("Sorry, ik kan mijn brein nu niet bereiken. Staat er een model "
                    "geselecteerd en gedownload? (Zie Modellen.)")

    def reset(self):
        self.history = []
