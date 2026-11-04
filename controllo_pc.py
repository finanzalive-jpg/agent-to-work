"""
controllo_pc.py - Controllo del computer e comunicazione.

- apri_sito: apre un sito per nome
- volume: alza / abbassa / muto
- screenshot: cattura lo schermo sul Desktop
- blocca_pc / spegni_pc (con annullo) / riavvia_pc
- whatsapp: apre WhatsApp con il messaggio pronto (numero dalla rubrica)
"""
import os
import re
import sys
import subprocess
import urllib.parse
from difflib import SequenceMatcher

import brain
import promemoria

# Importa pc_index per apertura unificata e fallback app web
try:
    import pc_index
except ImportError:
    import importlib.util as _ilu
    _spec = _ilu.spec_from_file_location(
        "pc_index", os.path.join(os.path.dirname(__file__), "pc_index.py"))
    pc_index = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(pc_index)


def _desktop():
    home = os.path.expanduser("~")
    d = os.path.join(home, "Desktop")
    return d if os.path.isdir(d) else home


def _apri_url(url):
    """Apre un URL usando pc_index (cross-platform)."""
    return pc_index.apri_percorso(url)


# ---------------------------------------------------------------- APRI SITO
_SITI = {
    # Istituzionali
    "agenzia delle entrate": "https://www.agenziaentrate.gov.it",
    "agenzia entrate": "https://www.agenziaentrate.gov.it",
    "inps": "https://www.inps.it", "poste": "https://www.poste.it",
    "inail": "https://www.inail.it",
    "agenzia dogane": "https://www.adm.gov.it",
    "camera di commercio": "https://www.registroimprese.it",
    "pec": "https://www.pec.it",
    # Email e produttivita'
    "gmail": "https://mail.google.com", "google": "https://www.google.com",
    "google drive": "https://drive.google.com",
    "google maps": "https://maps.google.com",
    "outlook": "https://outlook.live.com",
    # Social e messaggistica
    "youtube": "https://www.youtube.com", "amazon": "https://www.amazon.it",
    "facebook": "https://www.facebook.com", "instagram": "https://www.instagram.com",
    "linkedin": "https://www.linkedin.com",
    "twitter": "https://www.x.com", "x": "https://www.x.com",
    "tiktok": "https://www.tiktok.com",
    "whatsapp": "https://web.whatsapp.com",
    "web whatsapp": "https://web.whatsapp.com",
    "telegram": "https://web.telegram.org",
    "web telegram": "https://web.telegram.org",
    # E-commerce
    "ebay": "https://www.ebay.it",
    "subito": "https://www.subito.it",
    "aliexpress": "https://www.aliexpress.com",
    "zalando": "https://www.zalando.it",
    "mediaworld": "https://www.mediaworld.it",
    "unieuro": "https://www.unieuro.it",
    # Viaggi
    "booking": "https://www.booking.com",
    "trenitalia": "https://www.trenitalia.com", "italo": "https://www.italotreno.it",
    "ita airways": "https://www.ita-airways.com", "alitalia": "https://www.ita-airways.com",
    "ryanair": "https://www.ryanair.com", "skyscanner": "https://www.skyscanner.it",
    "airbnb": "https://www.airbnb.it",
    "trivago": "https://www.trivago.it",
    # Sport
    "as roma": "https://www.asroma.com", "roma": "https://www.asroma.com",
    "asroma": "https://www.asroma.com",
    "lazio": "https://www.sslazio.it",
    "juventus": "https://www.juventus.com", "juve": "https://www.juventus.com",
    "milan": "https://www.acmilan.com", "inter": "https://www.inter.it",
    "napoli": "https://www.sscnapoli.it",
    "gazzetta": "https://www.gazzetta.it",
    "corriere dello sport": "https://www.corrieredellosport.it",
    # Notizie
    "corriere": "https://www.corriere.it",
    "repubblica": "https://www.repubblica.it",
    "ansa": "https://www.ansa.it",
    "il sole 24 ore": "https://www.ilsole24ore.com",
    # Altro
    "wikipedia": "https://it.wikipedia.org",
    "netflix": "https://www.netflix.com",
    "spotify": "https://open.spotify.com",
    "twitch": "https://www.twitch.tv",
    "chatgpt": "https://chat.openai.com",
    "claude": "https://claude.ai",
}

# Alias per errori comuni di Whisper (trascrizioni sbagliate)
_ALIAS_WHISPER = {
    "webwhatpp": "whatsapp", "webwhatapp": "whatsapp", "web whatpp": "whatsapp",
    "web whatapp": "whatsapp", "watsapp": "whatsapp", "wazzap": "whatsapp",
    "whattsapp": "whatsapp", "whats app": "whatsapp",
    "as roma": "asroma", "a s roma": "asroma", "la roma": "asroma",
    "you tube": "youtube", "u tube": "youtube",
    "face book": "facebook", "feisbuk": "facebook",
    "insta gram": "instagram", "instagrem": "instagram",
    "linked in": "linkedin",
    "tik tok": "tiktok",
    "net flix": "netflix",
}


def _correggi_whisper(testo):
    """Corregge errori comuni di trascrizione Whisper."""
    low = testo.lower().strip()
    # Prima prova alias esatti
    if low in _ALIAS_WHISPER:
        return _ALIAS_WHISPER[low]
    # Poi prova contenimento
    for alias, corretto in _ALIAS_WHISPER.items():
        if alias in low:
            return corretto
    return low


def _fuzzy_match_sito(key):
    """Cerca il sito piu' simile con fuzzy matching (per errori Whisper)."""
    miglior_score = 0
    miglior_url = None
    for k, v in _SITI.items():
        score = SequenceMatcher(None, key, k).ratio()
        if score > miglior_score:
            miglior_score = score
            miglior_url = v
    # Accetta solo match con similarita' >= 0.6
    if miglior_score >= 0.6:
        return miglior_url
    return None


def apri_sito(testo):
    n = re.sub(r"^\s*(apri(mi)?\s+(la\s+pagina|il\s+sito|pagina|sito)\s*(di|del|della|dell')?\s*|apri(mi)?\s+su\s+|vai\s+su\s+|portami\s+su\s+|apri(mi)?\s+)",
               "", testo or "", flags=re.I).strip(" .?")
    if not n:
        return "Quale sito apro?"

    # 1. Correggi errori Whisper
    key = _correggi_whisper(n)

    # 2. Cerca match esatto nella mappa siti
    url = None
    for k, v in sorted(_SITI.items(), key=lambda x: -len(x[0])):
        if k in key:
            url = v
            break

    # 3. Se non trovato, prova fuzzy matching nella mappa siti
    if not url:
        url = _fuzzy_match_sito(key)

    # 3b. Prova pc_index (app web: whatsapp, gmail, ecc.)
    if not url:
        info = pc_index.trova_app_smart(key)
        if info and info["type"] == "web":
            url = info["command"]

    # 4. Fallback: costruisci URL
    if not url:
        if "." in key and " " not in key:
            url = key if key.startswith("http") else "https://" + key
        else:
            slug = re.sub(r"[^a-z0-9]", "", key)
            url = f"https://www.{slug}.com"

    _apri_url(url)
    return f"Apro il sito di {n}."


# ---------------------------------------------------------------- VOLUME
def _tasto(code, volte=1):
    import ctypes
    for _ in range(volte):
        ctypes.windll.user32.keybd_event(code, 0, 0, 0)
        ctypes.windll.user32.keybd_event(code, 0, 2, 0)


def volume(testo):
    if not sys.platform.startswith("win"):
        return "Il controllo volume è disponibile su Windows."
    low = (testo or "").lower()
    try:
        if any(k in low for k in ("muto", "silenzia", "zitto", "disattiva audio", "togli audio")):
            _tasto(0xAD)  # mute toggle
            return "Audio disattivato o riattivato."
        if any(k in low for k in ("abbassa", "giù", "giu", "diminuisci", "meno", "piano")):
            _tasto(0xAE, 6)
            return "Volume abbassato."
        _tasto(0xAF, 6)
        return "Volume alzato."
    except Exception as e:
        print(f"[volume] errore: {e}")
        return "Non riesco a cambiare il volume."


# ---------------------------------------------------------------- SCREENSHOT
def screenshot():
    try:
        from PIL import ImageGrab
    except Exception:
        return "Per lo screenshot manca la libreria Pillow. Installa: pip install pillow."
    import datetime
    try:
        img = ImageGrab.grab()
        path = os.path.join(_desktop(), "Screenshot_" + datetime.datetime.now().strftime("%d-%m_%H%M%S") + ".png")
        img.save(path)
        _apri_url(path)
        return "Screenshot salvato sul Desktop."
    except Exception as e:
        print(f"[screenshot] errore: {e}")
        return "Non riesco a fare lo screenshot."


# ---------------------------------------------------------------- SISTEMA
def blocca_pc():
    try:
        if sys.platform.startswith("win"):
            import ctypes
            ctypes.windll.user32.LockWorkStation()
            return "Computer bloccato."
        return "Blocco schermo disponibile su Windows."
    except Exception as e:
        print(f"[blocca] errore: {e}")
        return "Non riesco a bloccare il computer."


def spegni_pc():
    if not sys.platform.startswith("win"):
        return "Lo spegnimento è gestito su Windows."
    try:
        subprocess.run("shutdown /s /t 60", shell=True)
        return "Spengo il computer tra un minuto. Di' 'annulla spegnimento' per fermare."
    except Exception as e:
        print(f"[spegni] errore: {e}")
        return "Non riesco a spegnere il computer."


def riavvia_pc():
    if not sys.platform.startswith("win"):
        return "Il riavvio è gestito su Windows."
    try:
        subprocess.run("shutdown /r /t 60", shell=True)
        return "Riavvio il computer tra un minuto. Di' 'annulla spegnimento' per fermare."
    except Exception as e:
        return "Non riesco a riavviare il computer."


def annulla_spegnimento():
    if not sys.platform.startswith("win"):
        return "Niente da annullare."
    try:
        subprocess.run("shutdown /a", shell=True)
        return "Spegnimento annullato."
    except Exception:
        return "Non c'era nessuno spegnimento in corso."


# ---------------------------------------------------------------- WHATSAPP
def _numero_internazionale(num):
    n = re.sub(r"\D", "", num or "")
    if len(n) == 10 and n.startswith("3"):
        return "39" + n     # cellulare italiano
    return n


def manda_whatsapp(testo, brain_cfg):
    """Apre WhatsApp con il messaggio pronto (numero preso dalla rubrica o dettato)."""
    sys_p = ("Estrai da questa frase il destinatario e il messaggio per WhatsApp, in JSON: "
             "{\"nome\": \"...\", \"messaggio\": \"...\"}. Rispondi SOLO con il JSON.")
    import json
    out = brain.chat_libero(sys_p, testo, brain_cfg)
    nome, messaggio = "", ""
    m = re.search(r"\{.*\}", out, re.S)
    if m:
        try:
            d = json.loads(m.group(0))
            nome = d.get("nome", "")
            messaggio = d.get("messaggio", "")
        except Exception:
            pass
    if not nome:
        return "A chi devo mandare il messaggio?"
    # numero: dalla rubrica, oppure se 'nome' è già un numero
    numero = re.sub(r"\D", "", nome)
    if not numero:
        rub = promemoria._carica_json("rubrica_atlas.json", {})
        c = rub.get(nome.lower())
        if not c:
            for k, v in rub.items():
                if nome.lower() in k or k in nome.lower():
                    c = v
                    break
        if not c:
            return f"Non ho {nome} in rubrica. Salvalo prima con: salva il numero di {nome}."
        numero = c["numero"]
    numero = _numero_internazionale(numero)
    url = "https://wa.me/" + numero
    if messaggio:
        url += "?text=" + urllib.parse.quote(messaggio)
    _apri_url(url)
    return f"Ho aperto WhatsApp per {nome}. Premi invio per inviare."
