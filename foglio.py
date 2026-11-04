"""
foglio.py - Motore Excel ad AZIONI (ispirato a SheetCopilot).

Invece di programmare ogni operazione, definiamo un vocabolario di AZIONI atomiche.
Il cervello (Groq) traduce l'ordine vocale dell'utente in una lista di azioni JSON,
e qui le eseguiamo con openpyxl. Così l'utente può dire liberamente:
colonne, righe, formule, colori, grassetto, titoli, larghezza...

Azioni supportate (campo "azione"):
- intestazioni   {"colonne": ["Nome","Cognome","Totale"]}
- aggiungi_riga  {"valori": ["Mario","Rossi","100"]}
- scrivi_cella   {"cella": "B2", "valore": "ciao"}
- formula        {"cella": "D2", "formula": "=B2*C2"}
- formato        {"intervallo": "A1:C1", "grassetto": true, "colore_testo": "bianco", "sfondo": "blu", "centrato": true}
- titolo         {"testo": "Clienti 2026", "colonne": 3}
- larghezza      {"colonna": "A", "valore": 25}
"""
import json
import re

import brain

from openpyxl import load_workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.utils import get_column_letter

# Nomi colore italiani -> esadecimale
COLORI = {
    "rosso": "FF0000", "verde": "008000", "verde chiaro": "90EE90", "blu": "1F4E78",
    "azzurro": "2E75B6", "giallo": "FFFF00", "arancione": "ED7D31", "viola": "7030A0",
    "grigio": "808080", "grigio chiaro": "D9D9D9", "nero": "000000", "bianco": "FFFFFF",
    "oro": "BF9000", "rosa": "FF99CC", "marrone": "843C0C", "celeste": "9DC3E6",
}


def _hex(colore):
    if not colore:
        return None
    c = str(colore).strip().lower().lstrip("#")
    if c in COLORI:
        return COLORI[c]
    if re.fullmatch(r"[0-9a-fA-F]{6}", c):
        return c.upper()
    # prova una parola chiave contenuta
    for k, v in COLORI.items():
        if k in c:
            return v
    return None


def _righe_unite(ws):
    r = set()
    for rng in ws.merged_cells.ranges:
        r.update(range(rng.min_row, rng.max_row + 1))
    return r

def _riga_intestazioni(ws):
    """La riga delle intestazioni: la 1, oppure la 2 se la 1 è un titolo unito."""
    unite = _righe_unite(ws)
    r = 1
    while r in unite:
        r += 1
    return r

def _prossima_riga_vuota(ws):
    r = ws.max_row
    while r >= 1 and all((ws.cell(row=r, column=c).value in (None, "")) for c in range(1, ws.max_column + 1)):
        r -= 1
    return r + 1


# ---------------------------------------------------------------- ESECUZIONE
def esegui_azione(path, az):
    """Applica UNA azione al foglio. Torna una breve frase di conferma."""
    wb = load_workbook(path)
    ws = wb.active
    tipo = (az.get("azione") or "").lower()
    msg = "Fatto."

    if tipo == "intestazioni":
        cols = az.get("colonne", [])
        rh = _riga_intestazioni(ws)
        for j, h in enumerate(cols, 1):
            try:
                ws.cell(row=rh, column=j, value=h)
            except Exception:
                pass
        msg = ("Colonne impostate: " + ", ".join(cols) + ".") if cols else "Nessuna colonna indicata."

    elif tipo == "aggiungi_riga":
        valori = az.get("valori", [])
        r = _prossima_riga_vuota(ws)
        for j, v in enumerate(valori, 1):
            ws.cell(row=r, column=j, value=v)
        msg = "Riga aggiunta."

    elif tipo == "scrivi_cella":
        cella = az.get("cella")
        if cella:
            ws[cella] = az.get("valore", "")
            msg = f"Scritto in {cella}."

    elif tipo == "formula":
        cella = az.get("cella")
        formula = az.get("formula", "")
        if cella and formula:
            if not formula.startswith("="):
                formula = "=" + formula
            ws[cella] = formula
            msg = f"Formula inserita in {cella}."

    elif tipo == "formato":
        intervallo = az.get("intervallo") or az.get("cella")
        if intervallo:
            grass = bool(az.get("grassetto"))
            ct = _hex(az.get("colore_testo"))
            sf = _hex(az.get("sfondo"))
            centrato = bool(az.get("centrato"))
            righe = ws[intervallo] if ":" in str(intervallo) else [[ws[intervallo]]]
            for riga in righe:
                for cell in (riga if isinstance(riga, (list, tuple)) else [riga]):
                    try:
                        if grass or ct:
                            cell.font = Font(bold=grass, color=ct if ct else None)
                        if sf:
                            cell.fill = PatternFill("solid", fgColor=sf)
                        if centrato:
                            cell.alignment = Alignment(horizontal="center", vertical="center")
                    except Exception:
                        pass  # celle unite: salta
            msg = "Formato applicato."

    elif tipo == "titolo":
        testo = az.get("testo", "")
        n = int(az.get("colonne", ws.max_column or 1) or 1)
        n = max(1, n)
        # inserisce una riga in cima
        ws.insert_rows(1)
        ws.merge_cells(start_row=1, start_column=1, end_row=1, end_column=n)
        c = ws.cell(row=1, column=1, value=testo)
        c.font = Font(bold=True, size=16)
        c.alignment = Alignment(horizontal="center")
        msg = f"Titolo '{testo}' aggiunto."

    elif tipo == "larghezza":
        col = az.get("colonna", "A")
        val = az.get("valore", 20)
        try:
            ws.column_dimensions[str(col).upper()].width = float(val)
            msg = "Larghezza impostata."
        except Exception:
            msg = "Non ho capito la larghezza."

    else:
        msg = None  # azione sconosciuta

    wb.save(path)
    return msg


# ---------------------------------------------------------------- INTERPRETE
def _contesto(path):
    try:
        wb = load_workbook(path)
        ws = wb.active
        rh = _riga_intestazioni(ws)
        intest = [c.value for c in ws[rh] if c.value]
        return f"Colonne attuali: {intest if intest else 'nessuna'}. Righe totali: {ws.max_row}."
    except Exception:
        return "Foglio nuovo e vuoto."


def interpreta(comando, path, brain_cfg):
    """Il cervello traduce l'ordine vocale in una LISTA di azioni JSON. Torna lista (può essere vuota)."""
    sys = (
        "Sei il controllore di un foglio Excel. Converti l'ordine dell'utente in una LISTA JSON di azioni. "
        "Azioni possibili (campo 'azione') e campi:\n"
        "- intestazioni {colonne:[...]}  (imposta le colonne della riga 1)\n"
        "- aggiungi_riga {valori:[...]}  (una nuova riga di dati, nell'ordine delle colonne)\n"
        "- scrivi_cella {cella:'B2', valore:'...'}\n"
        "- formula {cella:'D2', formula:'=B2*C2'}  (usa riferimenti e funzioni Excel in INGLESE: SUM, AVERAGE...)\n"
        "- formato {intervallo:'A1:C1', grassetto:true, colore_testo:'bianco', sfondo:'blu', centrato:true}\n"
        "- titolo {testo:'...', colonne:3}\n"
        "- larghezza {colonna:'A', valore:25}\n"
        "Regole: usa i nomi colore in italiano (rosso, blu, verde, giallo, arancione, grigio...). "
        "Se l'utente chiede più cose, metti più azioni nella lista, in ordine. "
        "Se dice solo dei dati da inserire come riga, usa aggiungi_riga. "
        "Rispondi SOLO con l'array JSON, senza testo attorno. "
        "Contesto: " + _contesto(path)
    )
    out = brain.chat_libero(sys, comando, brain_cfg)
    m = re.search(r"\[.*\]", out, re.S)
    if not m:
        # magari ha restituito un singolo oggetto
        m2 = re.search(r"\{.*\}", out, re.S)
        if m2:
            try:
                return [json.loads(m2.group(0))]
            except Exception:
                return []
        return []
    try:
        dati = json.loads(m.group(0))
        return [d for d in dati if isinstance(d, dict)]
    except Exception:
        return []


def esegui_comando(path, comando, brain_cfg):
    """Interpreta ed esegue un ordine vocale sul foglio. Torna la frase da dire."""
    azioni = interpreta(comando, path, brain_cfg)
    if not azioni:
        return "Non ho capito cosa fare sul foglio. Prova a dirlo in modo più semplice."
    esiti = []
    for az in azioni:
        try:
            m = esegui_azione(path, az)
            if m:
                esiti.append(m)
        except PermissionError:
            return "Il foglio è aperto in un altro programma. Chiudilo e riprova."
        except Exception as e:
            print(f"[foglio] errore azione {az}: {e}")
    if not esiti:
        return "Non sono riuscito a eseguire il comando sul foglio."
    # frase breve
    return " ".join(esiti[:3]) + ("" if len(esiti) <= 3 else f" E altre {len(esiti)-3} operazioni.")
