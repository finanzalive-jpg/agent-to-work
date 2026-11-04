"""
officecli_bridge.py - Wrapper Python per OfficeCLI.

Permette di creare e modificare documenti Word, Excel e PowerPoint
senza bisogno di Microsoft Office installato.

Richiede: OfficeCLI installato e raggiungibile nel PATH.
Install: irm https://d.officecli.ai/install.ps1 | iex  (Windows PowerShell)
"""
import os
import subprocess
import json
import shutil


def _officecli_cmd():
    """Ritorna il percorso dell'eseguibile officecli."""
    path = shutil.which("officecli")
    if path:
        return path
    # Fallback: cerca nelle posizioni comuni Windows
    for p in [
        os.path.expanduser(r"~\.officecli\officecli.exe"),
        r"C:\Program Files\OfficeCLI\officecli.exe",
        os.path.expanduser(r"~\AppData\Local\Programs\OfficeCLI\officecli.exe"),
    ]:
        if os.path.isfile(p):
            return p
    return "officecli"  # sperando sia nel PATH


def _run(args, timeout=30):
    """Esegue un comando officecli e ritorna (success, output)."""
    cmd = [_officecli_cmd()] + args
    try:
        result = subprocess.run(
            cmd, capture_output=True, text=True, timeout=timeout
        )
        output = result.stdout.strip()
        if result.returncode != 0:
            err = result.stderr.strip() or output
            return False, f"Errore OfficeCLI: {err}"
        return True, output
    except FileNotFoundError:
        return False, "OfficeCLI non è installato. Installa con: irm https://d.officecli.ai/install.ps1 | iex"
    except subprocess.TimeoutExpired:
        return False, "Timeout: OfficeCLI ci mette troppo."
    except Exception as e:
        return False, f"Errore esecuzione: {e}"


def _run_json(args, timeout=30):
    """Esegue un comando officecli con --json e ritorna il dict parsed."""
    ok, out = _run(args + ["--json"], timeout)
    if not ok:
        return None, out
    try:
        return json.loads(out), None
    except json.JSONDecodeError:
        return None, f"Output non JSON: {out[:200]}"


def is_installed():
    """Controlla se OfficeCLI è installato."""
    ok, _ = _run(["--version"])
    return ok


# ================================================================
# WORD (.docx)
# ================================================================

def crea_word(percorso):
    """Crea un documento Word vuoto."""
    ok, out = _run(["create", percorso])
    return ok, out


def aggiungi_titolo(percorso, testo, livello=1):
    """Aggiunge un titolo (heading) al documento Word."""
    style = f"Heading{livello}"
    ok, out = _run([
        "add", percorso, "/body",
        "--type", "paragraph",
        "--prop", f"text={testo}",
        "--prop", f"style={style}",
    ])
    return ok, out


def aggiungi_paragrafo(percorso, testo, bold=False, size=None, color=None, align=None):
    """Aggiunge un paragrafo con formattazione opzionale."""
    args = [
        "add", percorso, "/body",
        "--type", "paragraph",
        "--prop", f"text={testo}",
    ]
    if bold:
        args += ["--prop", "bold=true"]
    if size:
        args += ["--prop", f"size={size}pt"]
    if color:
        args += ["--prop", f"color={color}"]
    if align:
        args += ["--prop", f"align={align}"]
    return _run(args)


def aggiungi_tabella(percorso, righe, colonne, posizione="/body"):
    """Crea una tabella vuota."""
    ok, out = _run([
        "add", percorso, posizione,
        "--type", "table",
        "--prop", f"rows={righe}",
        "--prop", f"cols={colonne}",
    ])
    return ok, out


def imposta_cella(percorso, tabella_idx, riga, colonna, testo,
                  bold=False, shd=None, color=None, align=None):
    """
    Imposta il contenuto di una cella della tabella.

    Args:
        percorso: path del file .docx
        tabella_idx: indice tabella (1-based)
        riga: indice riga (1-based)
        colonna: indice colonna (1-based)
        testo: contenuto della cella
        bold: grassetto
        shd: colore sfondo cella (hex senza #, es. "4472C4")
        color: colore testo (hex senza #)
        align: allineamento ("center", "right", "left")
    """
    path = f"/body/tbl[{tabella_idx}]/tr[{riga}]/tc[{colonna}]"
    args = [
        "set", percorso, path,
        "--prop", f"text={testo}",
    ]
    if bold:
        args += ["--prop", "bold=true"]
    if shd:
        args += ["--prop", f"shd={shd}"]
    if color:
        args += ["--prop", f"color={color}"]
    if align:
        args += ["--prop", f"align={align}"]
    return _run(args)


def compila_tabella(percorso, tabella_idx, dati, header_bg="4472C4", header_color="FFFFFF"):
    """
    Compila una tabella intera da una lista di liste.
    La prima riga viene trattata come header (sfondo colorato, grassetto).

    Args:
        percorso: path del file .docx
        tabella_idx: indice tabella (1-based)
        dati: lista di liste, es. [["Nome", "Prezzo"], ["Servizio A", "€100"]]
        header_bg: colore sfondo header (hex)
        header_color: colore testo header (hex)

    Returns:
        (success, messaggio)
    """
    errori = []
    for i, riga in enumerate(dati):
        for j, valore in enumerate(riga):
            if i == 0:
                # Header: grassetto, sfondo colorato
                ok, out = imposta_cella(
                    percorso, tabella_idx, i + 1, j + 1,
                    str(valore), bold=True, shd=header_bg, color=header_color
                )
            else:
                ok, out = imposta_cella(
                    percorso, tabella_idx, i + 1, j + 1,
                    str(valore)
                )
            if not ok:
                errori.append(f"Cella [{i+1},{j+1}]: {out}")

    if errori:
        return False, f"Tabella compilata con {len(errori)} errori: {'; '.join(errori[:3])}"
    return True, f"Tabella compilata: {len(dati)} righe x {len(dati[0]) if dati else 0} colonne."


def imposta_stile_doc(percorso, font="Calibri", size="11pt"):
    """Imposta font e dimensione predefiniti del documento."""
    return _run([
        "set", percorso, "/",
        "--prop", f"docDefaults.font={font}",
        "--prop", f"docDefaults.fontSize={size}",
    ])


def aggiungi_interruzione(percorso, tipo="page"):
    """Aggiunge un'interruzione (page, section, column)."""
    return _run([
        "add", percorso, "/body",
        "--type", "break",
        "--prop", f"type={tipo}",
    ])


def salva(percorso):
    """Salva e chiude il documento (flush)."""
    return _run(["close", percorso])


# ================================================================
# EXCEL (.xlsx)
# ================================================================

def crea_excel(percorso):
    """Crea un file Excel vuoto."""
    return _run(["create", percorso])


def imposta_cella_excel(percorso, foglio, cella, valore, bold=False, shd=None):
    """
    Imposta il valore di una cella Excel.

    Args:
        percorso: path del file .xlsx
        foglio: nome foglio (es. "Sheet1")
        cella: riferimento cella (es. "A1", "B2")
        valore: contenuto
        bold: grassetto
        shd: colore sfondo
    """
    path = f"/{foglio}/{cella}"
    args = ["set", percorso, path, "--prop", f"value={valore}"]
    if bold:
        args += ["--prop", "bold=true"]
    if shd:
        args += ["--prop", f"shd={shd}"]
    return _run(args)


def compila_excel(percorso, foglio, dati, header_bold=True):
    """
    Compila un foglio Excel da una lista di liste.

    Args:
        percorso: path del file .xlsx
        foglio: nome foglio
        dati: lista di liste (la prima riga = header)
        header_bold: grassetto per la prima riga
    """
    errori = []
    for i, riga in enumerate(dati):
        for j, valore in enumerate(riga):
            col_letter = _col_letter(j)
            cella = f"{col_letter}{i + 1}"
            bold = header_bold and i == 0
            ok, out = imposta_cella_excel(percorso, foglio, cella, str(valore), bold=bold)
            if not ok:
                errori.append(f"{cella}: {out}")

    if errori:
        return False, f"Excel compilato con {len(errori)} errori: {'; '.join(errori[:3])}"
    return True, f"Foglio compilato: {len(dati)} righe."


def _col_letter(idx):
    """Converte indice colonna (0-based) in lettera Excel (A, B, ..., Z, AA, AB, ...)."""
    result = ""
    while True:
        result = chr(65 + idx % 26) + result
        idx = idx // 26 - 1
        if idx < 0:
            break
    return result


# ================================================================
# POWERPOINT (.pptx)
# ================================================================

def crea_pptx(percorso):
    """Crea una presentazione PowerPoint vuota."""
    return _run(["create", percorso])


def aggiungi_slide(percorso, titolo=None, sfondo=None):
    """Aggiunge una slide alla presentazione."""
    args = ["add", percorso, "/", "--type", "slide"]
    if titolo:
        args += ["--prop", f"title={titolo}"]
    if sfondo:
        args += ["--prop", f"background={sfondo}"]
    return _run(args)


def aggiungi_shape(percorso, slide_idx, testo, x="2cm", y="5cm",
                   font="Arial", size=24, color="000000", bold=False):
    """Aggiunge un testo (shape) a una slide."""
    args = [
        "add", percorso, f"/slide[{slide_idx}]",
        "--type", "shape",
        "--prop", f"text={testo}",
        "--prop", f"x={x}",
        "--prop", f"y={y}",
        "--prop", f"font={font}",
        "--prop", f"size={size}",
        "--prop", f"color={color}",
    ]
    if bold:
        args += ["--prop", "bold=true"]
    return _run(args)


# ================================================================
# FUNZIONI HELPER PER DOCUMENTI SPECIFICI
# ================================================================

def crea_preventivo_word(percorso, dati_azienda, voci, note=None):
    """
    Crea un preventivo Word professionale con tabella formattata.

    Args:
        percorso: path file .docx da creare
        dati_azienda: dict con "nome", "indirizzo", "piva", "telefono", "email"
        voci: lista di dict [{"descrizione": ..., "quantita": ..., "prezzo": ..., "totale": ...}, ...]
        note: testo note opzionale

    Returns:
        (success, messaggio)
    """
    # Crea documento
    ok, out = crea_word(percorso)
    if not ok:
        return False, out

    # Font di base
    imposta_stile_doc(percorso, font="Calibri", size="11pt")

    # Intestazione azienda
    aggiungi_titolo(percorso, dati_azienda.get("nome", "Azienda"), livello=1)

    info_parts = []
    if dati_azienda.get("indirizzo"):
        info_parts.append(dati_azienda["indirizzo"])
    if dati_azienda.get("piva"):
        info_parts.append(f"P.IVA: {dati_azienda['piva']}")
    if dati_azienda.get("telefono"):
        info_parts.append(f"Tel: {dati_azienda['telefono']}")
    if dati_azienda.get("email"):
        info_parts.append(f"Email: {dati_azienda['email']}")
    if info_parts:
        aggiungi_paragrafo(percorso, " | ".join(info_parts), size=9, color="666666")

    # Spazio
    aggiungi_paragrafo(percorso, "")

    # Titolo preventivo
    aggiungi_titolo(percorso, "PREVENTIVO", livello=2)

    # Tabella voci
    n_righe = len(voci) + 2  # +1 header, +1 totale
    n_col = 4  # Descrizione, Qtà, Prezzo Unit., Totale
    aggiungi_tabella(percorso, n_righe, n_col)

    # Header tabella
    headers = ["Descrizione", "Quantità", "Prezzo Unit.", "Totale"]
    header_data = [headers]

    # Righe voci
    totale_generale = 0
    for v in voci:
        tot = v.get("totale", 0)
        if not tot and v.get("quantita") and v.get("prezzo"):
            try:
                tot = float(v["quantita"]) * float(v["prezzo"])
            except (ValueError, TypeError):
                tot = 0
        totale_generale += float(tot) if tot else 0
        header_data.append([
            v.get("descrizione", ""),
            str(v.get("quantita", "")),
            f"€{v.get('prezzo', '')}" if v.get("prezzo") else "",
            f"€{tot:.2f}" if tot else "",
        ])

    # Riga totale
    header_data.append(["", "", "TOTALE", f"€{totale_generale:.2f}"])

    # Compila tabella
    ok, out = compila_tabella(percorso, 1, header_data)
    if not ok:
        print(f"[officecli_bridge] Warning: {out}")

    # Riga totale in grassetto
    imposta_cella(percorso, 1, n_righe, 3, "TOTALE", bold=True, align="right")
    imposta_cella(percorso, 1, n_righe, 4, f"€{totale_generale:.2f}", bold=True)

    # Note
    if note:
        aggiungi_paragrafo(percorso, "")
        aggiungi_titolo(percorso, "Note", livello=3)
        aggiungi_paragrafo(percorso, note)

    # Salva
    salva(percorso)
    return True, f"Preventivo creato: {percorso} (totale €{totale_generale:.2f})"
