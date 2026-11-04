"""
web_info.py - Web e informazioni: ricerca web, definizioni, riassunti, mappe.

- ricerca web generale (DuckDuckGo, gratis) + risposta sintetizzata dal cervello
- definizioni / 'chi è / cos'è' (Wikipedia in italiano, gratis)
- riassunto di una pagina da un link
- mappe e indicazioni (apre Google Maps)
"""
import os
import re
import sys
import json
import urllib.parse
import urllib.request

import brain

_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}


def _togli_tag(s):
    return re.sub(r"\s+", " ", re.sub(r"<.*?>", "", s or "")).strip()


# ---------------------------------------------------------------- RICERCA WEB
def _ddg(query, n=4):
    url = "https://html.duckduckgo.com/html/?q=" + urllib.parse.quote(query)
    req = urllib.request.Request(url, headers=_HEADERS)
    with urllib.request.urlopen(req, timeout=8) as r:
        html = r.read().decode("utf-8", "ignore")
    titoli = re.findall(r'class="result__a"[^>]*>(.*?)</a>', html, re.S)
    snippet = re.findall(r'class="result__snippet"[^>]*>(.*?)</a>', html, re.S)
    res = []
    for t, s in zip(titoli, snippet):
        testo = _togli_tag(t) + ": " + _togli_tag(s)
        if len(testo) > 5:
            res.append(testo)
        if len(res) >= n:
            break
    return res


def cerca_web(query, brain_cfg):
    q = re.sub(r"^\s*(cerca su internet|cerca sul web|cerca online|cerca|cercami|informazioni su|dimmi)\b[:,]?\s*",
               "", query or "", flags=re.I).strip() or query
    try:
        risultati = _ddg(q)
    except Exception as e:
        print(f"[web] ddg errore: {e}")
        risultati = []
    if risultati:
        contesto = "\n".join(risultati)
        sys_p = ("Rispondi in italiano, breve (2-3 frasi), usando SOLO queste informazioni dal web. "
                 "Testo semplice: niente asterischi, elenchi o link. "
                 "Se le informazioni non bastano a rispondere, di' esattamente: "
                 "Non ho trovato informazioni affidabili sul web.\nInformazioni:\n" + contesto)
        return brain.chat_libero(sys_p, q, brain_cfg)
    # Nessun risultato: NON inventare. Sii onesto.
    return ("Non sono riuscito a cercare sul web in questo momento. "
            "Controlla la connessione. Se ti servono prezzi o quotazioni, chiedimi di un titolo "
            "o di una criptovaluta e li prendo dai mercati reali.")


# ---------------------------------------------------------------- DEFINIZIONI (Wikipedia)
def definizione(termine, brain_cfg=None):
    t = re.sub(r"^\s*(chi è|chi e|cos'è|cos e|cosa è|cosa sono|che cos'è|definizione di|definisci|spiegami|parlami di)\b[:,]?\s*",
               "", termine or "", flags=re.I).strip(" ?.")
    if not t:
        return "Di cosa vuoi la definizione?"
    try:
        url = "https://it.wikipedia.org/api/rest_v1/page/summary/" + urllib.parse.quote(t.replace(" ", "_"))
        req = urllib.request.Request(url, headers=_HEADERS)
        with urllib.request.urlopen(req, timeout=7) as r:
            dati = json.loads(r.read().decode("utf-8"))
        estratto = dati.get("extract", "")
        if estratto:
            frasi = re.split(r"(?<=[.!?])\s+", estratto)
            return " ".join(frasi[:2]).strip()
    except Exception as e:
        print(f"[wiki] errore: {e}")
    # ripiego sul cervello
    if brain_cfg is not None:
        return brain.chat_libero("Spiega in italiano in 2 frasi semplici, senza inventare.", t, brain_cfg)
    return f"Non ho trovato una definizione di {t}."


# ---------------------------------------------------------------- RIASSUNTO PAGINA
def riassumi(testo, brain_cfg):
    m = re.search(r"https?://\S+", testo or "")
    if not m:
        return "Incollami il link della pagina da riassumere (nella casella di testo)."
    url = m.group(0)
    try:
        req = urllib.request.Request(url, headers=_HEADERS)
        with urllib.request.urlopen(req, timeout=10) as r:
            html = r.read().decode("utf-8", "ignore")
    except Exception as e:
        print(f"[riassumi] errore: {e}")
        return "Non riesco ad aprire quella pagina."
    # togli script/style e tag
    html = re.sub(r"(?is)<(script|style).*?</\1>", " ", html)
    testo_pulito = _togli_tag(html)[:6000]
    if not testo_pulito:
        return "La pagina non ha testo leggibile."
    return brain.chat_libero("Riassumi in italiano in 3-4 frasi, testo semplice, i punti principali di questo testo.",
                             testo_pulito, brain_cfg)


# ---------------------------------------------------------------- MAPPE
def _apri_url(url):
    try:
        if sys.platform.startswith("win"):
            os.startfile(url)
        elif sys.platform.startswith("darwin"):
            import subprocess
            subprocess.run(["open", url])
        else:
            import subprocess
            subprocess.run(["xdg-open", url])
        return True
    except Exception as e:
        print(f"[mappa] errore: {e}")
        return False


def mappa(testo):
    low = (testo or "").lower()
    indicazioni = any(k in low for k in ("come arrivo", "come si arriva", "indicazioni", "portami", "strada per", "come raggiungo"))
    dest = re.sub(r"^.*?(come arrivo a|come si arriva a|indicazioni per|portami a|strada per|come raggiungo|dov'è|dove si trova|trova sulla mappa|mappa di|mostrami)\b\s*",
                  "", low, flags=re.I).strip(" ?.")
    if not dest:
        dest = re.sub(r"(mappa|maps|indicazioni)", "", low).strip()
    if not dest:
        return "Dove vuoi andare?"
    enc = urllib.parse.quote(dest)
    if indicazioni:
        url = f"https://www.google.com/maps/dir/?api=1&destination={enc}"
        msg = f"Ti apro le indicazioni per {dest}."
    else:
        url = f"https://www.google.com/maps/search/?api=1&query={enc}"
        msg = f"Ti mostro {dest} sulla mappa."
    _apri_url(url)
    return msg
