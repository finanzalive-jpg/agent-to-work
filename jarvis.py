import os
import sys
import json
import re
import threading
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

# Cervello INTERCAMBIABILE: cloud (Groq) oppure locale (Ollama).
# Si sceglie in config.json -> "brain" -> "provider". Vedi brain.py.
import brain
import web_tools
import documenti
import foglio
import calendario
import google_cal
import promemoria
import calcoli
import web_info
import controllo_pc
import voce
import navigazione
import datetime

# 1. SCANSIONE DINAMICA DELLE SKILL PRESENTI NELLA CARTELLA
def recupera_skills_locali():
    cartella = os.path.join(os.path.dirname(__file__), "skills")
    # Skill fisse di base riconosciute dall'orchestratore
    skills_rilevate = ["crea_cartella", "rinomina_cartella", "crea_preventivo", "meteo", "cerca_video", "cerca_musica", "mercati", "briefing", "analisi_titolo", "notizie", "apri_programma", "apri_cartella", "cerca_file", "apri_file", "crea_excel", "crea_word", "crea_pdf", "aggiungi_dati", "apri_documento", "crea_appuntamento", "agenda", "promemoria", "lista_promemoria", "completa_promemoria", "prendi_nota", "leggi_note", "salva_contatto", "trova_contatto", "timer", "calcolo", "crea_nota", "ricerca_web", "definizione", "riassumi", "mappa", "apri_sito", "volume", "screenshot", "blocca_pc", "spegni_pc", "riavvia_pc", "annulla_spegnimento", "whatsapp", "traduci", "chiama_contatto", "naviga_web", "cerca_pagina", "compila_form", "conversazione_generica", "nessuna"]
    
    if os.path.exists(cartella):
        for file in os.listdir(cartella):
            if file.endswith(".py") and not file.startswith("__"):
                nome_skill = file[:-3].replace("_skills", "")
                if nome_skill not in skills_rilevate:
                    skills_rilevate.append(nome_skill)
    return skills_rilevate

SKILLS_DISPONIBILI = recupera_skills_locali()

# 2. Carichiamo la configurazione hardware salvata da install.py
if not os.path.exists("config.json"):
    print("[X] Errore: Esegui prima 'python install.py' per configurare il sistema.")
    sys.exit(1)

with open("config.json", "r") as f:
    config = json.load(f)

NOME_ASSISTENTE = config.get("assistant_name", "Atlas").lower()
MODELLO = config.get("model_in_use", "qwen2.5:3b-instruct-q4_K_M")
CONTESTO = config.get("num_ctx", 2048)

# Configurazione del cervello. Se manca in config.json, si parte in LOCALE (Ollama)
# usando il modello scelto dall'hardware, cosi' il vecchio comportamento resta invariato.
BRAIN_CFG = config.get("brain", {
    "provider": "ollama",
    "ollama_model": MODELLO,
    "ollama_host": "http://127.0.0.1:11434",
    "num_ctx": CONTESTO,
    "temperature": 0.1,
})
# Se la config non lo specifica, allineiamo il cervello locale al modello/contesto scelti.
BRAIN_CFG.setdefault("ollama_model", MODELLO)
BRAIN_CFG.setdefault("num_ctx", CONTESTO)

# Importiamo i moduli di Jarvis dalle sotto-cartelle
try:
    from skills.system_skills import (
        esegui_crea_cartella, esegui_rinomina_cartella, esegui_apri_browser,
        esegui_apri_programma, esegui_apri_cartella, esegui_cerca_file, esegui_apri_file,
        apri_percorso,
    )
    import pc_index
    from skills.office_skills import esegui_crea_preventivo_word
except ImportError as e:
    print(f"[X] Avviso importazione moduli: {e}")

# 3. Schema JSON nativo e vincolante per Ollama (Dinamico)
SCHEMA_RIGIDO = {
    "type": "object",
    "properties": {
        "wake_word_detected": {"type": "boolean"},
        "skill_identificata": {
            "type": "string",
            "enum": SKILLS_DISPONIBILI
        },
        "stato_flusso": {"type": "string", "enum": ["immediato", "in_corso", "completato"]},
        "parametri": {
            "type": "object",
            "properties": {
                "target": {"type": "string"},
                "vecchio_nome": {"type": "string"},
                "nuovo_nome": {"type": "string"},
                "dati_preventivo": {
                    "type": "object",
                    "properties": {
                        "azienda_mittente": {"type": "string"},
                        "azienda_ricevente": {"type": "string"},
                        "valore": {"type": "string"},
                        "iva": {"type": "string"}
                    }
                }
            }
        },
        "risposta_vocale": {"type": "string"}
    },
    "required": ["wake_word_detected", "skill_identificata", "stato_flusso", "parametri", "risposta_vocale"]
}

# 4. System Prompt per la blindatura logica del modello
SYSTEM_PROMPT = (
    f"Tu sei il core esecutivo di AGENT-TO-WORK, un orchestratore di skill locale. L'utente ti ha configurato con il nome di attivazione: '{NOME_ASSISTENTE}'. "
    f"Regole: 1. Comportati SOLO come un Intent Classifier. 2. Se l'utente chiede l'andamento di borse, indici azionari o mercati, usa 'mercati'. "
    f"3. Se chiede un video o brano su youtube, usa 'cerca_video' e inserisci l'oggetto da cercare in parametri.target. "
    f"4. Se chiede di creare una cartella, usa 'crea_cartella' e inserisci il nome in parametri.target. "
    f"5. Se chiede di rinominare o cambiare nome a una cartella sul desktop, usa 'rinomina_cartella' ed estrai il vecchio nome in parametri.vecchio_nome e il nuovo nome in parametri.nuovo_nome. "
    f"6. Se l'utente saluta la mattina o chiede un riepilogo/notiziario della giornata (es. 'buongiorno', 'dammi il notiziario', 'com'e' la giornata'), usa 'briefing'. "
    f"7. Se chiede PREZZO, QUOTAZIONE, LIVELLI, VALORE o un parere su un TITOLO/azione di borsa o una CRIPTOVALUTA (es. 'che ne pensi di Apple', 'come va Tesla', 'quanto vale bitcoin', 'livelli di bitcoin', 'prezzo ethereum'), usa 'analisi_titolo' e metti il nome in parametri.target. NON usare la ricerca web per i prezzi. "
    f"8. Se chiede le notizie o cosa succede nel mondo (es. 'che notizie ci sono', 'ultime notizie', 'notizie su X'), usa 'notizie'; se c'e' un argomento specifico mettilo in parametri.target, altrimenti lascialo vuoto. "
    f"9. Se chiede di APRIRE un programma del computer (es. 'apri la calcolatrice', 'apri word'), usa 'apri_programma' con il nome in parametri.target. "
    f"10. Se chiede di APRIRE una cartella (es. 'apri i download', 'apri il desktop'), usa 'apri_cartella' con il nome in parametri.target. "
    f"11. Se chiede di CERCARE, TROVARE o MOSTRARE un file (es. 'trova il file preventivo', 'mostrami il documento X'), usa 'cerca_file' con il nome in parametri.target. "
    f"11b. Se chiede di APRIRE o MODIFICARE un file o documento (es. 'apri il documento X', 'modifica il file Y'), usa 'apri_file' con il nome in parametri.target. "
    f"12. Se chiede di TRADURRE qualcosa, usa 'traduci'. "
    f"13. Se chiede musica o una canzone, usa 'cerca_musica' con il titolo in parametri.target. "
    f"14. Se chiede che tempo fa, usa 'meteo'; se nomina una città (es. 'che tempo fa a Milano'), mettila in parametri.target, altrimenti lascialo vuoto. "
    f"16. Se chiede di creare un file/foglio EXCEL, usa 'crea_excel' con il nome in parametri.target. "
    f"17. Se chiede di creare un documento WORD, usa 'crea_word' con il nome in parametri.target. ECCEZIONE: se chiede specificamente un PREVENTIVO (es. 'crea un preventivo', 'fai un preventivo per Mario'), usa 'crea_preventivo' e inserisci i dati in parametri.dati_preventivo (azienda_mittente, azienda_ricevente, valore, iva). Se non ha ancora dato tutti i dati, metti quelli che hai e lascia vuoti gli altri. "
    f"18. Se chiede di creare un PDF, usa 'crea_pdf' con il nome in parametri.target. "
    f"19. Se chiede di AGGIUNGERE, SCRIVERE o INSERIRE dati o testo nel documento appena creato (es. 'aggiungi Mario Rossi partita iva...', 'scrivi che...'), usa 'aggiungi_dati'. "
    f"19b. Se chiede di APRIRE, MOSTRARE o VEDERE il documento che sta compilando (es. 'aprilo', 'fammi vedere', 'ho finito'), usa 'apri_documento'. "
    f"20. Se chiede di FISSARE/CREARE un appuntamento o promemoria (es. 'segna appuntamento domani alle 15 con Mario', 'ricordami riunione lunedì'), usa 'crea_appuntamento'. "
    f"21. Se chiede quali appuntamenti ha (es. 'che appuntamenti ho oggi', 'agenda di domani'), usa 'agenda'. "
    f"22. Se chiede di ricordargli QUALCOSA DA FARE (es. 'ricordami di chiamare il commercialista'), usa 'promemoria'. "
    f"23. Se chiede COSA DEVE FARE o la lista dei promemoria (es. 'cosa devo fare', 'leggimi i promemoria'), usa 'lista_promemoria'. "
    f"24. Se dice di aver FATTO una cosa (es. 'ho fatto X', 'segna come fatto X'), usa 'completa_promemoria'. "
    f"25. Se dice 'prendi nota: ...' / 'annota ...' una cosa SINGOLA e veloce, usa 'prendi_nota'. "
    f"25b. Se vuole APRIRE UN BLOCCO NOTE in cui dettare più cose (es. 'nota per domani', 'note per sabato', 'apri un blocco note spesa'), usa 'crea_nota' col titolo in parametri.target. "
    f"26. Se chiede di leggere le note/appunti, usa 'leggi_note'. "
    f"27. Se chiede di SALVARE un numero/contatto (es. 'salva il numero di Mario 333...'), usa 'salva_contatto'. "
    f"28. Se chiede il NUMERO di un contatto (es. 'qual è il numero di Mario', 'numero di Luigi'), usa 'trova_contatto'. "
    f"29. Se chiede un TIMER o una SVEGLIA tra un certo tempo (es. 'timer di 10 minuti', 'avvisami tra mezz'ora'), usa 'timer'. "
    f"30. Se chiede un CALCOLO: IVA ('1250 più IVA', 'scorpora l'IVA da 1220'), cambio valuta ('quanti dollari sono 1000 euro'), percentuali ('il 15% di 2000') o aritmetica ('1250 per 3'), usa 'calcolo'. "
    f"31. Se chiede di CERCARE sul web informazioni o fatti aggiornati (es. 'cerca sul web chi ha vinto', 'ultime su ...'), usa 'ricerca_web' col testo in parametri.target. "
    f"32. Se chiede CHI È o COS'È qualcosa/qualcuno (es. 'chi è Dante', 'cos'è lo spread'), usa 'definizione' col termine in parametri.target. "
    f"33. Se chiede di RIASSUMERE una pagina o un link, usa 'riassumi'. "
    f"34. Se chiede INDICAZIONI stradali o di mostrare un luogo sulla MAPPA (es. 'come arrivo a Roma', 'dov'è la stazione'), usa 'mappa' col luogo in parametri.target. "
    f"35. Se chiede di APRIRE un SITO o una PAGINA web (es. 'apri il sito di Poste', 'apri la pagina di Amazon', 'vai su Amazon', 'portami su eBay', 'apri Amazon'), usa 'apri_sito' col nome in parametri.target. Vale anche per negozi/compagnie/banche. NON rispondere mai che non puoi aprire siti. "
    f"36. Se chiede di alzare/abbassare il VOLUME o di mettere muto, usa 'volume'. "
    f"37. Se chiede uno SCREENSHOT o una foto dello schermo, usa 'screenshot'. "
    f"38. Se chiede di BLOCCARE lo schermo/il pc, usa 'blocca_pc'. "
    f"39. Se chiede di SPEGNERE il computer usa 'spegni_pc'; di RIAVVIARLO usa 'riavvia_pc'; di ANNULLARE lo spegnimento usa 'annulla_spegnimento'. "
    f"40. Se chiede di mandare un messaggio WHATSAPP (es. 'manda un whatsapp a Mario ...'), usa 'whatsapp'. "
    f"41. Se chiede di NAVIGARE un sito, USARE una pagina web, INTERAGIRE con un sito, COMPRARE qualcosa online, REGISTRARSI, COMPILARE un form online, o fare QUALSIASI cosa che richieda aprire e usare un browser in modo autonomo (es. 'vai su booking e cerca un hotel a Roma', 'naviga su amazon e cerca...', 'compra i biglietti del treno', 'registrami su...'), usa 'naviga_web' col compito completo in parametri.target. "
    f"42. Se chiede di LEGGERE, ESTRARRE o CERCARE informazioni IN una pagina web specifica (es. 'leggi cosa c'è su quella pagina', 'estrai i prezzi da...', 'cosa dice il sito X'), usa 'cerca_pagina' con l'URL o il sito in parametri.target. "
    f"43. Se chiede di COMPILARE un MODULO o FORM su un sito specifico (es. 'compila il form di contatto su...'), usa 'compila_form' col sito e le istruzioni in parametri.target. "
    f"15. Per QUALSIASI altra domanda o chiacchiera (cultura, consigli, spiegazioni, domande generiche), usa 'conversazione_generica'. "
    f"Elenco completo delle skill permesse: {', '.join(SKILLS_DISPONIBILI)}."
)

def interroga_assistente(testo_utente):
    # Un solo punto di ingresso: brain.py decide cloud (Groq) o locale (Ollama)
    # e restituisce SEMPRE lo stesso JSON vincolato dallo schema.
    return brain.interroga(SYSTEM_PROMPT, testo_utente, SCHEMA_RIGIDO, BRAIN_CFG)

def recupera_notizie(quante=2, argomento=None):
    """Legge titoli di notizie VERE da Google News (RSS, gratis, senza chiave).
    argomento=None -> prime notizie; argomento='economia mercati' -> cerca quel tema.
    Torna una lista di titoli puliti."""
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
            # Google News mette " - Testata" in fondo: lo togliamo per la lettura
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

def recupera_notizia_globale():
    """Compatibilita': una sola riga di notizia (usata dal tabellone stampato)."""
    titoli = recupera_notizie(1)
    return titoli[0] if titoli else "Nessuna notizia disponibile al momento."

_HEADERS = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}

INDICI_MAPPA = {
    "FTSE MIB": "FTSEMIB.MI",
    "S&P 500": "%5EGSPC",
    "DAX": "%5EGDAXI",
    "Nikkei 225": "%5EN225",
}
# Come leggere a voce ogni indice (piazza finanziaria)
INDICI_VOCE = {
    "FTSE MIB": "Milano",
    "S&P 500": "Wall Street",
    "DAX": "Francoforte",
    "Nikkei 225": "Tokyo",
}

def _dati_mercati():
    """Legge prezzo e variazione % reale di ogni indice da Yahoo. Torna {nome: (prezzo, pct)}."""
    risultati = {}
    for nome, ticker in INDICI_MAPPA.items():
        try:
            url = f"https://query1.finance.yahoo.com/v8/finance/chart/{ticker}"
            req = urllib.request.Request(url, headers=_HEADERS)
            with urllib.request.urlopen(req, timeout=5) as response:
                meta = json.loads(response.read().decode('utf-8'))["chart"]["result"][0]["meta"]
            prezzo = meta.get("regularMarketPrice")
            prec = meta.get("chartPreviousClose") or meta.get("previousClose")
            pct = ((prezzo - prec) / prec * 100.0) if (prezzo is not None and prec) else None
            risultati[nome] = (prezzo, pct)
        except Exception:
            risultati[nome] = (None, None)
    return risultati

def _fmt_prezzo(prezzo):
    return f"{prezzo:,.2f}" if prezzo is not None else "n.d."

def _fmt_pct_voce(pct):
    """Variazione % in parole, per la voce."""
    if pct is None:
        return "dato non disponibile"
    verso = "in rialzo" if pct >= 0 else "in calo"
    return f"{verso} dello {abs(pct):.1f} per cento"

def frase_mercati(dati):
    """Frase parlata sui mercati basata SOLO su dati reali (niente numeri inventati)."""
    pezzi = []
    for nome, (prezzo, pct) in dati.items():
        piazza = INDICI_VOCE.get(nome, nome)
        pezzi.append(f"{piazza} {_fmt_pct_voce(pct)}")
    return "Sui mercati: " + "; ".join(pezzi) + "."

# --- Meteo (open-meteo, gratis, senza chiave) ---
_METEO_TESTI = {
    0: "sereno", 1: "prevalentemente sereno", 2: "parzialmente nuvoloso", 3: "nuvoloso",
    45: "nebbia", 48: "nebbia", 51: "pioggerella", 53: "pioggerella", 55: "pioggerella",
    61: "pioggia leggera", 63: "pioggia", 65: "pioggia forte",
    71: "neve leggera", 73: "neve", 75: "neve forte",
    80: "rovesci", 81: "rovesci", 82: "rovesci forti",
    95: "temporale", 96: "temporale", 99: "temporale",
}

def _geocoding(citta):
    """Trova latitudine/longitudine di una citta' (open-meteo, gratis). Torna (lat, lon, nome) o (None, None, None)."""
    if not citta:
        return None, None, None
    try:
        url = ("https://geocoding-api.open-meteo.com/v1/search"
               f"?name={urllib.parse.quote(citta.strip())}&count=1&language=it&format=json")
        req = urllib.request.Request(url, headers=_HEADERS)
        with urllib.request.urlopen(req, timeout=5) as response:
            dati = json.loads(response.read().decode('utf-8'))
        r = (dati.get("results") or [None])[0]
        if not r:
            return None, None, None
        return r.get("latitude"), r.get("longitude"), r.get("name", citta)
    except Exception:
        return None, None, None

def _meteo_wttr(citta):
    """Riserva meteo via wttr.in (host diverso, utile se open-meteo e' bloccato)."""
    if not citta:
        return None, None
    try:
        url = f"https://wttr.in/{urllib.parse.quote(citta.strip())}?format=j1&lang=it"
        req = urllib.request.Request(url, headers=_HEADERS)
        with urllib.request.urlopen(req, timeout=8) as response:
            cc = json.loads(response.read().decode('utf-8'))["current_condition"][0]
        temp = round(float(cc.get("temp_C")))
        desc = None
        if cc.get("lang_it"):
            desc = cc["lang_it"][0].get("value")
        if not desc and cc.get("weatherDesc"):
            desc = cc["weatherDesc"][0].get("value")
        return temp, (desc or "variabile").lower()
    except Exception as e3:
        print(f"[meteo] riserva wttr fallita: {e3}")
        return None, None

def _meteo_attuale(lat=None, lon=None, citta=None):
    """Temperatura e cielo attuali. Senza coordinate usa la citta' di config. Torna (temp_C, descrizione)."""
    if lat is None or lon is None:
        m = config.get("meteo", {"citta": "Roma", "lat": 41.90, "lon": 12.50})
        lat = m.get("lat", 41.90)
        lon = m.get("lon", 12.50)
        if citta is None:
            citta = m.get("citta", "Roma")
    # Tentativo 1: API nuova (current=...)
    try:
        url = (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={lon}"
            "&current=temperature_2m,weather_code&timezone=auto"
        )
        req = urllib.request.Request(url, headers=_HEADERS)
        with urllib.request.urlopen(req, timeout=8) as response:
            cur = json.loads(response.read().decode('utf-8'))["current"]
        temp = round(cur.get("temperature_2m"))
        desc = _METEO_TESTI.get(cur.get("weather_code"), "variabile")
        return temp, desc
    except Exception as e1:
        print(f"[meteo] tentativo 1 fallito: {e1}")

    # Tentativo 2: API classica (current_weather=true)
    try:
        url = (
            "https://api.open-meteo.com/v1/forecast"
            f"?latitude={lat}&longitude={lon}&current_weather=true&timezone=auto"
        )
        req = urllib.request.Request(url, headers=_HEADERS)
        with urllib.request.urlopen(req, timeout=8) as response:
            cw = json.loads(response.read().decode('utf-8'))["current_weather"]
        temp = round(cw.get("temperature"))
        desc = _METEO_TESTI.get(cw.get("weathercode"), "variabile")
        return temp, desc
    except Exception as e2:
        print(f"[meteo] tentativo 2 fallito: {e2}")

    # Riserva finale: wttr.in (host diverso)
    return _meteo_wttr(citta)

# --- Data di oggi in italiano ---
_GIORNI = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"]
_MESI = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
         "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"]

def _data_oggi_it():
    oggi = datetime.date.today()
    return f"{_GIORNI[oggi.weekday()]} {oggi.day} {_MESI[oggi.month - 1]}"

def briefing_vocale():
    """Il NOTIZIARIO parlato: saluto + data + meteo + mercati, tutto da dati veri."""
    citta = config.get("meteo", {}).get("citta", "Roma")
    temp, cielo = _meteo_attuale()
    dati = _dati_mercati()

    saluto = f"Buongiorno. Oggi è {_data_oggi_it()}."
    if temp is not None:
        meteo_txt = f" A {citta} ci sono {temp} gradi, cielo {cielo}."
    else:
        meteo_txt = ""

    testo = saluto + meteo_txt + " " + frase_mercati(dati)

    # Notizie vere del momento
    titoli = recupera_notizie(2)
    if titoli:
        testo += " Tra le notizie principali: " + ". ".join(titoli) + "."
    return testo

def esegui_lettura_mercati_reali():
    """Tabellone stampato con prezzi VERI e variazione %."""
    dati = _dati_mercati()
    righe = ["--- TABELLONE MERCATI GLOBALI ---"]
    bandiere = {"FTSE MIB": "🇮🇹", "S&P 500": "🇺🇸", "DAX": "🇩🇪", "Nikkei 225": "🇯🇵"}
    for nome, (prezzo, pct) in dati.items():
        seg = ""
        if pct is not None:
            seg = f"  ({'+' if pct >= 0 else ''}{pct:.2f}%)"
        righe.append(f"{bandiere.get(nome, '')} {nome} ({INDICI_VOCE.get(nome, '')}): {_fmt_prezzo(prezzo)} punti{seg}")
    righe.append(f"📰 {recupera_notizia_globale()}")
    return "\n".join(righe)

# ----------------------------------------------------------------------
# CONVERSAZIONE A PIU' BATTUTE per la scelta dei file
# ----------------------------------------------------------------------
_FILE_IN_SOSPESO = []        # candidati dell'ultima ricerca ("quale apro?")
IN_ATTESA_SCELTA = False     # True quando l'assistente aspetta la tua risposta

# Documento su cui stiamo lavorando (per "aggiungi/scrivi" dopo averlo creato)
_DOC_CORRENTE = None         # dict: {"path","tipo","titolo","righe","fase","intestazioni"} oppure None

def _pulisci_prefisso(testo):
    """Toglie i verbi iniziali tipo 'scrivi/aggiungi/inserisci' dal testo da inserire."""
    import re as _re
    return _re.sub(r"^\s*(scrivi|aggiungi|inserisci|nota|annota|metti)\b[:,]?\s*", "", (testo or ""), flags=_re.I).strip()

def _parse_durata(testo):
    """Da 'timer di 10 minuti' / 'tra un'ora e mezza' ai secondi totali."""
    low = (testo or "").lower()
    if "mezz'ora" in low or "mezzora" in low or "mezz ora" in low:
        base = 1800
    elif "quarto d'ora" in low or "quarto d ora" in low:
        base = 900
    else:
        base = 0
    tot = base
    for num, unit in re.findall(r"(\d+)\s*(ore|ora|h|minut\w*|min|m|second\w*|sec|s)\b", low):
        n = int(num)
        if unit in ("ore", "ora", "h"):
            tot += n * 3600
        elif unit.startswith("minut") or unit in ("min", "m"):
            tot += n * 60
        else:
            tot += n
    if tot == 0 and ("un'ora" in low or "un ora" in low or "unora" in low):
        tot = 3600
    return tot

def _descrivi_durata(sec):
    m, s = divmod(sec, 60)
    h, m = divmod(m, 60)
    parti = []
    if h:
        parti.append(f"{h} ore" if h > 1 else "un'ora")
    if m:
        parti.append(f"{m} minuti")
    if s:
        parti.append(f"{s} secondi")
    return " e ".join(parti) if parti else "pochi secondi"

def _avvia_timer(secondi, etichetta=""):
    def _suona():
        testo = "Tempo scaduto" + (f": {etichetta}" if etichetta else "") + "."
        print(f"[TIMER] {testo}")
        try:
            voce.parla(testo, config.get("voce"))
        except Exception:
            pass
    t = threading.Timer(secondi, _suona)
    t.daemon = True
    t.start()

def _parse_colonne(testo):
    """Da 'colonna 1 dati, colonna 2 clienti...' (o lista separata da virgole) alle intestazioni."""
    import re as _re
    trovate = _re.findall(r"colonn[ae]\s*\d*\s*[:\-]?\s*(.+?)(?=\s*colonn[ae]\s*\d|\s*[,;]\s*colonn|\s*$)",
                          testo, _re.I)
    if trovate:
        cols = [t.strip(" .,;") for t in trovate if t.strip(" .,;")]
    else:
        cols = [p.strip(" .") for p in _re.split(r"[,;]", testo) if p.strip(" .")]
    return cols

def _esci_dal_wizard(low):
    """True se la frase è un comando nuovo o un 'ho finito' che chiude la compilazione guidata."""
    chiusura = ("aprilo", "apri il foglio", "apri il file", "apri il documento", "apri la nota",
                "ho finito", "abbiamo finito", "finito", "fine", "chiudi", "chiudi il foglio",
                "chiudi il documento", "chiudi la nota", "basta cosi", "basta così")
    nuovi = ("crea ", "che tempo", "che ore", "notizie", "mercati", "traduci",
             "cerca ", "trova ", "apri la", "apri il programma")
    return any(k in low for k in chiusura) or low.strip().startswith(nuovi)

def _modo_nota(testo):
    """Modalità BLOC-NOTES attiva: ogni frase viene annotata nel file. Torna la frase da dire,
    oppure None se l'utente ha dato un comando nuovo (esce dalla modalità)."""
    global _DOC_CORRENTE, IN_ATTESA_SCELTA
    path = _DOC_CORRENTE["path"]
    low = (testo or "").strip().lower()
    if _esci_dal_wizard(low):
        _DOC_CORRENTE["fase"] = None
        IN_ATTESA_SCELTA = False
        if any(k in low for k in ("apri", "finito", "fine", "basta", "chiudi")):
            return apri_percorso(path)
        return None
    try:
        ok = promemoria.aggiungi_al_blocco(path, testo)
    except Exception as e:
        print(f"[nota] errore: {e}")
        return "Non riesco a scrivere nella nota."
    IN_ATTESA_SCELTA = True
    return "Annotato." if ok else "Non ho capito cosa annotare."

def _modo_excel(testo):
    """Modalità foglio ATTIVO: ogni ordine vocale è tradotto in azioni Excel (foglio.py).
    Gestisce colonne, righe, formule, colori, titoli, larghezza. Torna la frase da dire,
    oppure None se l'utente ha dato un comando nuovo (esce dalla modalità foglio)."""
    global _DOC_CORRENTE, IN_ATTESA_SCELTA
    path = _DOC_CORRENTE["path"]
    low = (testo or "").strip().lower()

    # Uscita / chiusura
    if _esci_dal_wizard(low):
        _DOC_CORRENTE["fase"] = None
        IN_ATTESA_SCELTA = False
        if any(k in low for k in ("apri", "finito", "fine", "basta")):
            return apri_percorso(path)
        return None  # comando nuovo: lo gestisce il flusso normale

    frase = foglio.esegui_comando(path, testo, BRAIN_CFG)
    IN_ATTESA_SCELTA = True   # resta in ascolto per il prossimo ordine
    return frase

_ESTENSIONI = {
    "word": (".doc", ".docx"), "documento word": (".doc", ".docx"),
    "pdf": (".pdf",),
    "excel": (".xls", ".xlsx", ".csv"), "foglio": (".xls", ".xlsx", ".csv"),
    "powerpoint": (".ppt", ".pptx"), "presentazione": (".ppt", ".pptx"),
    "immagine": (".png", ".jpg", ".jpeg", ".gif"), "foto": (".png", ".jpg", ".jpeg"),
    "testo": (".txt",),
}
_ORDINALI = {"primo": 0, "prima": 0, "secondo": 1, "seconda": 1, "terzo": 2, "terza": 2,
             "quarto": 3, "quarta": 3, "quinto": 4}

def _descrivi_candidati(lista):
    """Breve descrizione a voce dei file trovati (per tipo)."""
    pezzi = []
    for i, p in enumerate(lista[:5], 1):
        ext = os.path.splitext(p)[1].lower().lstrip(".")
        pezzi.append(f"il numero {i}, un {ext}, {os.path.basename(p)}")
    return "; ".join(pezzi)

def _risolvi_scelta_file(testo, candidati):
    """Dall'input ('quello word', 'il pdf', 'il primo', 'il più recente') sceglie un file. Torna percorso o None."""
    t = testo.lower()
    # Per tipo/estensione
    for parola, exts in _ESTENSIONI.items():
        if parola in t:
            for p in candidati:
                if os.path.splitext(p)[1].lower() in exts:
                    return p
    # Per ordinale
    for parola, idx in _ORDINALI.items():
        if parola in t and idx < len(candidati):
            return candidati[idx]
    # "più recente" (i candidati sono già ordinati dal più recente)
    if "recente" in t or "ultimo" in t:
        return candidati[0]
    # Per numero scritto (1,2,3...)
    for tok in t.replace(",", " ").split():
        if tok.isdigit() and 1 <= int(tok) <= len(candidati):
            return candidati[int(tok) - 1]
    # Per pezzo di nome file
    for p in candidati:
        if any(w and w in os.path.basename(p).lower() for w in t.split()):
            return p
    return None

def rispondi(testo_utente):
    """Punto d'ingresso unico: gestisce la conversazione (anche la scelta file) e torna la frase da dire."""
    global _FILE_IN_SOSPESO, IN_ATTESA_SCELTA
    t = (testo_utente or "").strip()

    # Modalità BLOC-NOTES attiva: ogni frase viene annotata
    if _DOC_CORRENTE and _DOC_CORRENTE.get("tipo") == "nota" and _DOC_CORRENTE.get("fase") == "nota":
        risp = _modo_nota(testo_utente)
        if risp is not None:
            print(f"\n[AVATAR]: {risp}")
            return risp

    # Modalità FOGLIO Excel attiva: le frasi diventano azioni sul foglio, non vanno al cervello-intent
    if _DOC_CORRENTE and _DOC_CORRENTE.get("tipo") == "excel" and _DOC_CORRENTE.get("fase") == "excel":
        risp = _modo_excel(testo_utente)
        if risp is not None:
            print(f"\n[AVATAR]: {risp}")
            return risp
        # risp None = era un comando nuovo (modalità foglio chiusa): prosegui normale

    # Se stiamo aspettando QUALE file aprire, prova a risolvere la scelta
    if _FILE_IN_SOSPESO:
        scelto = _risolvi_scelta_file(t, _FILE_IN_SOSPESO)
        if scelto is not None:
            _FILE_IN_SOSPESO = []
            IN_ATTESA_SCELTA = False
            esito = apri_percorso(scelto)
            print(f"[SISTEMA]: {esito}")
            print(f"\n[AVATAR]: {esito}")
            return esito
        # Non era una scelta valida: annulla l'attesa e prosegui normale
        _FILE_IN_SOSPESO = []
        IN_ATTESA_SCELTA = False

    # Instradamento DIRETTO (non passa dal cervello): apertura siti/pagine web
    if re.match(r"^\s*(apri\s+la\s+pagina|apri\s+il\s+sito|apri\s+sito|apri\s+pagina|vai\s+su|portami\s+su)\b", t, re.I):
        return esecutore_comandi({"skill_identificata": "apri_sito",
                                  "parametri": {"target": t}, "risposta_vocale": ""}, t)

    # Instradamento DIRETTO: "apri X" dove X e' un sito noto (whatsapp, asroma, ecc.)
    m_apri = re.match(r"^\s*apri(?:mi)?\s+(?:la\s+|il\s+|lo\s+)?(.+)", t, re.I)
    if m_apri:
        nome_apri = m_apri.group(1).strip().lower()
        # Correggi errori Whisper e controlla se e' un sito noto
        nome_corretto = controllo_pc._correggi_whisper(nome_apri)
        sito_trovato = False
        for k in controllo_pc._SITI:
            if k in nome_corretto or nome_corretto in k:
                sito_trovato = True
                break
        if not sito_trovato:
            sito_trovato = controllo_pc._fuzzy_match_sito(nome_corretto) is not None
        if sito_trovato:
            return esecutore_comandi({"skill_identificata": "apri_sito",
                                      "parametri": {"target": nome_apri}, "risposta_vocale": ""}, t)

    return esecutore_comandi(interroga_assistente(testo_utente), testo_utente)

def esecutore_comandi(json_ricevuto, testo_utente=""):
    """Esegue la skill e RESTITUISCE la frase da dire a voce (testo_da_dire)."""
    global _DOC_CORRENTE, _FILE_IN_SOSPESO, IN_ATTESA_SCELTA
    if "error" in json_ricevuto:
        print(json_ricevuto["error"])
        return json_ricevuto["error"]

    skill = json_ricevuto.get("skill_identificata")
    parametri = json_ricevuto.get("parametri", {})
    target = parametri.get("target", "").strip()
    vecchio_nome = parametri.get("vecchio_nome", "").strip()
    nuovo_nome = parametri.get("nuovo_nome", "").strip()
    dati_prev = parametri.get("dati_preventivo", {})

    # Di default la voce dice la frase del modello...
    testo_da_dire = json_ricevuto.get("risposta_vocale", "")

    # ROUTING DELLE AZIONI
    # Per le azioni concrete la VOCE dice il RISULTATO REALE (esito), non la frase
    # ottimista del modello: cosi' non dice "fatto" se qualcosa e' andato storto.
    if skill == "crea_cartella" and target:
        esito = esegui_crea_cartella(target)
        print(f"[SISTEMA]: {esito}")
        testo_da_dire = esito

    elif skill == "rinomina_cartella":
        esito = esegui_rinomina_cartella(vecchio_nome, nuovo_nome)
        print(f"[SISTEMA]: {esito}")
        testo_da_dire = esito

    elif skill == "cerca_video" and target:
        query_pulita = target.lower().replace("://youtube.com", "").replace("youtube.com", "").replace("comauto", "auto").replace("su youtube", "").replace("su internet", "").strip()
        esito = esegui_apri_browser(query_ricerca=query_pulita, piattaforma='youtube')
        print(f"[SISTEMA]: {esito}")
        testo_da_dire = esito

    elif skill == "cerca_musica" and target:
        esito = esegui_apri_browser(query_ricerca=target, piattaforma='youtube')
        print(f"[SISTEMA]: {esito}")
        testo_da_dire = esito

    elif skill == "apri_programma":
        # Controlla prima se il target e' in realta' un sito noto
        nome_corretto = controllo_pc._correggi_whisper(target.lower()) if target else ""
        e_un_sito = False
        for k in controllo_pc._SITI:
            if k in nome_corretto or nome_corretto in k:
                e_un_sito = True
                break
        if e_un_sito:
            testo_da_dire = controllo_pc.apri_sito(target)
        else:
            esito = esegui_apri_programma(target)
            # Se il programma non si trova, prova ad aprirlo come sito
            if "non riesco" in esito.lower() or "non è riconosciuto" in esito.lower():
                testo_da_dire = controllo_pc.apri_sito(target)
            else:
                testo_da_dire = esito
        print(f"[SISTEMA]: {testo_da_dire}")

    elif skill == "apri_cartella":
        esito = esegui_apri_cartella(target)
        print(f"[SISTEMA]: {esito}")
        testo_da_dire = esito

    elif skill == "cerca_file":
        esito = esegui_cerca_file(target)
        print(f"[SISTEMA]: {esito}")
        testo_da_dire = esito

    elif skill in ("crea_excel", "crea_word", "crea_pdf"):
        nome = target or "documento"
        try:
            if skill == "crea_excel":
                path = documenti.crea_excel(nome); tipo = "excel"
            elif skill == "crea_word":
                path = documenti.crea_word(nome); tipo = "word"
            else:
                path = documenti.crea_pdf(nome); tipo = "pdf"
            # NON apriamo il file ora: se Excel lo tiene aperto si blocca la scrittura.
            _DOC_CORRENTE = {"path": path, "tipo": tipo, "titolo": nome, "righe": [],
                             "fase": None, "intestazioni": []}
            if tipo == "excel":
                # Attiva la modalità FOGLIO: ogni ordine diventa un'azione Excel
                _DOC_CORRENTE["fase"] = "excel"
                IN_ATTESA_SCELTA = True
                testo_da_dire = (f"Ho creato il foglio Excel {nome}. Dimmi cosa fare: "
                                 "le colonne, un titolo, le righe, formule, colori. Quando hai finito dì: aprilo.")
            else:
                tipo_nome = {"word": "Word", "pdf": "PDF"}[tipo]
                testo_da_dire = (f"Ho creato il file {tipo_nome} {nome}. "
                                 "Dettami cosa scrivere; quando hai finito dì: aprilo.")
        except Exception as e:
            print(f"[ERRORE crea doc]: {e}")
            testo_da_dire = "Non riesco a creare il documento."
        print(f"[SISTEMA]: {testo_da_dire}")

    elif skill == "aggiungi_dati":
        if not _DOC_CORRENTE:
            testo_da_dire = "Prima dimmi che documento creare, ad esempio: crea un file Excel clienti."
        else:
            contenuto = testo_utente or target
            tipo = _DOC_CORRENTE["tipo"]
            try:
                if tipo == "excel":
                    n, intest = documenti.aggiungi_righe_excel(_DOC_CORRENTE["path"], contenuto, BRAIN_CFG)
                    testo_da_dire = f"Aggiunte {n} voci al foglio." if n != 1 else "Aggiunta al foglio."
                elif tipo == "word":
                    documenti.aggiungi_paragrafo_word(_DOC_CORRENTE["path"], _pulisci_prefisso(contenuto))
                    testo_da_dire = "Scritto nel documento."
                else:  # pdf
                    _DOC_CORRENTE["righe"].append(_pulisci_prefisso(contenuto))
                    documenti.scrivi_pdf(_DOC_CORRENTE["path"], _DOC_CORRENTE["titolo"], _DOC_CORRENTE["righe"])
                    testo_da_dire = "Scritto nel PDF."
            except PermissionError:
                testo_da_dire = "Il documento è aperto in un altro programma. Chiudilo e riprova."
            except Exception as e:
                print(f"[ERRORE scrittura doc]: {e}")
                testo_da_dire = "Non riesco a scrivere nel documento."
        print(f"[SISTEMA]: {testo_da_dire}")

    elif skill == "promemoria":
        testo_da_dire = promemoria.aggiungi_todo(testo_utente or target)
        print(f"[SISTEMA]: {testo_da_dire}")

    elif skill == "lista_promemoria":
        testo_da_dire = promemoria.lista_todo()
        print(f"[SISTEMA]: {testo_da_dire}")

    elif skill == "completa_promemoria":
        testo_da_dire = promemoria.completa_todo(testo_utente or target)
        print(f"[SISTEMA]: {testo_da_dire}")

    elif skill == "crea_nota":
        titolo = re.sub(r"^\s*(apri|un|il|la|per|blocco|note|nota|appunti)\b\s*", "",
                        (target or "appunti"), flags=re.I).strip() or "appunti"
        try:
            path = promemoria.crea_blocco(titolo)
            _DOC_CORRENTE = {"path": path, "tipo": "nota", "titolo": titolo,
                             "fase": "nota", "righe": [], "intestazioni": []}
            IN_ATTESA_SCELTA = True
            testo_da_dire = f"Bloc-notes '{titolo}' aperto. Dettami cosa annotare; quando hai finito dì: chiudi."
        except Exception as e:
            print(f"[ERRORE nota]: {e}")
            testo_da_dire = "Non riesco a creare la nota."
        print(f"[SISTEMA]: {testo_da_dire}")

    elif skill == "prendi_nota":
        testo_da_dire = promemoria.aggiungi_nota(testo_utente or target)
        print(f"[SISTEMA]: {testo_da_dire}")

    elif skill == "leggi_note":
        testo_da_dire = promemoria.leggi_note()
        print(f"[SISTEMA]: {testo_da_dire}")

    elif skill == "salva_contatto":
        testo_da_dire = promemoria.salva_contatto(testo_utente or target)
        print(f"[SISTEMA]: {testo_da_dire}")

    elif skill == "trova_contatto":
        testo_da_dire = promemoria.trova_contatto(testo_utente or target)
        print(f"[SISTEMA]: {testo_da_dire}")

    elif skill == "timer":
        sec = _parse_durata(testo_utente or target)
        if sec <= 0:
            testo_da_dire = "Non ho capito la durata. Dimmi ad esempio: timer di 10 minuti."
        else:
            _avvia_timer(sec, "")
            testo_da_dire = f"Ok, ti avviso tra {_descrivi_durata(sec)}."
        print(f"[SISTEMA]: {testo_da_dire}")

    elif skill == "calcolo":
        testo_da_dire = calcoli.risolvi(testo_utente or target)
        print(f"[CALCOLO]: {testo_da_dire}")

    elif skill == "ricerca_web":
        contenuto = testo_utente or target or ""
        # Rete di sicurezza: se chiede prezzi/quotazioni di un titolo o cripta noti,
        # usa i DATI REALI (Yahoo), non la ricerca web (che allucinerebbe i numeri).
        tick = web_tools.ticker_noto(contenuto) if any(
            k in contenuto.lower() for k in ("prezzo", "quanto vale", "quotazione", "livell", "quota", "vale")) else None
        if tick:
            print(f"[SISTEMA]: Prendo i dati reali di '{contenuto}'...")
            commento, dettagli = web_tools.analizza_titolo(contenuto, BRAIN_CFG)
            if dettagli:
                print(f"[DATI]: {dettagli}")
            print("[NOTA]: Dati reali di mercato, non un consiglio di investimento.")
            testo_da_dire = commento
        else:
            print("[SISTEMA]: Cerco sul web...")
            testo_da_dire = web_info.cerca_web(contenuto, BRAIN_CFG)
            print(f"[WEB]: {testo_da_dire}")

    elif skill == "definizione":
        testo_da_dire = web_info.definizione(testo_utente or target, BRAIN_CFG)
        print(f"[DEFINIZIONE]: {testo_da_dire}")

    elif skill == "riassumi":
        print("[SISTEMA]: Leggo e riassumo la pagina...")
        testo_da_dire = web_info.riassumi(testo_utente or target, BRAIN_CFG)
        print(f"[RIASSUNTO]: {testo_da_dire}")

    elif skill == "mappa":
        testo_da_dire = web_info.mappa(testo_utente or target)
        print(f"[MAPPA]: {testo_da_dire}")

    elif skill == "apri_sito":
        testo_da_dire = controllo_pc.apri_sito(testo_utente or target)
        print(f"[SISTEMA]: {testo_da_dire}")

    elif skill == "volume":
        testo_da_dire = controllo_pc.volume(testo_utente or target)
        print(f"[SISTEMA]: {testo_da_dire}")

    elif skill == "screenshot":
        testo_da_dire = controllo_pc.screenshot()
        print(f"[SISTEMA]: {testo_da_dire}")

    elif skill == "blocca_pc":
        testo_da_dire = controllo_pc.blocca_pc()
        print(f"[SISTEMA]: {testo_da_dire}")

    elif skill == "spegni_pc":
        testo_da_dire = controllo_pc.spegni_pc()
        print(f"[SISTEMA]: {testo_da_dire}")

    elif skill == "riavvia_pc":
        testo_da_dire = controllo_pc.riavvia_pc()
        print(f"[SISTEMA]: {testo_da_dire}")

    elif skill == "annulla_spegnimento":
        testo_da_dire = controllo_pc.annulla_spegnimento()
        print(f"[SISTEMA]: {testo_da_dire}")

    elif skill == "whatsapp":
        testo_da_dire = controllo_pc.manda_whatsapp(testo_utente or target, BRAIN_CFG)
        print(f"[SISTEMA]: {testo_da_dire}")

    elif skill == "crea_appuntamento":
        ev = calendario.estrai_evento(testo_utente or target, BRAIN_CFG)
        if not ev:
            testo_da_dire = "Non ho capito quando. Dimmi ad esempio: segna appuntamento domani alle 15 con Mario."
        else:
            quando = calendario.frase_data(ev["data"])
            luogo = f" a {ev['luogo']}" if ev.get("luogo") else ""
            fatto = False
            # 1) Prova Google Calendar
            if google_cal.configurato():
                try:
                    google_cal.crea_evento(ev["titolo"], ev["data"], ev["ora"], ev.get("durata_min", 60), ev.get("luogo", ""))
                    testo_da_dire = f"Segnato su Google Calendar: {ev['titolo']} {quando} alle {ev['ora']}{luogo}."
                    fatto = True
                except Exception as e:
                    print(f"[ERRORE Google Calendar]: {e}")
            # 2) Ripiego locale (.ics)
            if not fatto:
                try:
                    path, ev = calendario.aggiungi(ev)
                    if path:
                        apri_percorso(path)
                    testo_da_dire = f"Segnato: {ev['titolo']} {quando} alle {ev['ora']}{luogo}."
                except Exception as e:
                    print(f"[ERRORE appuntamento]: {e}")
                    testo_da_dire = "Non riesco a salvare l'appuntamento."
        print(f"[SISTEMA]: {testo_da_dire}")

    elif skill == "agenda":
        low = (testo_utente or "").lower()
        giorno = datetime.date.today()
        if "dopodomani" in low:
            giorno = giorno + datetime.timedelta(days=2)
        elif "domani" in low:
            giorno = giorno + datetime.timedelta(days=1)
        data_iso = giorno.isoformat()
        if google_cal.configurato():
            try:
                eventi = google_cal.eventi_del_giorno(data_iso)
                testo_da_dire = calendario.descrivi_lista(eventi, data_iso)
            except Exception as e:
                print(f"[ERRORE Google Calendar]: {e}")
                testo_da_dire = calendario.descrivi_giornata(data_iso)
        else:
            testo_da_dire = calendario.descrivi_giornata(data_iso)
        print(f"[AGENDA]: {testo_da_dire}")

    elif skill == "apri_documento":
        if _DOC_CORRENTE:
            testo_da_dire = apri_percorso(_DOC_CORRENTE["path"])
        else:
            testo_da_dire = "Non c'è nessun documento da aprire al momento."
        print(f"[SISTEMA]: {testo_da_dire}")

    elif skill == "apri_file":
        _risultati = pc_index.trova_file_smart((target or "").strip(), pc_index.get_index())
        trovati = [r["path"] for r in _risultati]
        if not trovati:
            testo_da_dire = f"Non ho trovato nessun file chiamato {target}."
        elif len(trovati) == 1:
            testo_da_dire = apri_percorso(trovati[0])
        else:
            _FILE_IN_SOSPESO = trovati
            IN_ATTESA_SCELTA = True
            print("[FILE TROVATI]:")
            for i, p in enumerate(trovati[:9], 1):
                print(f"  {i}. {p}")
            testo_da_dire = (f"Ne ho trovati {len(trovati)}: " + _descrivi_candidati(trovati)
                             + ". Quale apro?")
        print(f"[SISTEMA]: {testo_da_dire}")

    elif skill == "meteo":
        if target:
            # Meteo della citta' richiesta
            lat, lon, nome = _geocoding(target)
            if lat is None:
                testo_da_dire = f"Non trovo la città {target}."
            else:
                temp, cielo = _meteo_attuale(lat, lon, citta=nome)
                testo_da_dire = (f"A {nome} ci sono {temp} gradi, cielo {cielo}."
                                 if temp is not None else f"Non riesco a leggere il meteo di {nome}.")
        else:
            temp, cielo = _meteo_attuale()
            citta = config.get("meteo", {}).get("citta", "Roma")
            testo_da_dire = (f"A {citta} ci sono {temp} gradi, cielo {cielo}."
                             if temp is not None else "Non riesco a leggere il meteo in questo momento.")
        print(f"[METEO]: {testo_da_dire}")

    elif skill == "traduci":
        print("[SISTEMA]: Traduco...")
        sys_trad = ("Sei un traduttore. Traduci esattamente ciò che chiede l'utente nella lingua richiesta. "
                    "Rispondi SOLO con la traduzione, in testo semplice, senza spiegazioni.")
        testo_da_dire = brain.chat_libero(sys_trad, testo_utente, BRAIN_CFG)
        print(f"[TRADUZIONE]: {testo_da_dire}")

    elif skill == "naviga_web":
        # Navigazione web autonoma con browser-use
        compito = target or testo_utente
        # Verifica se browser-use è installato PRIMA di provare
        _bu_ok = False
        try:
            import browser_use as _bu_test  # noqa: F401
            _bu_ok = True
        except ImportError:
            pass
        if not _bu_ok:
            # Fallback intelligente: apri il sito + ricerca Google come aiuto
            print(f"[SISTEMA]: browser-use non installato, apro nel browser normale...")
            # Prova prima ad aprire il sito menzionato
            _aperto = controllo_pc.apri_sito(compito)
            # Poi apri anche una ricerca Google col compito completo
            import urllib.parse as _up
            _query = _up.quote_plus(compito)
            controllo_pc._apri_url(f"https://www.google.com/search?q={_query}")
            testo_da_dire = f"Ho aperto il browser con una ricerca per: {compito}. La navigazione autonoma richiede browser-use."
            print(f"[SISTEMA]: {testo_da_dire}")
        if _bu_ok:
            print(f"[SISTEMA]: Avvio navigazione autonoma: {compito}")
            testo_da_dire = "Sto aprendo il browser, un momento..."
            # La navigazione vera gira in un thread per non bloccare la voce
            def _nav():
                nonlocal testo_da_dire
                ris = navigazione.naviga_web(compito, BRAIN_CFG)
                testo_da_dire = ris if ris else "Navigazione completata."
                print(f"[BROWSER]: {testo_da_dire}")
            import threading as _th
            t = _th.Thread(target=_nav)
            t.start()
            t.join(timeout=90)
            if t.is_alive():
                testo_da_dire = "La navigazione sta richiedendo più tempo del previsto, ma continuo in background."

    elif skill == "cerca_pagina":
        # Cerca informazioni in una pagina web specifica
        print(f"[SISTEMA]: Cerco informazioni nella pagina: {target}")
        try:
            import browser_use as _bu_test2  # noqa: F401
            import re as _re
            url_match = _re.search(r'https?://\S+', target or testo_utente)
            if url_match:
                url = url_match.group(0)
                cosa = (target or testo_utente).replace(url, '').strip() or "estrai le informazioni principali"
                testo_da_dire = navigazione.cerca_in_pagina(url, cosa, BRAIN_CFG)
            else:
                testo_da_dire = navigazione.naviga_web(
                    f"cerca su google: {target or testo_utente} e riporta i risultati principali",
                    BRAIN_CFG
                )
            print(f"[BROWSER]: {testo_da_dire}")
        except ImportError:
            # Fallback: apri il sito normalmente
            testo_da_dire = controllo_pc.apri_sito(target or testo_utente)
            print(f"[SISTEMA]: {testo_da_dire}")

    elif skill == "compila_form":
        # Compila un form su una pagina web
        print(f"[SISTEMA]: Compilo il form: {target}")
        try:
            import browser_use as _bu_test3  # noqa: F401
            import re as _re
            url_match = _re.search(r'https?://\S+', target or testo_utente)
            if url_match:
                url = url_match.group(0)
                istruzioni = (target or testo_utente).replace(url, '').strip()
                testo_da_dire = navigazione.compila_form(url, istruzioni, BRAIN_CFG)
            else:
                testo_da_dire = navigazione.naviga_web(target or testo_utente, BRAIN_CFG)
            print(f"[BROWSER]: {testo_da_dire}")
        except ImportError:
            testo_da_dire = "Per compilare form serve browser-use. Apro il sito normalmente."
            controllo_pc.apri_sito(target or testo_utente)
            print(f"[SISTEMA]: {testo_da_dire}")

    elif skill == "conversazione_generica":
        # Il "cervello libero": risponde a qualsiasi domanda, in modo naturale.
        persona = (f"Sei {NOME_ASSISTENTE.capitalize()}, un assistente vocale in italiano. "
                   "Rispondi in modo naturale, chiaro e breve (massimo 2-3 frasi). "
                   "Testo semplice, senza asterischi o elenchi. Se non sai una cosa, dillo.")
        testo_da_dire = brain.chat_libero(persona, testo_utente, BRAIN_CFG)
        print(f"[RISPOSTA]: {testo_da_dire}")

    elif skill == "mercati":
        # Per i mercati la VOCE usa i dati reali, non i numeri del modello.
        dati = _dati_mercati()
        testo_da_dire = frase_mercati(dati)
        print("[SISTEMA]: Lettura mercati in corso...")
        print(esegui_lettura_mercati_reali())

    elif skill == "briefing":
        # Il notiziario: saluto + data + meteo + mercati, tutto reale.
        print("[SISTEMA]: Preparo il notiziario...")
        testo_da_dire = briefing_vocale()
        print(f"[NOTIZIARIO]: {testo_da_dire}")

    elif skill == "analisi_titolo":
        print(f"[SISTEMA]: Cerco i dati reali su '{target}'...")
        commento, dettagli = web_tools.analizza_titolo(target, BRAIN_CFG)
        if dettagli:
            print(f"[DATI]: {dettagli}")
        print(f"[ANALISI]: {commento}")
        print("[NOTA]: Questa è solo una descrizione dei dati, non è un consiglio di investimento.")
        testo_da_dire = commento

    elif skill == "notizie":
        print("[SISTEMA]: Leggo le notizie...")
        titoli = recupera_notizie(3, argomento=(target or None))
        if titoli:
            for i, t in enumerate(titoli, 1):
                print(f"  {i}. {t}")
            intro = f"Ultime notizie su {target}: " if target else "Ecco le ultime notizie: "
            testo_da_dire = intro + ". ".join(titoli) + "."
        else:
            testo_da_dire = "Non riesco a leggere le notizie in questo momento."
        print(f"[NOTIZIE]: {testo_da_dire}")

    elif skill == "crea_preventivo":
        # Se c'era un doc Word orfano creato prima, eliminalo
        if _DOC_CORRENTE and _DOC_CORRENTE.get("tipo") == "word":
            vecchio = _DOC_CORRENTE.get("path", "")
            if vecchio and os.path.exists(vecchio):
                try:
                    os.remove(vecchio)
                    print(f"[SISTEMA]: Rimosso file orfano: {os.path.basename(vecchio)}")
                except Exception:
                    pass
            _DOC_CORRENTE = None
        esito = esegui_crea_preventivo_word(dati_prev)
        print(f"[SISTEMA]: {esito}")
        testo_da_dire = esito

    # Stampa sempre cosa dice l'assistente
    print(f"\n[AVATAR]: {testo_da_dire}")
    return testo_da_dire


def ciclo_testo():
    """Modalita' TASTIERA (riserva): scrivi e leggi."""
    print("Modalità TASTIERA. Scrivi 'esci' per chiudere, 'voce' per passare al microfono.")
    while True:
        try:
            testo = input("\nTu: ")
            if testo.lower() == 'esci':
                break
            if testo.lower() == 'voce':
                ciclo_voce()
                continue
            if not testo.strip():
                continue
            rispondi(testo)
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"[X] Errore: {e}")


def ciclo_voce():
    """Modalita' VOCE (push-to-talk): parli e ascolti la risposta."""
    try:
        import voce
    except Exception as e:
        print(f"[X] Modulo voce non disponibile ({e}). Installa i requisiti: pip install -r requirements.txt")
        return

    print("Modalità VOCE (push-to-talk). Di' 'esci' o premi CTRL+C per uscire; INVIO a vuoto per tornare alla tastiera.")
    while True:
        try:
            testo = voce.ascolta(BRAIN_CFG)
            if not testo:
                print("[i] Non ho sentito nulla. Torno alla tastiera.")
                return
            print(f"\n[TU]: {testo}")
            if testo.strip().lower().startswith("esci"):
                break
            da_dire = rispondi(testo)
            voce.parla(da_dire, config.get("voce"))
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"[X] Errore: {e}")


if __name__ == "__main__":
    print("=" * 60)
    print(f"[*] Cervello di {NOME_ASSISTENTE.upper()} pronto. Provider: {BRAIN_CFG.get('provider')}")
    print(f"[*] Skill caricate: {len(SKILLS_DISPONIBILI)}")
    print("=" * 60)

    # Avvio in modalita' voce con:  python jarvis.py voce
    if len(sys.argv) > 1 and sys.argv[1].lower() in ("voce", "voice"):
        ciclo_voce()
    else:
        ciclo_testo()
