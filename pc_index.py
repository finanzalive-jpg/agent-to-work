"""
pc_index.py - Indicizzazione e ricerca smart di file, cartelle e app.

Ispirato a AI-Voice-Desktop-Assistant (github.com/Abdur-Rahman-Argon/AI-Voice-Desktop-Assistant).
Costruisce un indice delle cartelle utente all'avvio e offre ricerca con punteggio
(fuzzy matching, scoring per parola, penalità antonimi).

Uso:
    from pc_index import get_index, trova_file_smart, trova_app_smart, trova_cartella_smart

    index = get_index()  # costruisce o ritorna cache
    risultati = trova_file_smart("preventivo mario", index)
    app_path = trova_app_smart("whatsapp", index)
"""
import os
import re
import sys
import platform
from difflib import get_close_matches, SequenceMatcher

# ---------------------------------------------------------------- INDICE
_INDICE_CACHE = None


def _cartelle_utente():
    """Cartelle principali dell'utente da indicizzare."""
    home = os.path.expanduser("~")
    cartelle = [
        os.path.join(home, "Desktop"),
        os.path.join(home, "Documents"),
        os.path.join(home, "Downloads"),
        os.path.join(home, "Pictures"),
        os.path.join(home, "Music"),
        os.path.join(home, "Videos"),
    ]
    # Windows: aggiungi OneDrive se esiste
    onedrive = os.path.join(home, "OneDrive")
    if os.path.isdir(onedrive):
        cartelle.append(onedrive)
    return [c for c in cartelle if os.path.isdir(c)]


def build_index(force=False):
    """Costruisce l'indice di file, cartelle e app. Cachea il risultato."""
    global _INDICE_CACHE
    if _INDICE_CACHE and not force:
        return _INDICE_CACHE

    files = []
    folders = []
    apps = []

    for search_dir in _cartelle_utente():
        for root, dirs, filelist in os.walk(search_dir):
            # Salta cartelle nascoste
            dirs[:] = [d for d in dirs if not d.startswith(".")]
            for d in dirs:
                folders.append((d, os.path.join(root, d)))
            for f in filelist:
                if not f.startswith("."):
                    files.append((f, os.path.join(root, f)))

    # App: su Windows cerca nel menu Start e in Program Files
    if sys.platform.startswith("win"):
        apps = _trova_app_windows()

    _INDICE_CACHE = {"files": files, "folders": folders, "apps": apps}
    print(f"[pc_index] Indicizzati {len(files)} file, {len(folders)} cartelle, {len(apps)} app")
    return _INDICE_CACHE


def get_index():
    """Ritorna l'indice (lo costruisce se non esiste)."""
    return build_index()


def _trova_app_windows():
    """Cerca app installate su Windows tramite menu Start e Program Files."""
    apps = []
    home = os.path.expanduser("~")
    search_paths = [
        os.path.join(home, "AppData", "Roaming", "Microsoft", "Windows", "Start Menu", "Programs"),
        r"C:\ProgramData\Microsoft\Windows\Start Menu\Programs",
    ]
    for sp in search_paths:
        if not os.path.isdir(sp):
            continue
        for root, dirs, files in os.walk(sp):
            for f in files:
                if f.lower().endswith((".lnk", ".exe")):
                    nome = os.path.splitext(f)[0]
                    apps.append((nome, os.path.join(root, f)))
    return apps


# ---------------------------------------------------------------- NORMALIZZAZIONE

def _normalizza(testo):
    """Rimuove spazi, trattini, underscore e mette in minuscolo."""
    return re.sub(r"[-_\s]+", "", (testo or "").lower())


def _parole(testo):
    """Spezza il testo in parole (split su spazi, trattini, underscore, punti)."""
    return [w for w in re.split(r"[-_\s\.]+", (testo or "").lower()) if w]


# ---------------------------------------------------------------- SCORING (da AI-Voice-Desktop-Assistant)

# Coppie di antonimi per penalizzare match fuorvianti
_ANTONIMI = [
    ("vecchio", "nuovo"), ("nuovo", "vecchio"),
    ("bozza", "finale"), ("finale", "bozza"),
    ("interno", "esterno"), ("esterno", "interno"),
    ("draft", "final"), ("final", "draft"),
    ("old", "new"), ("new", "old"),
    ("temp", "definitivo"), ("definitivo", "temp"),
]

# Estensioni comuni per tipo di file
_EXT_TIPO = {
    "word": [".docx", ".doc"],
    "excel": [".xlsx", ".xls"],
    "pdf": [".pdf"],
    "powerpoint": [".pptx", ".ppt"],
    "immagine": [".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp"],
    "testo": [".txt", ".md", ".rtf"],
}


def _punteggio_file(parole_query, parole_file, ext_file=None, ext_cercata=None):
    """Calcola un punteggio di match tra query e nome file."""
    score = 0

    for qw in parole_query:
        # Match esatto sulla parola
        if qw in parole_file:
            score += 2
        # Fuzzy match (cutoff 0.7 = abbastanza simile)
        elif get_close_matches(qw, parole_file, n=1, cutoff=0.7):
            score += 1

    # Penalizza antonimi
    for q in parole_query:
        for f in parole_file:
            for a, b in _ANTONIMI:
                if q == a and b in parole_file:
                    score -= 2

    # Bonus se l'estensione corrisponde a quella cercata
    if ext_cercata and ext_file:
        if ext_file.lower() == ext_cercata.lower():
            score += 1

    return score


# ---------------------------------------------------------------- RICERCA FILE

def trova_file_smart(query, index=None, tipo_file=None, max_risultati=20):
    """
    Cerca file con scoring intelligente (ispirato a AI-Voice-Desktop-Assistant).

    Args:
        query: cosa cercare (es. "preventivo mario", "fattura 2024")
        index: indice precostruito (se None, lo costruisce)
        tipo_file: filtro estensione (es. ".docx", ".pdf") o tipo ("word", "excel")
        max_risultati: massimo risultati

    Returns:
        lista di dict {name, path, score, ext} ordinata per punteggio decrescente
    """
    if index is None:
        index = get_index()

    parole_query = _parole(query)
    if not parole_query:
        return []

    # Risolvi tipo_file in estensione
    ext_cercata = None
    if tipo_file:
        if tipo_file.startswith("."):
            ext_cercata = tipo_file
        elif tipo_file.lower() in _EXT_TIPO:
            ext_cercata = _EXT_TIPO[tipo_file.lower()][0]
        else:
            ext_cercata = "." + tipo_file.lstrip(".")

    risultati = []
    for nome, percorso in index["files"]:
        # Filtro per estensione se specificato
        ext = os.path.splitext(nome)[1].lower()
        if ext_cercata:
            # Se tipo_file è una categoria (es. "word"), accetta tutte le estensioni della categoria
            if tipo_file and tipo_file.lower() in _EXT_TIPO:
                if ext not in _EXT_TIPO[tipo_file.lower()]:
                    continue
            elif ext != ext_cercata.lower():
                continue

        parole_file = _parole(nome)
        score = _punteggio_file(parole_query, parole_file, ext, ext_cercata)

        if score > 0:
            risultati.append({
                "name": nome,
                "path": percorso,
                "score": score,
                "ext": ext,
            })

    # Ordina: punteggio decrescente, poi file più recente
    risultati.sort(key=lambda r: (-r["score"], -_mtime(r["path"])))
    return risultati[:max_risultati]


def _mtime(path):
    """Ritorna il tempo di modifica del file (0 se errore)."""
    try:
        return os.path.getmtime(path)
    except Exception:
        return 0


# ---------------------------------------------------------------- RICERCA APP

# Mappa app conosciute -> comando Windows (estesa da system_skills.py)
_APP_LOCALI = {
    "blocco note": "notepad", "notepad": "notepad", "note": "notepad",
    "calcolatrice": "calc", "calcolatore": "calc", "calc": "calc",
    "paint": "mspaint",
    "esplora risorse": "explorer", "esplora file": "explorer",
    "word": "winword", "excel": "excel", "powerpoint": "powerpnt",
    "outlook": "outlook", "onenote": "onenote",
    "browser": "", "internet": "", "chrome": "chrome", "edge": "msedge",
    "firefox": "firefox",
    "prompt": "cmd", "terminale": "cmd", "cmd": "cmd",
    "powershell": "powershell",
    "spotify": "spotify", "discord": "discord", "steam": "steam",
    "telegram": "telegram",
    "teams": "ms-teams",
    "task manager": "taskmgr", "gestione attività": "taskmgr",
    "impostazioni": "ms-settings:", "settings": "ms-settings:",
}

# Mappa app web (quando non c'è l'app locale installata)
_APP_WEB = {
    "whatsapp": "https://web.whatsapp.com",
    "web whatsapp": "https://web.whatsapp.com",
    "telegram": "https://web.telegram.org",
    "web telegram": "https://web.telegram.org",
    "gmail": "https://mail.google.com",
    "google drive": "https://drive.google.com",
    "google maps": "https://maps.google.com",
    "google calendar": "https://calendar.google.com",
    "youtube": "https://www.youtube.com",
    "chatgpt": "https://chat.openai.com",
    "claude": "https://claude.ai",
    "notion": "https://notion.so",
    "figma": "https://figma.com",
    "github": "https://github.com",
    "linkedin": "https://www.linkedin.com",
    "facebook": "https://www.facebook.com",
    "instagram": "https://www.instagram.com",
    "twitter": "https://www.x.com",
    "x": "https://www.x.com",
    "tiktok": "https://www.tiktok.com",
    "spotify": "https://open.spotify.com",
    "netflix": "https://www.netflix.com",
    "twitch": "https://www.twitch.tv",
    "slack": "https://slack.com",
    "zoom": "https://zoom.us",
    "trello": "https://trello.com",
}


# App di sistema che funzionano SEMPRE su Windows senza PATH completo
_APP_SISTEMA_SICURE = {
    "blocco note", "notepad", "note", "calcolatrice", "calcolatore", "calc",
    "paint", "esplora risorse", "esplora file", "prompt", "terminale", "cmd",
    "powershell", "task manager", "gestione attività", "impostazioni", "settings",
    "browser", "internet",
}


def trova_app_smart(nome, index=None):
    """
    Cerca un'app per nome. Logica:
    1. App di sistema sicure (notepad, calc, ecc. - funzionano sempre)
    2. Indice app installate (percorso .lnk completo dal menu Start)
    3. Match in _APP_LOCALI (per app non trovate nell'indice)
    4. Fallback su _APP_WEB (versione web)

    Returns:
        dict {type: "locale"|"web", command: str, name: str} o None
    """
    if index is None:
        index = get_index()

    chiave = _normalizza(nome)
    chiave_lower = nome.strip().lower()

    # 1. Solo app di sistema sicure (calc, notepad, cmd, ecc.)
    for k, cmd in _APP_LOCALI.items():
        if k in _APP_SISTEMA_SICURE:
            if chiave == _normalizza(k) or _normalizza(k) in chiave or chiave in _normalizza(k):
                return {"type": "locale", "command": cmd, "name": k}

    # 2. App installate dall'indice (hanno percorso .lnk completo!)
    if index.get("apps"):
        nomi_app = [_normalizza(a[0]) for a in index["apps"]]
        # Prima: match esatto o contenimento
        for i, n in enumerate(nomi_app):
            if chiave == n or chiave in n or n in chiave:
                return {"type": "locale", "command": index["apps"][i][1], "name": index["apps"][i][0]}
        # Poi: fuzzy match
        matches = get_close_matches(chiave, nomi_app, n=1, cutoff=0.6)
        if matches:
            idx = nomi_app.index(matches[0])
            return {"type": "locale", "command": index["apps"][idx][1], "name": index["apps"][idx][0]}

    # 3. Fallback _APP_LOCALI (app non sicure come word, excel - ultimo tentativo)
    for k, cmd in _APP_LOCALI.items():
        if k not in _APP_SISTEMA_SICURE:
            if chiave == _normalizza(k) or _normalizza(k) in chiave or chiave in _normalizza(k):
                return {"type": "locale", "command": cmd, "name": k}

    # 4. Fallback web app
    for k, url in _APP_WEB.items():
        if chiave == _normalizza(k) or _normalizza(k) in chiave or chiave in _normalizza(k):
            return {"type": "web", "command": url, "name": k}

    return None


# ---------------------------------------------------------------- RICERCA CARTELLE

# Cartelle note (estese)
_CARTELLE_NOTE = {
    "desktop": "Desktop", "scrivania": "Desktop",
    "download": "Downloads", "scaricati": "Downloads", "downloads": "Downloads",
    "documenti": "Documents", "documents": "Documents",
    "immagini": "Pictures", "foto": "Pictures", "pictures": "Pictures",
    "musica": "Music", "music": "Music",
    "video": "Videos", "videos": "Videos", "film": "Videos",
    "home": "", "casa": "",
    "onedrive": "OneDrive",
}


def trova_cartella_smart(nome, index=None):
    """
    Cerca una cartella per nome.
    1. Match in cartelle note (Desktop, Downloads, ecc.)
    2. Fuzzy match nell'indice cartelle

    Returns:
        percorso completo o None
    """
    if index is None:
        index = get_index()

    chiave = nome.strip().lower()
    home = os.path.expanduser("~")

    # 1. Cartelle note
    for k, v in _CARTELLE_NOTE.items():
        if k in chiave:
            percorso = os.path.join(home, v) if v else home
            if os.path.isdir(percorso):
                return percorso

    # 2. Sottocartella del Desktop
    percorso_desktop = os.path.join(home, "Desktop", nome.strip())
    if os.path.isdir(percorso_desktop):
        return percorso_desktop

    # 3. Fuzzy match nell'indice
    if index.get("folders"):
        nomi_cartelle = [_normalizza(f[0]) for f in index["folders"]]
        chiave_norm = _normalizza(nome)
        # Prima: match esatto o contenimento
        for i, n in enumerate(nomi_cartelle):
            if chiave_norm == n or chiave_norm in n:
                return index["folders"][i][1]
        # Poi: fuzzy
        matches = get_close_matches(chiave_norm, nomi_cartelle, n=1, cutoff=0.6)
        if matches:
            idx = nomi_cartelle.index(matches[0])
            return index["folders"][idx][1]

    return None


# ---------------------------------------------------------------- APERTURA UNIFICATA

def apri_percorso(percorso):
    """Apre un file o cartella nel programma predefinito. Cross-platform."""
    try:
        if sys.platform.startswith("win"):
            os.startfile(percorso)
        elif sys.platform.startswith("darwin"):
            import subprocess
            subprocess.run(["open", percorso])
        else:
            import subprocess
            subprocess.run(["xdg-open", percorso])
        return True
    except Exception as e:
        print(f"[pc_index] Errore apertura {percorso}: {e}")
        return False


def apri_app(info_app):
    """
    Apre un'app dal risultato di trova_app_smart().

    Args:
        info_app: dict da trova_app_smart()

    Returns:
        str: messaggio di conferma
    """
    import subprocess

    if info_app["type"] == "web":
        apri_percorso(info_app["command"])
        return f"Apro {info_app['name']} nel browser."

    cmd = info_app["command"]
    if not cmd:
        # Browser predefinito
        apri_percorso("https://www.google.com")
        return "Apro il browser."

    try:
        if sys.platform.startswith("win"):
            if cmd.endswith(".lnk"):
                os.startfile(cmd)
            elif cmd.startswith("ms-"):
                os.startfile(cmd)
            else:
                subprocess.Popen(cmd, shell=True)
        elif sys.platform.startswith("darwin"):
            subprocess.run(["open", "-a", cmd])
        else:
            subprocess.Popen([cmd])
        return f"Apro {info_app['name']}."
    except Exception as e:
        # Se fallisce come app locale, prova come web app
        web = _APP_WEB.get(_normalizza(info_app["name"]))
        if web:
            apri_percorso(web)
            return f"Apro {info_app['name']} nel browser."
        return f"Non riesco ad aprire '{info_app['name']}': {e}"
