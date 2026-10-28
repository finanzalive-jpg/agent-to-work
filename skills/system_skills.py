import os
import sys
import subprocess
import urllib.parse

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
        # FIX DEFINITIVO: Rimuove tentativi di link sporchi generati dall'IA
        parola_chiave = query_ricerca.replace("https", "").replace("http", "").replace("youtube.com", "").replace("/", "").strip()
        query_enc = urllib.parse.quote(parola_chiave)
        # Forza l'indirizzo di ricerca corretto con i parametri di YouTube
        url = f"https://youtube.com{query_enc}"
    elif query_ricerca:
        # FIX DEFINITIVO: Rimuove tentativi di link sporchi generati dall'IA per Google
        parola_chiave = query_ricerca.replace("https", "").replace("http", "").replace("google.com", "").replace("/", "").strip()
        query_enc = urllib.parse.quote(parola_chiave)
        url = f"https://google.com{query_enc}"
    else:
        url = "https://google.com"

    try:
        if sys.platform.startswith('win'):
            os.startfile(url)
        elif sys.platform.startswith('darwin'):
            subprocess.run(["open", url])
        else:
            subprocess.run(["xdg-open", url])
        return f"Sto aprendo il browser su {piattaforma}."
    except Exception as e:
        return f"Impossibile aprire il browser: {e}"
