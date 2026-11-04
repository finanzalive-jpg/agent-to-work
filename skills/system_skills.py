"""
system_skills.py - Operazioni di sistema (app, file, cartelle, browser).

Usa pc_index per ricerca intelligente con scoring e fuzzy matching
(ispirato a AI-Voice-Desktop-Assistant).
"""
import os
import sys
import subprocess
import urllib.parse

# Importa il nuovo modulo di indicizzazione
try:
    import pc_index
except ImportError:
    # Fallback: se pc_index non è importabile, lo cerca nella cartella parent
    import importlib.util
    _spec = importlib.util.spec_from_file_location(
        "pc_index", os.path.join(os.path.dirname(os.path.dirname(__file__)), "pc_index.py"))
    pc_index = importlib.util.module_from_spec(_spec)
    _spec.loader.exec_module(pc_index)


def esegui_crea_cartella(nome_cartella):
    """Crea una cartella sul Desktop dell'utente (funziona su Windows e Linux)."""
    if not nome_cartella:
        return "Non ho capito il nome della cartella da creare."

    home = os.path.expanduser("~")
    percorso_desktop = os.path.join(home, "Desktop")
    percorso_finale = os.path.join(percorso_desktop, nome_cartella)

    try:
        if not os.path.exists(percorso_finale):
            os.makedirs(percorso_finale)
            return f"Ok, ho creato la cartella '{nome_cartella}' sul tuo Desktop."
        else:
            return f"La cartella '{nome_cartella}' esiste già sul Desktop."
    except Exception as e:
        return f"Errore durante la creazione della cartella: {e}"


def esegui_rinomina_cartella(vecchio_nome, nuovo_nome):
    """Rinomina una cartella esistente sul Desktop dell'utente."""
    if not vecchio_nome or not nuovo_nome:
        return "Non ho capito quali nomi usare per rinominare la cartella."

    home = os.path.expanduser("~")
    percorso_desktop = os.path.join(home, "Desktop")

    percorso_vecchio = os.path.join(percorso_desktop, vecchio_nome.strip())
    percorso_nuovo = os.path.join(percorso_desktop, nuovo_nome.strip())

    try:
        if os.path.exists(percorso_vecchio):
            if not os.path.exists(percorso_nuovo):
                os.rename(percorso_vecchio, percorso_nuovo)
                return f"Ok, ho rinominato la cartella '{vecchio_nome}' in '{nuovo_nome}' sul tuo Desktop."
            else:
                return f"Impossibile rinominare: esiste già una cartella chiamata '{nuovo_nome}' sul Desktop."
        else:
            return f"Non ho trovato la cartella '{vecchio_nome}' sul tuo Desktop da poter rinominare."
    except Exception as e:
        return f"Errore durante la rinomina della cartella: {e}"


def esegui_apri_browser(query_ricerca=None, piattaforma="google"):
    """Apre il browser predefinito con l'URL di ricerca corretto."""
    if piattaforma == "youtube" and query_ricerca:
        parola_chiave = query_ricerca.replace("https", "").replace("http", "").replace("youtube.com", "").replace("/", "").strip()
        query_enc = urllib.parse.quote(parola_chiave)
        url = f"https://www.youtube.com/results?search_query={query_enc}"
    elif query_ricerca:
        parola_chiave = query_ricerca.replace("https", "").replace("http", "").replace("google.com", "").replace("/", "").strip()
        query_enc = urllib.parse.quote(parola_chiave)
        url = f"https://www.google.com/search?q={query_enc}"
    else:
        url = "https://www.google.com"

    try:
        pc_index.apri_percorso(url)
        return f"Sto aprendo il browser su {piattaforma}."
    except Exception as e:
        return f"Impossibile aprire il browser: {e}"


def esegui_apri_programma(nome):
    """
    Apre un programma/app. Logica intelligente:
    1. Cerca tra app di sistema conosciute
    2. Cerca tra app installate (indice con fuzzy matching)
    3. Fallback: apre come web app se disponibile
    """
    if not nome:
        return "Quale programma vuoi aprire?"

    # Usa pc_index per trovare l'app in modo smart
    info = pc_index.trova_app_smart(nome)

    if info:
        return pc_index.apri_app(info)

    # Ultimo fallback: prova ad eseguire il comando diretto
    chiave = nome.strip().lower()
    try:
        if sys.platform.startswith('win'):
            subprocess.Popen(chiave, shell=True)
            return f"Provo ad aprire {nome}."
        elif sys.platform.startswith('darwin'):
            subprocess.run(["open", "-a", nome])
            return f"Apro {nome}."
        else:
            subprocess.Popen([chiave])
            return f"Apro {nome}."
    except Exception as e:
        return f"Non riesco ad aprire '{nome}': {e}"


def esegui_apri_cartella(nome):
    """Apre una cartella usando pc_index (fuzzy matching + cartelle note)."""
    if not nome:
        return "Quale cartella vuoi aprire?"

    percorso = pc_index.trova_cartella_smart(nome)

    if not percorso:
        return f"Non trovo la cartella '{nome}'."

    if not os.path.exists(percorso):
        return f"Non trovo la cartella '{nome}'."

    if pc_index.apri_percorso(percorso):
        return f"Apro la cartella {nome}."
    else:
        return f"Non riesco ad aprire la cartella '{nome}'."


def esegui_apri_file(nome):
    """
    Trova un file con ricerca smart (scoring + fuzzy) e lo apre.
    Usa pc_index.trova_file_smart() invece della vecchia ricerca per substring.
    """
    if not nome:
        return "Quale file vuoi aprire?"

    index = pc_index.get_index()
    risultati = pc_index.trova_file_smart(nome.strip(), index)

    if not risultati:
        return f"Non ho trovato nessun file chiamato '{nome}'."

    # Apre il primo (miglior punteggio, più recente)
    percorso = risultati[0]["path"]
    nomefile = risultati[0]["name"]
    score = risultati[0]["score"]

    if pc_index.apri_percorso(percorso):
        extra = ""
        if len(risultati) > 1:
            extra = f" (il migliore tra {len(risultati)} risultati, score {score})"
        return f"Apro il file {nomefile}{extra}, puoi modificarlo."
    else:
        return f"Non riesco ad aprire il file '{nomefile}'."


def apri_percorso(percorso):
    """Apre un file (percorso completo) nel suo programma predefinito."""
    nomefile = os.path.basename(percorso)
    if pc_index.apri_percorso(percorso):
        return f"Apro {nomefile}, puoi modificarlo."
    else:
        return f"Non riesco ad aprire {nomefile}."


def _mostra_in_explorer(percorso):
    """Apre Esplora risorse mostrando (e selezionando) il file."""
    try:
        if sys.platform.startswith('win'):
            subprocess.Popen(f'explorer /select,"{percorso}"')
        elif sys.platform.startswith('darwin'):
            subprocess.run(["open", "-R", percorso])
        else:
            subprocess.run(["xdg-open", os.path.dirname(percorso)])
    except Exception:
        pass


def _apri_cartella_percorso(cartella):
    try:
        pc_index.apri_percorso(cartella)
    except Exception:
        pass


def esegui_cerca_file(nome, max_risultati=20):
    """Cerca un file per nome con scoring smart e APRE le cartelle mostrando i documenti."""
    if not nome:
        return "Quale file devo cercare?"

    index = pc_index.get_index()
    risultati = pc_index.trova_file_smart(nome.strip(), index, max_risultati=max_risultati)

    if not risultati:
        return f"Non ho trovato nessun file chiamato '{nome}'."

    # Mostra a schermo l'elenco (NON viene letto a voce)
    print(f"[FILE TROVATI] {len(risultati)} risultati per '{nome}':")
    for r in risultati:
        print(f"  - [score={r['score']}] {r['path']}")

    n = len(risultati)
    if n == 1:
        _mostra_in_explorer(risultati[0]["path"])
        return f"Ho trovato il file {risultati[0]['name']}, te lo mostro."

    # Più file: apri le cartelle uniche (max 3 finestre)
    cartelle_uniche = []
    for r in risultati:
        d = os.path.dirname(r["path"])
        if d not in cartelle_uniche:
            cartelle_uniche.append(d)

    if n <= 4:
        for r in risultati:
            _mostra_in_explorer(r["path"])
    else:
        for d in cartelle_uniche[:3]:
            _apri_cartella_percorso(d)

    return f"Ho trovato {n} file chiamati '{nome}'. Te li apro nelle cartelle."
