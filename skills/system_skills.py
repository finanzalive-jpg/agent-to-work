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
    
    if not os.path.exists(percorso_desktop):
        percorso_desktop = os.path.join(home, "Desktop")
        
    percorso_finale = os.path.join(percorso_desktop, nome_cartella)
    
    try:
        if not os.path.exists(percorso_finale):
            os.makedirs(percorso_finale)
            return f"Ok, ho creato la cartella '{nome_cartella}' sul tuo Desktop."
        else:
            return f"La cartella '{nome_cartella}' esiste già sul Desktop."
    except Exception as e:
        return f"Errore hardware durante la creazione della cartella: {e}"

def esegui_apri_browser(query_ricerca=None, piattaforma="google"):
    """Apre il browser predefinito con l'URL corretto."""
    if piattaforma == "youtube" and query_ricerca:
        query_enc = urllib.parse.quote(query_ricerca.strip())
        url = f"https://youtube.com{query_enc}"
    elif query_ricerca:
        query_enc = urllib.parse.quote(query_ricerca.strip())
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
