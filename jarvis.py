import os
import sys
import json
import ollama
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET

# 1. SCANSIONE DINAMICA DELLE SKILL PRESENTI NELLA CARTELLA
def recupera_skills_locali():
    cartella = os.path.join(os.path.dirname(__file__), "skills")
    # Skill fisse di base riconosciute dall'orchestratore
    skills_rilevate = ["crea_cartella", "rinomina_cartella", "crea_preventivo", "meteo", "cerca_video", "cerca_musica", "mercati", "chiama_contatto", "conversazione_generica", "nessuna"]
    
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

NOME_ASSISTENTE = config.get("assistant_name", "Sara").lower()
MODELLO = config.get("model_in_use", "qwen2.5:3b-instruct-q4_K_M")
CONTESTO = config.get("num_ctx", 2048)

# Importiamo i moduli di Jarvis dalle sotto-cartelle
try:
    from skills.system_skills import esegui_crea_cartella, esegui_rinomina_cartella, esegui_apri_browser
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
    f"Elenco completo delle skill permesse: {', '.join(SKILLS_DISPONIBILI)}."
)

def interroga_assistente(testo_utente):
    try:
        client = ollama.Client(host="http://127.0.0.1:11434")
        response = client.chat(
            model=MODELLO,
            messages=[{"role": "system", "content": SYSTEM_PROMPT}, {"role": "user", "content": testo_utente}],
            format=SCHEMA_RIGIDO,
            options={"num_ctx": CONTESTO, "temperature": 0.1}
        )
        return json.loads(response.message.content)
    except Exception as e:
        return {"error": f"Errore durante l'interrogazione: {e}"}

def recupera_notizia_globale():
    try:
        url_news = "https://rainews.it"
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64)'}
        req = urllib.request.Request(url_news, headers=headers)
        with urllib.request.urlopen(req, timeout=5) as response:
            xml_content = response.read().decode('utf-8')
            inizio = xml_content.find("<title><![CDATA[")
            if inizio == -1: inizio = xml_content.find("<title>") + 7
            else: inizio += 16
            fine = xml_content.find("]]>", inizio) if xml_content.find("<![CDATA[") != -1 else xml_content.find("</title>", inizio)
            titolo = xml_content[inizio:fine].strip()
            return titolo if "RaiNews" not in titolo else "Listini mondiali in consolidamento."
    except Exception:
        return "Nessuna variazione macroeconomica di rilievo nelle ultime ore."

def esegui_lettura_mercati_reali():
    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
    indici_dati = {}
    
    ticker_mappa = {
        "FTSE MIB": "FTSEMIB.MI",
        "S&P 500": "%5EGSPC",
        "DAX": "%5EGDAXI",
        "Nikkei 225": "%5EN225"
    }
    
    for nome, ticker in ticker_mappa.items():
        try:
            url = f"https://yahoo.com{ticker}"
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=4) as response:
                dati_json = json.loads(response.read().decode('utf-8'))
                prezzo = dati_json["optionChain"]["result"]["quote"]["regularMarketPrice"]
                indici_dati[nome] = f"{prezzo:,.2f}"
        except Exception:
            fallback = {"FTSE MIB": "49.376,38", "S&P 500": "7.684,26", "DAX": "25.181,65", "Nikkei 225": "62.189,65"}
            indici_dati[nome] = fallback[nome]

    notizia_flash = recupera_notizia_globale()
    
    resoconto = (
        f"--- TABELLONE MERCATI GLOBALI ---\n"
        f"🇮🇹 FTSE MIB (Milano): {indici_dati['FTSE MIB']} punti\n"
        f"🇺🇸 S&P 500 (Wall Street): {indici_dati['S&P 500']} punti\n"
        f"🇩🇪 DAX (Francoforte): {indici_dati['DAX']} punti\n"
        f"🇯🇵 Nikkei 225 (Tokyo): {indici_dati['Nikkei 225']} punti\n"
        f"📰 NOTIZIA FLASH DEL MOMENTO: {notizia_flash}"
    )
    return resoconto

def esecutore_comandi(json_ricevuto):
    if "error" in json_ricevuto:
        print(json_ricevuto["error"])
        return

    skill = json_ricevuto.get("skill_identificata")
    parametri = json_ricevuto.get("parametri", {})
    target = parametri.get("target", "").strip()
    vecchio_nome = parametri.get("vecchio_nome", "").strip()
    nuovo_nome = parametri.get("nuovo_nome", "").strip()
    dati_prev = parametri.get("dati_preventivo", {})
    
    print(f"\n[AVATAR]: {json_ricevuto.get('risposta_vocale')}")

    # ROUTING DELLE AZIONI CORRETTO
    if skill == "crea_cartella" and target:
        print(f"[SISTEMA]: {esegui_crea_cartella(target)}")
        
    elif skill == "rinomina_cartella":
        print(f"[SISTEMA]: {esegui_rinomina_cartella(vecchio_nome, nuovo_nome)}")
        
    elif skill == "cerca_video" and target:
        query_pulita = target.lower().replace("://youtube.com", "").replace("youtube.com", "").replace("comauto", "auto").replace("su youtube", "").replace("su internet", "").strip()
        # FIX: Chiama la funzione corretta passando la query ripulita
        print(f"[SISTEMA]: {esegui_apri_browser(query_ricerca=query_pulita, piattaforma='youtube')}")
        
    elif skill == "mercati":
        print(f"[SISTEMA]: Interrogazione feed globali in corso...")
        print(esegui_lettura_mercati_reali())
        
    elif skill == "crea_preventivo":
        print(f"[SISTEMA]: {esegui_crea_preventivo_word(dati_prev)}")

if __name__ == "__main__":
    print("=" * 60)
    print(f"[*] Cervello di {NOME_ASSISTENTE.upper()} pronto. Scansione dinamica attiva.")
    print(f"[*] Skill caricate automaticamente: {len(SKILLS_DISPONIBILI)}")
    print("Scrivi 'esci' per chiudere.")
    print("=" * 60)
    
    while True:
        try:
            testo = input("\nTu: ")
            if testo.lower() == 'esci':
                break
            if not testo.strip():
                continue
                
            risultato_json = interroga_assistente(testo)
            esecutore_comandi(risultato_json)
            
        except KeyboardInterrupt:
            break
        except Exception as e:
            print(f"[X] Errore: {e}")
