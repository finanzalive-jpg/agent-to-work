"""
office_skills.py - Creazione documenti Office professionali.

Usa officecli_bridge per creare Word/Excel/PowerPoint con tabelle,
formattazione e layout professionale (senza bisogno di MS Office).
Fallback a python-docx se OfficeCLI non è installato.
"""
import os
import sys

# Importa officecli_bridge
try:
    import officecli_bridge as ocli
except ImportError:
    import importlib.util as _ilu
    _spec = _ilu.spec_from_file_location(
        "officecli_bridge",
        os.path.join(os.path.dirname(os.path.dirname(__file__)), "officecli_bridge.py"))
    ocli = _ilu.module_from_spec(_spec)
    _spec.loader.exec_module(ocli)


def _desktop():
    home = os.path.expanduser("~")
    d = os.path.join(home, "Desktop")
    return d if os.path.isdir(d) else home


def esegui_crea_preventivo_word(dati):
    """
    Genera un preventivo Word professionale con tabella formattata.

    Prova OfficeCLI (tabelle colorate, font professionali).
    Fallback a python-docx se OfficeCLI non è installato.
    """
    if not dati:
        return "Impossibile generare il preventivo: dati mancanti."

    # Estrai dati
    mittente = dati.get("azienda_mittente", "N/D")
    ricevente = dati.get("azienda_ricevente", "N/D")
    valore = dati.get("valore", "0")
    iva = dati.get("iva", "22")

    # Calcolo totale
    try:
        valore_num = float(str(valore).replace("€", "").replace(",", ".").strip())
        iva_num = float(str(iva).replace("%", "").strip())
        imponibile = valore_num
        importo_iva = valore_num * (iva_num / 100)
        totale = imponibile + importo_iva
    except Exception:
        imponibile = 0
        importo_iva = 0
        totale = 0

    nome_file = f"Preventivo_{ricevente.replace(' ', '_').replace('/', '-')}.docx"
    percorso = os.path.join(_desktop(), nome_file)

    # Prepara le voci per il preventivo
    voci_tabella = dati.get("voci", None)
    if not voci_tabella:
        # Crea una voce singola dai dati base
        voci_tabella = [{
            "descrizione": dati.get("descrizione", "Commercializzazione prodotti"),
            "quantita": 1,
            "prezzo": imponibile,
            "totale": imponibile,
        }]

    # Prova OfficeCLI per output professionale
    if ocli.is_installed():
        dati_azienda = {
            "nome": mittente,
            "indirizzo": dati.get("indirizzo", ""),
            "piva": dati.get("piva", ""),
            "telefono": dati.get("telefono", ""),
            "email": dati.get("email", ""),
        }

        note_testo = dati.get("note", None)
        if not note_testo and iva_num > 0:
            note_testo = f"Imponibile: €{imponibile:.2f} | IVA {iva_num:.0f}%: €{importo_iva:.2f} | Totale: €{totale:.2f}"

        ok, msg = ocli.crea_preventivo_word(percorso, dati_azienda, voci_tabella, note=note_testo)
        if ok:
            # Apri il file
            try:
                import pc_index
                pc_index.apri_percorso(percorso)
            except Exception:
                pass
            return f"Preventivo professionale '{nome_file}' creato sul Desktop."
        else:
            print(f"[office_skills] OfficeCLI fallito: {msg}, provo python-docx")

    # ---- Fallback: python-docx ----
    return _crea_preventivo_docx(percorso, nome_file, mittente, ricevente,
                                  valore, iva, imponibile, importo_iva, totale,
                                  voci_tabella, dati)


def _crea_preventivo_docx(percorso, nome_file, mittente, ricevente,
                           valore, iva, imponibile, importo_iva, totale,
                           voci, dati):
    """Fallback: crea preventivo con python-docx (senza OfficeCLI)."""
    try:
        from docx import Document
        from docx.shared import Pt, Inches, RGBColor
        from docx.enum.text import WD_ALIGN_PARAGRAPH
    except ImportError:
        return ("Per creare documenti Word serve OfficeCLI oppure python-docx. "
                "Installa uno dei due: pip install python-docx")

    doc = Document()

    # Stile
    style = doc.styles['Normal']
    style.font.name = 'Calibri'
    style.font.size = Pt(11)

    # Intestazione
    h = doc.add_heading(mittente, level=1)

    info_parts = []
    if dati.get("indirizzo"):
        info_parts.append(dati["indirizzo"])
    if dati.get("piva"):
        info_parts.append(f"P.IVA: {dati['piva']}")
    if info_parts:
        p = doc.add_paragraph(" | ".join(info_parts))
        p.style.font.size = Pt(9)

    doc.add_paragraph("")
    doc.add_heading("PREVENTIVO", level=2)
    doc.add_paragraph(f"Spett.le: {ricevente}")
    doc.add_paragraph("")

    # Tabella
    n_voci = len(voci) if voci else 1
    table = doc.add_table(rows=n_voci + 2, cols=4)
    table.style = 'Light Grid Accent 1'

    # Header
    headers = ["Descrizione", "Qtà", "Prezzo Unit.", "Totale"]
    for i, h in enumerate(headers):
        cell = table.rows[0].cells[i]
        cell.text = h
        for p in cell.paragraphs:
            for run in p.runs:
                run.bold = True

    # Voci
    if voci:
        for idx, v in enumerate(voci):
            row = table.rows[idx + 1]
            row.cells[0].text = str(v.get("descrizione", ""))
            row.cells[1].text = str(v.get("quantita", ""))
            prezzo = v.get("prezzo", "")
            row.cells[2].text = f"€{prezzo}" if prezzo else ""
            tot_v = v.get("totale", "")
            row.cells[3].text = f"€{tot_v}" if tot_v else ""
    else:
        row = table.rows[1]
        row.cells[0].text = dati.get("descrizione", "Commercializzazione prodotti")
        row.cells[1].text = "1"
        row.cells[2].text = f"€{imponibile:.2f}"
        row.cells[3].text = f"€{imponibile:.2f}"

    # Riga totale
    last_row = table.rows[-1]
    last_row.cells[2].text = "TOTALE"
    last_row.cells[3].text = f"€{totale:.2f}"
    for p in last_row.cells[2].paragraphs:
        for run in p.runs:
            run.bold = True
    for p in last_row.cells[3].paragraphs:
        for run in p.runs:
            run.bold = True

    # Note IVA
    doc.add_paragraph("")
    doc.add_paragraph(
        f"Imponibile: €{imponibile:.2f} | IVA {iva}%: €{importo_iva:.2f} | Totale: €{totale:.2f}",
    )

    try:
        doc.save(percorso)
        # Apri il file
        try:
            import pc_index
            pc_index.apri_percorso(percorso)
        except Exception:
            pass
        return f"Preventivo '{nome_file}' creato sul Desktop."
    except Exception as e:
        return f"Errore salvataggio: {e}"


def esegui_crea_documento_word(dati):
    """
    Crea un documento Word generico.

    dati: dict con "titolo", "contenuto" (testo o lista di paragrafi)
    """
    if not dati:
        return "Dati mancanti per il documento."

    titolo = dati.get("titolo", "Documento")
    contenuto = dati.get("contenuto", "")
    nome_file = f"{titolo.replace(' ', '_').replace('/', '-')}.docx"
    percorso = os.path.join(_desktop(), nome_file)

    if ocli.is_installed():
        ok, out = ocli.crea_word(percorso)
        if ok:
            ocli.aggiungi_titolo(percorso, titolo, livello=1)

            if isinstance(contenuto, list):
                for p in contenuto:
                    ocli.aggiungi_paragrafo(percorso, str(p))
            elif contenuto:
                for p in str(contenuto).split("\n"):
                    if p.strip():
                        ocli.aggiungi_paragrafo(percorso, p.strip())

            ocli.salva(percorso)
            try:
                import pc_index
                pc_index.apri_percorso(percorso)
            except Exception:
                pass
            return f"Documento '{nome_file}' creato sul Desktop."

    # Fallback python-docx
    try:
        from docx import Document
        doc = Document()
        doc.add_heading(titolo, level=1)
        if isinstance(contenuto, list):
            for p in contenuto:
                doc.add_paragraph(str(p))
        elif contenuto:
            for p in str(contenuto).split("\n"):
                if p.strip():
                    doc.add_paragraph(p.strip())
        doc.save(percorso)
        try:
            import pc_index
            pc_index.apri_percorso(percorso)
        except Exception:
            pass
        return f"Documento '{nome_file}' creato sul Desktop."
    except ImportError:
        return "Serve OfficeCLI o python-docx per creare documenti Word."
    except Exception as e:
        return f"Errore: {e}"


def esegui_crea_foglio_excel(dati):
    """
    Crea un foglio Excel con dati tabulari.

    dati: dict con "titolo", "righe" (lista di liste)
    """
    if not dati or not dati.get("righe"):
        return "Dati mancanti per il foglio Excel."

    titolo = dati.get("titolo", "Foglio")
    righe = dati["righe"]
    nome_file = f"{titolo.replace(' ', '_').replace('/', '-')}.xlsx"
    percorso = os.path.join(_desktop(), nome_file)

    if ocli.is_installed():
        ok, out = ocli.crea_excel(percorso)
        if ok:
            ok2, out2 = ocli.compila_excel(percorso, "Sheet1", righe)
            ocli.salva(percorso)
            try:
                import pc_index
                pc_index.apri_percorso(percorso)
            except Exception:
                pass
            return f"Foglio Excel '{nome_file}' creato sul Desktop."

    return "Serve OfficeCLI per creare fogli Excel."
