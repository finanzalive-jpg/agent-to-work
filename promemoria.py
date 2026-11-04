"""
promemoria.py - Produttività: to-do, note, rubrica contatti.

Tutto salvato in file locali sul Desktop:
- todo_atlas.json      (cose da fare)
- note_atlas.txt       (appunti dettati)
- rubrica_atlas.json   (contatti: nome -> numero)
"""
import os
import re
import json


def _desktop():
    home = os.path.expanduser("~")
    d = os.path.join(home, "Desktop")
    return d if os.path.isdir(d) else home


def _p(nome):
    return os.path.join(_desktop(), nome)


def _carica_json(nome, default):
    try:
        with open(_p(nome), "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return default


def _salva_json(nome, dati):
    with open(_p(nome), "w", encoding="utf-8") as f:
        json.dump(dati, f, ensure_ascii=False, indent=2)


# ---------------------------------------------------------------- TO-DO
def _pulisci_todo(testo):
    return re.sub(r"^\s*(ricordami di|ricordami che devo|ricordami|devo|aggiungi|segna|promemoria|nota)\b[:,]?\s*",
                  "", (testo or ""), flags=re.I).strip(" .")


def aggiungi_todo(testo):
    t = _pulisci_todo(testo)
    if not t:
        return "Cosa devo ricordarti?"
    lista = _carica_json("todo_atlas.json", [])
    lista.append({"testo": t, "fatto": False})
    _salva_json("todo_atlas.json", lista)
    return f"Promemoria aggiunto: {t}."


def lista_todo():
    lista = [x for x in _carica_json("todo_atlas.json", []) if not x.get("fatto")]
    if not lista:
        return "Non hai promemoria da fare."
    voci = "; ".join(x["testo"] for x in lista)
    return f"Hai {len(lista)} cose da fare: {voci}."


def completa_todo(testo):
    chiave = _pulisci_todo(testo).lower()
    lista = _carica_json("todo_atlas.json", [])
    for x in lista:
        if not x.get("fatto") and (chiave in x["testo"].lower() or x["testo"].lower() in chiave):
            x["fatto"] = True
            _salva_json("todo_atlas.json", lista)
            return f"Segnato come fatto: {x['testo']}."
    return "Non ho trovato quel promemoria."


# ---------------------------------------------------------------- NOTE
def _pulisci_nota(testo):
    return re.sub(r"^\s*(prendi nota|prendi appunto|appunta|annota|nota|scrivi nota)\b[:,]?\s*",
                  "", (testo or ""), flags=re.I).strip()


def aggiungi_nota(testo):
    t = _pulisci_nota(testo)
    if not t:
        return "Cosa devo annotare?"
    import datetime
    riga = datetime.datetime.now().strftime("%d/%m %H:%M") + " - " + t + "\n"
    with open(_p("note_atlas.txt"), "a", encoding="utf-8") as f:
        f.write(riga)
    return "Nota salvata."


def _nomefile_blocco(titolo):
    base = re.sub(r"[^\w\- ]", "", titolo or "appunti").strip() or "appunti"
    return f"Note - {base}.txt"


def crea_blocco(titolo):
    """Crea (se non esiste) un bloc-notes dedicato e torna il percorso."""
    import datetime
    path = _p(_nomefile_blocco(titolo))
    if not os.path.exists(path):
        with open(path, "w", encoding="utf-8") as f:
            f.write(f"NOTE: {titolo}  ({datetime.datetime.now().strftime('%d/%m/%Y')})\n\n")
    return path


def _pulisci_contenuto(testo):
    t = (testo or "").strip()
    pat = re.compile(r"^(nelle note|nella nota|nel blocco|note|nota|scrivi|aggiungi|inserisci|annota|metti|segna)\b[:,]?\s*", re.I)
    prev = None
    while t != prev:
        prev = t
        t = pat.sub("", t, count=1).strip()
    return t


def aggiungi_al_blocco(path, testo):
    t = _pulisci_contenuto(testo)
    if not t:
        return False
    with open(path, "a", encoding="utf-8") as f:
        f.write("- " + t + "\n")
    return True


def leggi_note(quante=5):
    try:
        with open(_p("note_atlas.txt"), "r", encoding="utf-8") as f:
            righe = [r.strip() for r in f if r.strip()]
    except Exception:
        righe = []
    if not righe:
        return "Non hai note."
    ultime = righe[-quante:]
    return "Le tue ultime note: " + "; ".join(r.split(" - ", 1)[-1] for r in ultime) + "."


# ---------------------------------------------------------------- RUBRICA
def estrai_contatto(testo):
    """Da 'salva il numero di Mario Rossi 333 1234567' -> ('Mario Rossi', '3331234567')."""
    numero = re.sub(r"\D", "", testo or "")
    nome = re.sub(r"[0-9]", "", testo or "")
    nome = re.sub(r"(salva|il numero di|numero di|il contatto di|contatto di|contatto|numero|rubrica|aggiungi)",
                  "", nome, flags=re.I)
    nome = nome.strip(" .,-")
    return nome, numero


def salva_contatto(testo):
    nome, numero = estrai_contatto(testo)
    if not nome or not numero:
        return "Dimmi nome e numero, ad esempio: salva il numero di Mario 333 1234567."
    rub = _carica_json("rubrica_atlas.json", {})
    rub[nome.lower()] = {"nome": nome, "numero": numero}
    _salva_json("rubrica_atlas.json", rub)
    return f"Contatto salvato: {nome}, {numero}."


def trova_contatto(testo):
    nome = re.sub(r"(qual è|qual e|il numero di|numero di|trova|cerca|contatto di|chiama|dammi)",
                  "", (testo or ""), flags=re.I).strip(" ?.,")
    rub = _carica_json("rubrica_atlas.json", {})
    # match esatto o parziale
    key = nome.lower()
    if key in rub:
        c = rub[key]
        return f"Il numero di {c['nome']} è {c['numero']}."
    for k, c in rub.items():
        if key and (key in k or k in key):
            return f"Il numero di {c['nome']} è {c['numero']}."
    return f"Non ho trovato {nome} in rubrica." if nome else "Chi devo cercare in rubrica?"
