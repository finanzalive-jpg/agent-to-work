"""
web_tools.py - Informazioni dal web su richiesta.

Per ora: analisi di un TITOLO di borsa ("che ne pensi di Apple?").
Prende i dati VERI da Yahoo Finance e li fa commentare al cervello (brain.chat_libero),
cosi' il commento si basa su numeri reali, non inventati.

NB: non e' consulenza finanziaria. Il commento resta descrittivo.
"""
import json
import urllib.parse
import urllib.request

import brain

_HEADERS = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}

# Nomi comuni -> ticker Yahoo (puoi aggiungerne quanti vuoi)
_TICKER = {
    "apple": "AAPL", "tesla": "TSLA", "microsoft": "MSFT", "amazon": "AMZN",
    "google": "GOOGL", "alphabet": "GOOGL", "nvidia": "NVDA", "meta": "META",
    "facebook": "META", "netflix": "NFLX", "intel": "INTC", "amd": "AMD",
    "eni": "ENI.MI", "enel": "ENEL.MI", "intesa": "ISP.MI", "unicredit": "UCG.MI",
    "stellantis": "STLAM.MI", "ferrari": "RACE.MI", "leonardo": "LDO.MI",
    "generali": "G.MI", "poste": "PST.MI", "bitcoin": "BTC-USD", "ethereum": "ETH-USD",
}


def ticker_noto(nome):
    """Solo match sul dizionario (azioni/cripto conosciute), senza il ripiego generico."""
    if not nome:
        return None
    chiave = nome.strip().lower()
    for k, v in _TICKER.items():
        if k in chiave:
            return v
    return None


def _trova_ticker(nome):
    if not nome:
        return None
    chiave = nome.strip().lower()
    # match diretto sul dizionario
    for k, v in _TICKER.items():
        if k in chiave:
            return v
    # se l'utente ha scritto gia' un ticker (es. "AAPL"), usalo
    pulito = chiave.upper().replace(" ", "")
    if 1 <= len(pulito) <= 12 and pulito.replace(".", "").replace("-", "").isalnum():
        return pulito
    return None


def _dati_titolo(ticker):
    """Dati reali da Yahoo: prezzo, variazione %, massimi/minimi, valuta."""
    url = "https://query1.finance.yahoo.com/v8/finance/chart/%s" % urllib.parse.quote(ticker)
    req = urllib.request.Request(url, headers=_HEADERS)
    with urllib.request.urlopen(req, timeout=6) as resp:
        meta = json.loads(resp.read().decode("utf-8"))["chart"]["result"][0]["meta"]
    prezzo = meta.get("regularMarketPrice")
    prec = meta.get("chartPreviousClose") or meta.get("previousClose")
    pct = None
    if prezzo is not None and prec:
        pct = (prezzo - prec) / prec * 100.0
    return {
        "ticker": ticker,
        "valuta": meta.get("currency", ""),
        "prezzo": prezzo,
        "variazione_pct": pct,
        "max_52w": meta.get("fiftyTwoWeekHigh"),
        "min_52w": meta.get("fiftyTwoWeekLow"),
    }


def analizza_titolo(nome, brain_cfg):
    """Restituisce (testo_da_dire, testo_dettagli). Il commento si basa sui dati veri."""
    ticker = _trova_ticker(nome)
    if not ticker:
        return ("Non ho capito di quale titolo parli. Prova con un nome o un simbolo di borsa.", "")

    try:
        d = _dati_titolo(ticker)
    except Exception as e:
        return ("Non riesco a leggere i dati di %s adesso." % ticker, "Errore: %s" % e)

    if d["prezzo"] is None:
        return ("Non ho trovato quotazioni per %s." % ticker, "")

    segno = ""
    if d["variazione_pct"] is not None:
        segno = "+" if d["variazione_pct"] >= 0 else ""

    riassunto_dati = (
        "Titolo %s. Prezzo attuale %.2f %s. "
        "Variazione di oggi %s%.2f%%. "
        "Massimo 52 settimane %.2f, minimo 52 settimane %.2f."
        % (
            d["ticker"], d["prezzo"], d["valuta"],
            segno, (d["variazione_pct"] or 0.0),
            d["max_52w"] or 0.0, d["min_52w"] or 0.0,
        )
    )

    system = (
        "Sei un assistente che spiega i dati di borsa in italiano, in modo semplice e in massimo 2 frasi. "
        "Descrivi la situazione basandoti SOLO sui dati forniti. "
        "Scrivi in TESTO SEMPLICE: niente asterischi, niente grassetto, niente parentesi, niente elenchi. "
        "NON dare consigli di acquisto o vendita e non fare previsioni: non sei un consulente finanziario. "
        "NON aggiungere avvertenze o disclaimer: ci pensa il programma."
    )
    commento = brain.chat_libero(system, "Dati: " + riassunto_dati, brain_cfg)
    return (commento, riassunto_dati)
