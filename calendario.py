"""
calendario.py - Appuntamenti e agenda a voce.

- Crea appuntamenti: estrae data/ora dalla frase (col cervello) e genera un file .ics
  (si apre in Outlook/Google Calendar) + li salva in un'agenda locale (JSON).
- Legge l'agenda del giorno: "che appuntamenti ho oggi / domani".

Tutto locale, nessun account richiesto.
"""
import os
import re
import json
import datetime

import brain

_GIORNI = ["lunedì", "martedì", "mercoledì", "giovedì", "venerdì", "sabato", "domenica"]
_MESI = ["gennaio", "febbraio", "marzo", "aprile", "maggio", "giugno",
         "luglio", "agosto", "settembre", "ottobre", "novembre", "dicembre"]


def _desktop():
    home = os.path.expanduser("~")
    d = os.path.join(home, "Desktop")
    return d if os.path.isdir(d) else home


def _store_path():
    return os.path.join(_desktop(), "Agenda_Atlas.json")


def _carica():
    try:
        with open(_store_path(), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return []


def _salva(lista):
    with open(_store_path(), "w", encoding="utf-8") as f:
        json.dump(lista, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------- ESTRAZIONE
def estrai_evento(testo, brain_cfg):
    """Dal parlato ricava {titolo, data 'YYYY-MM-DD', ora 'HH:MM', durata_min, luogo}."""
    oggi = datetime.date.today()
    giorno = _GIORNI[oggi.weekday()]
    sys = (
        f"Oggi è {giorno} {oggi.isoformat()}. Estrai l'appuntamento dalla frase dell'utente in JSON "
        "con questi campi: titolo (stringa), data (YYYY-MM-DD), ora (HH:MM 24h), durata_min (numero), luogo (stringa). "
        "Risolvi 'oggi', 'domani', 'dopodomani', i giorni della settimana e le date relative rispetto a oggi. "
        "Se manca l'ora usa 09:00; se manca la durata usa 60; se manca il luogo usa stringa vuota. "
        "Rispondi SOLO con l'oggetto JSON."
    )
    out = brain.chat_libero(sys, testo, brain_cfg)
    m = re.search(r"\{.*\}", out, re.S)
    if m:
        try:
            d = json.loads(m.group(0))
            d.setdefault("titolo", "Appuntamento")
            d.setdefault("data", oggi.isoformat())
            d.setdefault("ora", "09:00")
            d.setdefault("durata_min", 60)
            d.setdefault("luogo", "")
            return d
        except Exception:
            pass
    return None


# ---------------------------------------------------------------- CREAZIONE
def _scrivi_ics(evento):
    """Crea un file .ics singolo sul Desktop (doppio clic = aggiunge al calendario)."""
    try:
        inizio = datetime.datetime.strptime(evento["data"] + " " + evento["ora"], "%Y-%m-%d %H:%M")
    except Exception:
        return None
    fine = inizio + datetime.timedelta(minutes=int(evento.get("durata_min", 60) or 60))
    uid = "atlas-" + inizio.strftime("%Y%m%d%H%M%S")
    ics = "\n".join([
        "BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//Atlas//Agenda//IT", "CALSCALE:GREGORIAN",
        "BEGIN:VEVENT",
        "UID:" + uid,
        "DTSTAMP:" + datetime.datetime.now().strftime("%Y%m%dT%H%M%S"),
        "DTSTART:" + inizio.strftime("%Y%m%dT%H%M%S"),
        "DTEND:" + fine.strftime("%Y%m%dT%H%M%S"),
        "SUMMARY:" + str(evento.get("titolo", "Appuntamento")),
        "LOCATION:" + str(evento.get("luogo", "")),
        "END:VEVENT", "END:VCALENDAR",
    ])
    nome = re.sub(r"[^\w\- ]", "", str(evento.get("titolo", "appuntamento"))).strip() or "appuntamento"
    path = os.path.join(_desktop(), f"{nome}_{inizio.strftime('%d-%m_%H%M')}.ics")
    with open(path, "w", encoding="utf-8") as f:
        f.write(ics)
    return path


def aggiungi(evento):
    """Salva l'evento nell'agenda locale e crea il file .ics. Torna (path_ics, evento)."""
    lista = _carica()
    lista.append(evento)
    lista.sort(key=lambda e: (e.get("data", ""), e.get("ora", "")))
    _salva(lista)
    path = _scrivi_ics(evento)
    return path, evento


# ---------------------------------------------------------------- LETTURA
def eventi_del_giorno(data_iso):
    return [e for e in _carica() if e.get("data") == data_iso]


def frase_data(data_iso):
    try:
        d = datetime.date.fromisoformat(data_iso)
        return f"{_GIORNI[d.weekday()]} {d.day} {_MESI[d.month - 1]}"
    except Exception:
        return data_iso


def descrivi_lista(eventi, data_iso):
    """Frase da leggere data una lista di eventi (da locale o da Google)."""
    quando = frase_data(data_iso)
    if not eventi:
        return f"Per {quando} non hai appuntamenti."
    pezzi = []
    for e in eventi:
        p = f"alle {e.get('ora', '')} {e.get('titolo', '')}"
        if e.get("luogo"):
            p += f" a {e['luogo']}"
        pezzi.append(p)
    return f"Per {quando} hai {len(eventi)} appuntamenti: " + "; ".join(pezzi) + "."


def descrivi_giornata(data_iso):
    """Frase da leggere con gli appuntamenti LOCALI del giorno."""
    return descrivi_lista(eventi_del_giorno(data_iso), data_iso)
