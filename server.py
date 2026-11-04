"""
server.py - Atlas Cloud Server per Render.

FastAPI + WebSocket. Architettura ispirata a AIVoice (manxlr/AIVoice).
Importa brain.py per il LLM (Groq), edge-tts per la voce,
Groq Whisper per la trascrizione audio.

Protocollo WebSocket:
  Client -> Server:  {"type":"text","text":"..."} oppure {"type":"audio","data":"<base64 wav>"}
  Server -> Client:  {"type":"state","state":"thinking|speaking|idle"}
                     {"type":"transcript","text":"..."}
                     {"type":"response","text":"...","audio":"<base64 mp3>"}

Start: uvicorn server:app --host 0.0.0.0 --port 10000
"""
import os
import sys
import json
import re
import base64
import asyncio
import tempfile
import datetime
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles

# --- Carica .env se presente ---
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

# --- Importa il cervello (funziona su Linux) ---
import brain

# ======================================================================
# CONFIGURAZIONE DA ENVIRONMENT (niente config.json sul server)
# ======================================================================
NOME_ASSISTENTE = os.getenv("ATLAS_NAME", "Atlas").lower()
VOCE_DEFAULT = os.getenv("ATLAS_VOICE", "it-IT-DiegoNeural")
CITTA_DEFAULT = os.getenv("ATLAS_CITY", "Roma")
LAT_DEFAULT = float(os.getenv("ATLAS_LAT", "41.90"))
LON_DEFAULT = float(os.getenv("ATLAS_LON", "12.50"))

# Cervello VELOCE per classificazione intent (JSON corto, serve velocita')
BRAIN_CFG = {
    "provider": "groq",
    "api_key_env": "GROQ_API_KEY",
    "base_url": os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1"),
    "model": os.getenv("GROQ_MODEL_FAST", "meta-llama/llama-4-scout-17b-16e-instruct"),
    "temperature": 0.1,
    "max_tokens": 250,
    "stt_model": os.getenv("GROQ_STT_MODEL", "whisper-large-v3-turbo"),
}

# Cervello SMART per conversazione libera e risposte complesse
BRAIN_SMART_CFG = {
    "provider": "groq",
    "api_key_env": "GROQ_API_KEY",
    "base_url": os.getenv("GROQ_BASE_URL", "https://api.groq.com/openai/v1"),
    "model": os.getenv("GROQ_MODEL_SMART", "llama-3.3-70b-versatile"),
    "temperature": 0.3,
}

# ======================================================================
# SKILL CLOUD: solo quelle che funzionano senza PC locale
# ======================================================================
SKILLS_CLOUD = [
    "meteo", "mercati", "briefing", "analisi_titolo", "notizie",
    "calcolo", "ricerca_web", "definizione", "traduci", "timer",
    "conversazione_generica", "nessuna",
]

SKILLS_PC_ONLY = [
    "apri_programma", "apri_cartella", "cerca_file", "apri_file",
    "crea_excel", "crea_word", "crea_pdf", "aggiungi_dati", "apri_documento",
    "volume", "screenshot", "blocca_pc", "spegni_pc", "riavvia_pc",
    "annulla_spegnimento", "whatsapp", "naviga_web", "cerca_pagina",
    "compila_form", "crea_cartella", "rinomina_cartella", "cerca_video",
    "cerca_musica", "apri_sito", "crea_preventivo",
    "crea_appuntamento", "agenda", "promemoria", "lista_promemoria",
    "completa_promemoria", "prendi_nota", "leggi_note", "crea_nota",
    "salva_contatto", "trova_contatto", "chiama_contatto",
    "riassumi", "mappa",
]

ALL_SKILLS = SKILLS_CLOUD + SKILLS_PC_ONLY

# Schema JSON per intent classification (come jarvis.py)
SCHEMA_RIGIDO = {
    "type": "object",
    "properties": {
        "wake_word_detected": {"type": "boolean"},
        "skill_identificata": {"type": "string", "enum": ALL_SKILLS},
        "stato_flusso": {"type": "string", "enum": ["immediato", "in_corso", "completato"]},
        "parametri": {
            "type": "object",
            "properties": {
                "target": {"type": "string"},
                "vecchio_nome": {"type": "string"},
                "nuovo_nome": {"type": "string"},
            },
        },
        "risposta_vocale": {"type": "string"},
    },
    "required": ["wake_word_detected", "skill_identificata", "stato_flusso", "parametri", "risposta_vocale"],
}

# System prompt per il classificatore di intent (versione cloud)
SYSTEM_PROMPT = (
    f"Tu sei il core esecutivo di ATLAS, un assistente vocale intelligente. "
    f"Il nome di attivazione e': '{NOME_ASSISTENTE}'. "
    f"Regole: 1. Comportati SOLO come un Intent Classifier. "
    f"2. Se l'utente chiede l'andamento di borse, indici azionari o mercati, usa 'mercati'. "
    f"6. Se l'utente saluta la mattina o chiede un riepilogo/notiziario della giornata, usa 'briefing'. "
    f"7. Se chiede PREZZO, QUOTAZIONE, VALORE di un TITOLO/azione/criptovaluta, usa 'analisi_titolo' con il nome in parametri.target. "
    f"8. Se chiede le notizie o cosa succede nel mondo, usa 'notizie'; se c'e' un argomento specifico mettilo in parametri.target. "
    f"14. Se chiede che tempo fa, usa 'meteo'; se nomina una citta', mettila in parametri.target. "
    f"30. Se chiede un CALCOLO (IVA, cambio valuta, percentuali, aritmetica), usa 'calcolo'. "
    f"31. Se chiede di CERCARE sul web informazioni, usa 'ricerca_web' col testo in parametri.target. "
    f"32. Se chiede CHI E' o COS'E' qualcosa, usa 'definizione' col termine in parametri.target. "
    f"12. Se chiede di TRADURRE qualcosa, usa 'traduci'. "
    f"15. Per QUALSIASI altra domanda o chiacchiera, usa 'conversazione_generica'. "
    f"Elenco completo delle skill permesse: {', '.join(ALL_SKILLS)}."
)

# ======================================================================
# FUNZIONI DATI (estratte da jarvis.py — funzionano su Linux)
# ======================================================================
_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# --- Notizie (Google News RSS) ---
def recupera_notizie(quante=2, argomento=None):
    try:
        if argomento:
            q = urllib.parse.quote(argomento)
            url = f"https://news.google.com/rss/search?q={q}&hl=it&gl=IT&ceid=IT:it"
        else:
            url = "https://news.google.com/rss?hl=it&gl=IT&ceid=IT:it"
        req = urllib.request.Request(url, headers=_HEADERS)
        with urllib.request.urlopen(req, timeout=6) as response:
            xml_content = response.read().decode("utf-8")
        root = ET.fromstring(xml_content)
        titoli = []
        for item in root.iter("item"):
            t = item.findtext("title") or ""
            if " - " in t:
                t = t.rsplit(" - ", 1)[0]
            t = t.strip()
            if t:
                titoli.append(t)
            if len(titoli) >= quante:
                break
        return titoli
    except Exception:
        return []

# --- Mercati (Yahoo Finance) ---
INDICI_MAPPA = {
    "FTSE MIB": "FTSEMIB.MI", "S&P 500": "%5EGSPC",
    "DAX": "%5EGDAXI", "Nikkei 225": "%5EN225",
}
INDICI_VOCE = {
    "FTSE MIB": "Milano", "S&P 500": "Wall Street",
    "DAX": "Francoforte", "Nikkei 225": "Tokyo",
}

def _dati_mercati():
    risultati = {}
    for nome, ticker in INDICI_MAPPA.items():
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
            req = urllib.request.Request(url, headers=_HEADERS)
            with urllib.request.urlopen(req, timeout=5) as response:
                meta = json.loads(response.read().decode("utf-8"))["chart"]["result"][0]["meta"]
            prezzo = meta.get("regularMarketPrice")
            prec = meta.get("chartPreviousClose") or meta.get("previousClose")
            pct = ((prezzo - prec) / prec * 100.0) if (prezzo and prec) else None
            risultati[nome] = (prezzo, pct)
        except Exception:
            risultati[nome] = (None, None)
    return risultati

def _fmt_prezzo(prezzo):
    return f"{prezzo:,.2f}" if prezzo is not None else "n.d."

def _fmt_pct_voce(pct):
    if pct is None:
        return "dato non disponibile"
    verso = "in rialzo" if pct >= 0 else "in calo"
    return f"{verso} dello {abs(pct):.1f} per cento"

def frase_mercati(dati):
    pezzi = []
    for nome, (prezzo, pct) in dati.items():
        piazza = INDICI_VOCE.get(nome, nome)
        pezzi.append(f"{piazza} {_fmt_pct_voce(pct)}")
    return "Sui mercati: " + "; ".join(pezzi) + "."

def tabellone_mercati(dati):
    righe = ["--- TABELLONE MERCATI GLOBALI ---"]
    bandiere = {"FTSE MIB": "IT", "S&P 500": "US", "DAX": "DE", "Nikkei 225": "JP"}
    for nome, (prezzo, pct) in dati.items():
        seg = ""
        if pct is not None:
            seg = f"  ({'+' if pct >= 0 else ''}{pct:.2f}%)"
        righe.append(f"[{bandiere.get(nome, '')}] {nome} ({INDICI_VOCE.get(nome, '')}): {_fmt_prezzo(prezzo)} punti{seg}")
    return "\n".join(righe)

# --- Meteo (Open-Meteo, gratis) ---
_METEO_TESTI = {
    0: "sereno", 1: "prevalentemente sereno", 2: "parzialmente nuvoloso", 3: "nuvoloso",
    45: "nebbia", 48: "nebbia", 51: "pioggerella", 53: "pioggerella", 55: "pioggerella",
    61: "pioggia leggera", 63: "pioggia", 65: "pioggia forte",
    71: "neve leggera", 73: "neve", 75: "neve forte",
    80: "rovesci", 81: "rovesci", 82: "rovesci forti",
    95: "temporale", 96: "temporale", 99: "temporale",
}

def _geocoding(citta):
    if not citta:
        return None, None, None
    try:
        url = (
            "https://geocoding-api.open-meteo.com/v1/search"
            f"?name={urllib.parse.quote(citta.strip())}&count=1&language=it&format=json"
        )
        req = urllib.request.Request(url, headers=_HEADERS)
        with urllib.request.urlopen(req, timeout=5) as response:
            dati = json.loads(response.read().decode("utf-8"))
        r = (dati.get("results") or [None])[0]
        if not r:
            return None, None, None
        return r.get("latitude"), r.get("longitude"), r.get("name", citta)
    except Exception:
        return None, None, None

def _meteo_attuale(lat=None, lon=None, citta=None):
    if lat is None or lon is None:
        lat, lon = LAT_DEFAULT, LON_DEFAULT
        if citta is None:
            citta = CITTA_DEFAULT
    try:
        url = (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={lon}"
            "&current=temperature_2m,weather_code&timezone=auto"
        )
        req = urllib.request.Request(url, headers=_HEADERS)
        with urllib.request.urlopen(req, timeout=8) as response:
            cur = json.loads(response.read().decode("utf-8"))["current"]
        temp = round(cur.get("temperature_2m"))
        desc = _METEO_TESTI.get(cur.get("weather_code"), "variabile")
        return temp, desc
    except Exception:
        pass
    # fallback wttr.in
    if citta:
        try:
            url = f"https://wttr.in/{urllib.parse.quote(citta.strip())}?format=j1&lang=it"
            req = urllib.request.Request(url, headers=_HEADERS)
            with urllib.request.urlopen(req, timeout=8) as response:
                cc = json.loads(response.read().decode("utf-8"))["current_condition"][0]
            temp = round(float(cc.get("temp_C")))
            desc = (cc.get("lang_it", [{}])[0].get("value") or "variabile").lower()
            return temp, desc
        except Exception:
            pass
    return None, None

# --- Data in italiano ---
_GIORNI = ["lunedi", "martedi", "mercoledi", "giovedi", "venerdi", "sabato", "domenica"]
_MESI = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
         "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"]

def _data_oggi_it():
    oggi = datetime.date.today()
    return f"{_GIORNI[oggi.weekday()]} {oggi.day} {_MESI[oggi.month - 1]}"

# --- Briefing ---
def briefing_vocale():
    citta = CITTA_DEFAULT
    temp, cielo = _meteo_attuale()
    dati = _dati_mercati()
    saluto = f"Buongiorno. Oggi e' {_data_oggi_it()}."
    if temp is not None:
        meteo_txt = f" A {citta} ci sono {temp} gradi, cielo {cielo}."
    else:
        meteo_txt = ""
    testo = saluto + meteo_txt + " " + frase_mercati(dati)
    titoli = recupera_notizie(2)
    if titoli:
        testo += " Tra le notizie principali: " + ". ".join(titoli) + "."
    return testo

# --- Calcolo (IVA, percentuali, aritmetica) ---
def _esegui_calcolo(testo):
    """Calcoli base: IVA, percentuali, aritmetica semplice."""
    t = (testo or "").lower()
    # IVA
    m = re.search(r"(\d[\d.,]*)\s*(piu|più|\+)\s*iva", t)
    if m:
        val = float(m.group(1).replace(".", "").replace(",", "."))
        return f"{val:.2f} + IVA 22% = {val * 1.22:.2f} euro."
    m = re.search(r"scorpora.*?(\d[\d.,]*)", t)
    if m:
        val = float(m.group(1).replace(".", "").replace(",", "."))
        netto = val / 1.22
        return f"Scorporando l'IVA da {val:.2f}: netto {netto:.2f}, IVA {val - netto:.2f}."
    # Percentuale
    m = re.search(r"(\d[\d.,]*)\s*%\s*di\s*(\d[\d.,]*)", t)
    if m:
        pct = float(m.group(1).replace(",", "."))
        base = float(m.group(2).replace(".", "").replace(",", "."))
        return f"Il {pct}% di {base:.2f} e' {base * pct / 100:.2f}."
    # Aritmetica semplice via eval (sicuro: solo cifre e operatori)
    espressione = re.sub(r"[^\d+\-*/().,%]", " ", t)
    espressione = espressione.replace(",", ".").replace("%", "/100")
    espressione = re.sub(r"\s+", "", espressione)
    if espressione and re.match(r"^[\d+\-*/().]+$", espressione):
        try:
            risultato = eval(espressione)
            return f"Il risultato e' {risultato:g}."
        except Exception:
            pass
    return "Non riesco a fare questo calcolo. Prova a riformulare."


# ======================================================================
# STT (Groq Whisper) e TTS (Edge-TTS) — lato server
# ======================================================================
def _pulisci_per_voce(testo):
    if not testo:
        return ""
    t = testo
    t = re.sub(r"\([^)]*\)", "", t)
    t = t.replace("*", "").replace("#", "").replace("`", "").replace("_", " ")
    t = re.sub(r"^\s*[-•]\s*", "", t, flags=re.MULTILINE)
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{2,}", "\n", t)
    return t.strip()

async def sintetizza_voce(testo, voce=None):
    """Edge-TTS: testo -> bytes MP3."""
    testo = _pulisci_per_voce(testo)
    if not testo:
        return None
    import edge_tts
    voce = voce or VOCE_DEFAULT
    percorso = tempfile.mktemp(suffix=".mp3")
    try:
        com = edge_tts.Communicate(testo, voce)
        await com.save(percorso)
        with open(percorso, "rb") as f:
            audio_bytes = f.read()
        return audio_bytes
    except Exception as e:
        print(f"[TTS] Errore: {e}")
        return None
    finally:
        try:
            os.remove(percorso)
        except Exception:
            pass

def trascrivi_audio(audio_bytes):
    """Groq Whisper: bytes WAV -> testo."""
    from openai import OpenAI
    api_key = os.getenv(BRAIN_CFG.get("api_key_env", "GROQ_API_KEY"))
    if not api_key:
        return ""
    client = OpenAI(api_key=api_key, base_url=BRAIN_CFG.get("base_url"))
    percorso = tempfile.mktemp(suffix=".wav")
    try:
        with open(percorso, "wb") as f:
            f.write(audio_bytes)
        with open(percorso, "rb") as f:
            guida = ("desktop, cartella, mercati, borsa, titolo, azione, "
                     "Apple, Microsoft, Tesla, bitcoin, notiziario, buongiorno")
            r = client.audio.transcriptions.create(
                model=BRAIN_CFG.get("stt_model", "whisper-large-v3-turbo"),
                file=f,
                language="it",
                prompt=guida,
                temperature=0.0,
            )
        return (r.text or "").strip()
    except Exception as e:
        print(f"[STT] Errore: {e}")
        return ""
    finally:
        try:
            os.remove(percorso)
        except Exception:
            pass


# ======================================================================
# ROUTER SKILL (versione cloud)
# ======================================================================
def processa_comando(testo_utente):
    """Classifica l'intent e esegue la skill. Ritorna il testo della risposta."""
    if not testo_utente or not testo_utente.strip():
        return "Non ho capito, puoi ripetere?"

    # Classifica con il cervello
    json_intent = brain.interroga(SYSTEM_PROMPT, testo_utente, SCHEMA_RIGIDO, BRAIN_CFG)

    if "error" in json_intent:
        return json_intent["error"]

    skill = json_intent.get("skill_identificata", "conversazione_generica")
    parametri = json_intent.get("parametri", {})
    target = parametri.get("target", "").strip()
    risposta_modello = json_intent.get("risposta_vocale", "")

    # --- Skill cloud ---
    if skill == "briefing":
        return briefing_vocale()

    elif skill == "mercati":
        dati = _dati_mercati()
        voce_txt = frase_mercati(dati)
        tabella = tabellone_mercati(dati)
        return tabella + "\n\n" + voce_txt

    elif skill == "meteo":
        if target:
            lat, lon, nome = _geocoding(target)
            if lat:
                temp, desc = _meteo_attuale(lat, lon, target)
                citta = nome or target
            else:
                return f"Non trovo la citta' {target}."
        else:
            temp, desc = _meteo_attuale()
            citta = CITTA_DEFAULT
        if temp is not None:
            return f"A {citta} ci sono {temp} gradi, cielo {desc}."
        return f"Non riesco a recuperare il meteo per {citta}."

    elif skill == "notizie":
        titoli = recupera_notizie(4, target or None)
        if titoli:
            return "Ecco le ultime notizie: " + ". ".join(titoli) + "."
        return "Non riesco a recuperare le notizie al momento."

    elif skill == "analisi_titolo":
        # Usa chat_libero per un commento sui dati
        if target:
            prompt_analisi = (
                f"Sei un analista finanziario italiano. L'utente chiede di '{target}'. "
                f"Dai una risposta breve e utile su questo titolo/criptovaluta. "
                f"Se conosci il ticker, menziona il nome completo. Rispondi in italiano."
            )
            risposta = brain.chat_libero(prompt_analisi, testo_utente, BRAIN_SMART_CFG)
            return risposta
        return risposta_modello or "Dimmi quale titolo vuoi analizzare."

    elif skill == "calcolo":
        return _esegui_calcolo(testo_utente)

    elif skill == "ricerca_web":
        # In cloud non abbiamo browser-use, usiamo chat_libero
        prompt_web = (
            "Sei un assistente italiano. L'utente chiede informazioni. "
            "Rispondi con quello che sai, in modo conciso e utile. "
            "Se non sei sicuro, dillo chiaramente."
        )
        return brain.chat_libero(prompt_web, testo_utente, BRAIN_SMART_CFG)

    elif skill == "definizione":
        prompt_def = (
            "Sei un'enciclopedia italiana parlante. Dai una definizione chiara e concisa "
            "in 2-3 frasi. Rispondi in italiano."
        )
        return brain.chat_libero(prompt_def, testo_utente, BRAIN_SMART_CFG)

    elif skill == "traduci":
        prompt_trad = (
            "Sei un traduttore professionale. Traduci quello che l'utente chiede, "
            "specificando la lingua di partenza e di arrivo. Rispondi in modo chiaro."
        )
        return brain.chat_libero(prompt_trad, testo_utente, BRAIN_SMART_CFG)

    elif skill == "conversazione_generica":
        prompt_conv = (
            f"Sei {NOME_ASSISTENTE.capitalize()}, un assistente vocale italiano simpatico e competente. "
            f"Rispondi in modo naturale, breve e utile. Rispondi in italiano."
        )
        return brain.chat_libero(prompt_conv, testo_utente, BRAIN_SMART_CFG)

    elif skill in SKILLS_PC_ONLY:
        return (
            f"La funzione '{skill}' e' disponibile solo dalla versione desktop di Atlas. "
            f"Dal cloud posso aiutarti con: meteo, mercati, notizie, briefing, calcoli, "
            f"traduzioni, definizioni e conversazione."
        )

    # Fallback
    return risposta_modello or "Non ho capito, puoi ripetere?"


# ======================================================================
# FASTAPI APP
# ======================================================================
app = FastAPI(title="Atlas Cloud", version="1.0.0")

# Serve la cartella static/ per il client web
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(STATIC_DIR, exist_ok=True)


@app.get("/")
async def index():
    """Serve il client web (PWA)."""
    index_path = os.path.join(STATIC_DIR, "index.html")
    if os.path.exists(index_path):
        return FileResponse(index_path, media_type="text/html")
    return HTMLResponse("<h1>Atlas Cloud</h1><p>Client web non trovato. Metti index.html in static/</p>")


@app.get("/health")
async def health():
    """Endpoint per il health check di Render."""
    api_key = os.getenv("GROQ_API_KEY")
    return {
        "status": "ok",
        "assistant": NOME_ASSISTENTE,
        "brain": BRAIN_CFG.get("model"),
        "groq_key_set": bool(api_key),
    }


@app.websocket("/ws")
async def websocket_endpoint(ws: WebSocket):
    await ws.accept()
    print("[WS] Client connesso")

    try:
        while True:
            data = await ws.receive_text()
            msg = json.loads(data)
            msg_type = msg.get("type", "")

            if msg_type == "text":
                testo = msg.get("text", "").strip()
                if not testo:
                    continue

                # Stato: pensando
                await ws.send_text(json.dumps({"type": "state", "state": "thinking"}))

                # Processa il comando
                risposta = await asyncio.to_thread(processa_comando, testo)

                # Manda SUBITO il testo (il client lo mostra immediatamente)
                await ws.send_text(json.dumps({
                    "type": "response",
                    "text": risposta,
                    "audio": None,
                }))

                # Poi genera e manda l'audio separatamente
                await ws.send_text(json.dumps({"type": "state", "state": "speaking"}))
                audio_bytes = await sintetizza_voce(risposta)
                if audio_bytes:
                    audio_b64 = base64.b64encode(audio_bytes).decode()
                    await ws.send_text(json.dumps({
                        "type": "audio",
                        "data": audio_b64,
                    }))

                # Stato: idle
                await ws.send_text(json.dumps({"type": "state", "state": "idle"}))

            elif msg_type == "audio":
                audio_b64 = msg.get("data", "")
                if not audio_b64:
                    continue

                # Stato: pensando
                await ws.send_text(json.dumps({"type": "state", "state": "thinking"}))

                # Trascrivi
                audio_bytes = base64.b64decode(audio_b64)
                testo = await asyncio.to_thread(trascrivi_audio, audio_bytes)

                if not testo:
                    await ws.send_text(json.dumps({
                        "type": "response",
                        "text": "Non ho capito, puoi ripetere?",
                        "audio": None,
                    }))
                    await ws.send_text(json.dumps({"type": "state", "state": "idle"}))
                    continue

                # Invia la trascrizione
                await ws.send_text(json.dumps({"type": "transcript", "text": testo}))

                # Processa
                risposta = await asyncio.to_thread(processa_comando, testo)

                # Manda SUBITO il testo
                await ws.send_text(json.dumps({
                    "type": "response",
                    "text": risposta,
                    "audio": None,
                }))

                # Poi genera e manda l'audio separatamente
                await ws.send_text(json.dumps({"type": "state", "state": "speaking"}))
                audio_out = await sintetizza_voce(risposta)
                if audio_out:
                    audio_out_b64 = base64.b64encode(audio_out).decode()
                    await ws.send_text(json.dumps({
                        "type": "audio",
                        "data": audio_out_b64,
                    }))
                await ws.send_text(json.dumps({"type": "state", "state": "idle"}))

            elif msg_type == "ping":
                await ws.send_text(json.dumps({"type": "pong"}))

    except WebSocketDisconnect:
        print("[WS] Client disconnesso")
    except Exception as e:
        print(f"[WS] Errore: {e}")
        try:
            await ws.close()
        except Exception:
            pass


# Mount static DOPO le route (cosi' / non viene sovrascritto)
if os.path.isdir(STATIC_DIR):
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
