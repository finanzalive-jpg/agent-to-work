"""
documenti.py - Creazione e scrittura di documenti Office a voce.

Crea e compila a voce:
- Excel (.xlsx): es. "crea un file excel clienti", poi "aggiungi Mario Rossi, p.iva 123..."
- Word (.docx): es. "crea un documento word verbale", poi "scrivi ..."
- PDF (.pdf): idem

Usa il cervello (brain.chat_libero) per trasformare quello che dici in righe/colonne pulite.
I file vengono salvati sul Desktop.
"""
import os
import re
import json

import brain


def _desktop():
    home = os.path.expanduser("~")
    d = os.path.join(home, "Desktop")
    return d if os.path.isdir(d) else home


def _nome_file(nome, ext):
    base = "".join(c for c in (nome or "documento") if c.isalnum() or c in " _-").strip()
    return (base or "documento") + ext


# ---------------------------------------------------------------- CREAZIONE
def crea_excel(nome):
    from openpyxl import Workbook
    path = os.path.join(_desktop(), _nome_file(nome, ".xlsx"))
    wb = Workbook()
    ws = wb.active
    ws.title = (nome or "Foglio")[:31]
    wb.save(path)
    return path


def crea_word(nome):
    from docx import Document
    path = os.path.join(_desktop(), _nome_file(nome, ".docx"))
    doc = Document()
    if nome:
        doc.add_heading(nome, level=0)
    doc.save(path)
    return path


def crea_pdf(nome):
    path = os.path.join(_desktop(), _nome_file(nome, ".pdf"))
    scrivi_pdf(path, titolo=(nome or ""), righe=[])
    return path


# ---------------------------------------------------------------- SCRITTURA
def _estrai_voci(testo, brain_cfg):
    """Trasforma una frase in una LISTA di dizionari (una riga per voce/persona)."""
    sys = (
        "Estrai i dati dalla frase dell'utente e restituiscili come JSON. "
        "Se c'è UNA sola voce, restituisci un oggetto chiave-valore. "
        "Se ci sono PIÙ voci/persone, restituisci una LISTA di oggetti. "
        "Le chiavi sono nomi di colonna in italiano con iniziale maiuscola "
        "(es. Nome, Cognome, Partita IVA, Telefono, Email, Indirizzo, Note). "
        "Non inventare dati non presenti. Rispondi SOLO con il JSON, senza testo attorno."
    )
    out = brain.chat_libero(sys, testo, brain_cfg)
    m = re.search(r"(\[.*\]|\{.*\})", out, re.S)
    if m:
        try:
            dati = json.loads(m.group(1))
            if isinstance(dati, dict):
                return [dati]
            if isinstance(dati, list):
                return [d for d in dati if isinstance(d, dict)] or [{"Dato": testo}]
        except Exception:
            pass
    return [{"Dato": testo}]


def aggiungi_righe_excel(path, testo, brain_cfg):
    """Aggiunge una o più righe all'Excel, estraendo i campi dal parlato. Torna (n_righe, intestazioni)."""
    from openpyxl import load_workbook
    voci = _estrai_voci(testo, brain_cfg)
    wb = load_workbook(path)
    ws = wb.active

    # Intestazioni esistenti (prima riga non vuota)
    intest = []
    if ws.max_row >= 1:
        intest = [c.value for c in ws[1] if c.value]

    for voce in voci:
        # aggiunge eventuali colonne nuove
        for k in voce.keys():
            if k not in intest:
                intest.append(k)
        if ws.max_row == 1 and not [c.value for c in ws[1] if c.value]:
            # foglio vuoto: scrivi l'intestazione sulla riga 1
            for j, h in enumerate(intest, 1):
                ws.cell(row=1, column=j, value=h)
        else:
            # assicura che l'intestazione contenga tutte le colonne
            for j, h in enumerate(intest, 1):
                if ws.cell(row=1, column=j).value != h:
                    ws.cell(row=1, column=j, value=h)
        ws.append([voce.get(h, "") for h in intest])

    wb.save(path)
    return len(voci), intest


def imposta_intestazioni(path, colonne):
    """Scrive le intestazioni ESATTE sulla riga 1 (sovrascrive la riga 1)."""
    from openpyxl import load_workbook
    wb = load_workbook(path)
    ws = wb.active
    # pulisce la riga 1 e scrive le colonne richieste
    for j in range(1, max(ws.max_column, len(colonne)) + 1):
        ws.cell(row=1, column=j, value=(colonne[j - 1] if j - 1 < len(colonne) else None))
    wb.save(path)


def aggiungi_riga_valori(path, valori):
    """Aggiunge una riga con i valori nell'ORDINE dato (posizionale)."""
    from openpyxl import load_workbook
    wb = load_workbook(path)
    ws = wb.active
    ws.append([str(v) for v in valori])
    riga = ws.max_row
    wb.save(path)
    return riga


def mappa_valori(testo, colonne, brain_cfg):
    """Mappa quello che l'utente detta sulle colonne ESISTENTI, nell'ordine. Torna lista lunga come 'colonne'."""
    n = len(colonne)
    # Se l'utente ha scandito con le virgole, uso lo split diretto (deterministico)
    parti = [p.strip() for p in testo.split(",") if p.strip()]
    if len(parti) >= 2:
        return (parti + [""] * n)[:n]
    # Altrimenti chiedo al cervello di incasellare nelle colonne fisse
    sys = (
        "Le colonne della tabella sono, in quest'ordine: " + ", ".join(colonne) + ". "
        "Dalla frase dell'utente estrai i valori corrispondenti, NELLO STESSO ORDINE delle colonne. "
        "Rispondi SOLO con un array JSON di stringhe lungo esattamente " + str(n) + ", "
        "stringa vuota se un valore non è presente. Non aggiungere altre colonne, non spiegare."
    )
    out = brain.chat_libero(sys, testo, brain_cfg)
    m = re.search(r"\[.*\]", out, re.S)
    if m:
        try:
            arr = [str(x) for x in json.loads(m.group(0))]
            return (arr + [""] * n)[:n]
        except Exception:
            pass
    return (parti + [""] * n)[:n]


def aggiungi_paragrafo_word(path, testo):
    from docx import Document
    doc = Document(path)
    doc.add_paragraph(testo)
    doc.save(path)


def scrivi_pdf(path, titolo, righe):
    """(Ri)genera il PDF con titolo + tutte le righe."""
    from fpdf import FPDF
    pdf = FPDF()
    pdf.add_page()
    if titolo:
        pdf.set_font("Helvetica", "B", 16)
        pdf.multi_cell(0, 10, _latin(titolo))
        pdf.ln(2)
    pdf.set_font("Helvetica", size=12)
    for r in righe:
        pdf.multi_cell(0, 8, _latin(r))
        pdf.ln(1)
    pdf.output(path)


def _latin(s):
    """fpdf core font gestisce latin-1: sostituisce i caratteri fuori range."""
    return (s or "").encode("latin-1", "replace").decode("latin-1")
