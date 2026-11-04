"""
calcoli.py - Calcoli business: IVA, cambio valuta, percentuali, aritmetica.

Tutto DETERMINISTICO (nessuna fantasia dell'IA):
- IVA: aggiungi o scorpora ("1250 più IVA", "scorpora l'IVA da 1220")
- Cambio valuta reale (frankfurter.app, gratis, senza chiave)
- Percentuali ("il 15% di 2000", "2000 meno il 10%")
- Aritmetica a voce ("1250 per 3", "1000 più 250")
"""
import re
import ast
import json
import operator
import urllib.parse
import urllib.request

_HEADERS = {"User-Agent": "Mozilla/5.0"}

# Nomi valuta -> codice ISO
VALUTE = {
    "euro": "EUR", "eur": "EUR",
    "dollari": "USD", "dollaro": "USD", "dollari americani": "USD", "usd": "USD",
    "sterline": "GBP", "sterlina": "GBP", "gbp": "GBP",
    "yen": "JPY", "franchi": "CHF", "franco svizzero": "CHF", "chf": "CHF",
    "dollari canadesi": "CAD", "dollari australiani": "AUD",
    "yuan": "CNY", "renminbi": "CNY", "rubli": "RUB", "real": "BRL",
    "corone": "SEK", "zloty": "PLN", "bitcoin": "BTC",
}


# ---------------------------------------------------------------- NUMERI
def _numeri(testo):
    """Estrae i numeri (gestisce 1.250,50 all'italiana e 1250.50)."""
    out = []
    for tok in re.findall(r"\d[\d\.\,]*", testo or ""):
        t = tok
        if "." in t and "," in t:       # 1.250,50 -> 1250.50
            t = t.replace(".", "").replace(",", ".")
        elif "," in t:                   # 1250,50 -> 1250.50
            t = t.replace(",", ".")
        elif t.count(".") == 1 and len(t.split(".")[1]) == 3:
            t = t.replace(".", "")       # 1.250 (migliaia) -> 1250
        try:
            out.append(float(t))
        except Exception:
            pass
    return out


def _fmt(n):
    """Numero in formato italiano: 1.234,56 (toglie ,00 se intero)."""
    if abs(n - round(n)) < 1e-9:
        n = int(round(n))
        s = f"{n:,}".replace(",", ".")
    else:
        s = f"{n:,.2f}".replace(",", "§").replace(".", ",").replace("§", ".")
    return s


# ---------------------------------------------------------------- IVA
def _aliquota(testo, default=22.0):
    m = re.search(r"(?:iva|aliquota)\s*(?:al|del|di)?\s*(\d{1,2})\s*%?", testo, re.I)
    if m:
        return float(m.group(1))
    m = re.search(r"(\d{1,2})\s*%", testo)
    return float(m.group(1)) if m else default


def iva(testo):
    nums = _numeri(testo)
    if not nums:
        return "Dimmi l'importo, ad esempio: 1250 più IVA."
    imp = nums[0]
    ali = _aliquota(testo)
    low = testo.lower()
    if any(k in low for k in ("scorpor", "tolgo", "senza iva", "scorporare", "al netto")):
        imponibile = imp / (1 + ali / 100)
        iva_val = imp - imponibile
        return (f"Da {_fmt(imp)} euro IVA inclusa al {int(ali)} per cento: "
                f"imponibile {_fmt(imponibile)} euro, IVA {_fmt(iva_val)} euro.")
    else:
        iva_val = imp * ali / 100
        tot = imp + iva_val
        return (f"{_fmt(imp)} euro più IVA al {int(ali)} per cento fa {_fmt(tot)} euro "
                f"(IVA {_fmt(iva_val)} euro).")


# ---------------------------------------------------------------- PERCENTUALI
def percentuale(testo):
    low = testo.lower()
    # "X% di Y"
    m = re.search(r"(\d+[\.,]?\d*)\s*(?:per\s*cento|%|percento)\s*di\s*(\d[\d\.\,]*)", low)
    if m:
        p = _numeri(m.group(1))[0]
        base = _numeri(m.group(2))[0]
        return f"Il {_fmt(p)} per cento di {_fmt(base)} è {_fmt(base * p / 100)}."
    # "Y più/meno X%"
    m = re.search(r"(\d[\d\.\,]*)\s*(più|piu|meno)\s*(?:il\s*)?(\d+[\.,]?\d*)\s*(?:per\s*cento|%|percento)", low)
    if m:
        base = _numeri(m.group(1))[0]
        p = _numeri(m.group(3))[0]
        if m.group(2).startswith("men"):
            return f"{_fmt(base)} meno il {_fmt(p)} per cento fa {_fmt(base * (1 - p / 100))}."
        return f"{_fmt(base)} più il {_fmt(p)} per cento fa {_fmt(base * (1 + p / 100))}."
    return None


# ---------------------------------------------------------------- ARITMETICA
_OPS = {ast.Add: operator.add, ast.Sub: operator.sub, ast.Mult: operator.mul,
        ast.Div: operator.truediv, ast.USub: operator.neg, ast.Pow: operator.pow}


def _safe_eval(expr):
    def ev(n):
        if isinstance(n, ast.Constant) and isinstance(n.value, (int, float)):
            return n.value
        if isinstance(n, ast.BinOp):
            return _OPS[type(n.op)](ev(n.left), ev(n.right))
        if isinstance(n, ast.UnaryOp):
            return _OPS[type(n.op)](ev(n.operand))
        raise ValueError("espressione non valida")
    return ev(ast.parse(expr, mode="eval").body)


def aritmetica(testo):
    low = " " + testo.lower() + " "
    for a, b in ((" moltiplicato per ", "*"), (" diviso per ", "/"), (" più ", "+"),
                 (" piu ", "+"), (" meno ", "-"), (" per ", "*"), (" diviso ", "/"),
                 (" x ", "*")):
        low = low.replace(a, b)
    low = low.replace(",", ".")
    # tieni solo numeri e operatori
    expr = re.sub(r"[^0-9\.\+\-\*\/\(\) ]", "", low).strip()
    if not re.search(r"[\+\-\*\/]", expr):
        return None
    try:
        ris = _safe_eval(expr)
        return f"Fa {_fmt(ris)}."
    except Exception:
        return None


# ---------------------------------------------------------------- CAMBIO VALUTA
def _valute_ordinate(testo):
    """Valute trovate, in ORDINE di posizione nel testo. Torna [(pos, code)...]."""
    low = list(testo.lower())
    trovate = []
    visti = set()
    for nome, code in sorted(VALUTE.items(), key=lambda x: -len(x[0])):
        s = "".join(low)
        for m in re.finditer(r"\b" + re.escape(nome) + r"\b", s):
            if code not in visti:
                trovate.append((m.start(), code))
                visti.add(code)
            # "cancella" l'occorrenza così nomi più corti non rimatchano (es. dollari dentro dollari canadesi)
            for i in range(m.start(), m.end()):
                low[i] = " "
    trovate.sort()
    return trovate


def _trova_valute(testo):
    return _valute_ordinate(testo)


def cambio(testo):
    nums = _numeri(testo)
    valute = _valute_ordinate(testo)
    if not nums or len(valute) < 2:
        return "Dimmi importo e valute, ad esempio: quanti dollari sono 1000 euro."
    importo = nums[0]
    # posizione del numero: la valuta che viene SUBITO DOPO è quella di partenza (da)
    mnum = re.search(r"\d", testo)
    pos_num = mnum.start() if mnum else 0
    dopo = [(p, c) for p, c in valute if p >= pos_num]
    prima = [(p, c) for p, c in valute if p < pos_num]
    if dopo:
        da = dopo[0][1]
        a = next((c for p, c in valute if c != da), valute[-1][1])
    else:
        da = valute[-1][1]
        a = valute[0][1]
    try:
        url = f"https://api.frankfurter.app/latest?amount={importo}&from={da}&to={a}"
        req = urllib.request.Request(url, headers=_HEADERS)
        with urllib.request.urlopen(req, timeout=6) as r:
            dati = json.loads(r.read().decode("utf-8"))
        val = dati["rates"][a]
        return f"{_fmt(importo)} {da} fanno {_fmt(val)} {a}."
    except Exception as e:
        print(f"[cambio] errore: {e}")
        return "Non riesco a leggere il cambio in questo momento."


# ---------------------------------------------------------------- INGRESSO UNICO
def risolvi(testo):
    low = (testo or "").lower()
    if "iva" in low:
        return iva(testo)
    if _trova_valute(testo) and len(_trova_valute(testo)) >= 2:
        return cambio(testo)
    if "%" in low or "percento" in low or "per cento" in low:
        p = percentuale(testo)
        if p:
            return p
    a = aritmetica(testo)
    if a:
        return a
    return "Non ho capito il calcolo. Prova ad esempio: 1250 più IVA, oppure il 15 per cento di 2000."
