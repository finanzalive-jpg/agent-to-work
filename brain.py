"""
brain.py - Cervello INTERCAMBIABILE di Agent-to-Work.

Un solo punto per "pensare": l'orchestratore chiama brain.interroga(...) e qui si decide
se usare il CLOUD (Groq / OpenAI-compatibile, veloce) o il LOCALE (Ollama, privato).
Cambi fornitore in config.json ("brain" -> "provider") senza toccare il resto del progetto:
  - provider = "groq"   -> veloce, cervello in cloud (serve chiave GROQ_API_KEY nel file .env)
  - provider = "ollama" -> tutto in locale (serve Ollama in esecuzione, nessuna chiave)

In entrambi i casi la risposta e' lo STESSO JSON vincolato dallo schema (intent classifier).
"""
import os
import json

# Carica le chiavi dal file .env (se presente) senza farle finire nel codice/git
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass


def _istruzioni_json(schema):
    """Trasforma lo schema in istruzioni testuali: serve ai modelli cloud (modalita' JSON)
    per restituire ESATTAMENTE la forma giusta, come fa Ollama con format=schema."""
    props = schema.get("properties", {})
    skill_enum = props.get("skill_identificata", {}).get("enum", [])
    flusso_enum = props.get("stato_flusso", {}).get("enum", [])
    righe = [
        "Rispondi SOLO con un oggetto JSON valido, senza testo prima o dopo, con questi campi ESATTI:",
        '- "wake_word_detected": true/false',
        '- "skill_identificata": uno tra -> ' + ", ".join(skill_enum),
        '- "stato_flusso": uno tra -> ' + ", ".join(flusso_enum),
        '- "parametri": oggetto con "target", "vecchio_nome", "nuovo_nome" (stringhe, vuote se non servono) '
        'e "dati_preventivo" (oggetto con "azienda_mittente", "azienda_ricevente", "valore", "iva")',
        '- "risposta_vocale": frase breve in italiano da dire all\'utente',
    ]
    return "\n".join(righe)


def _brain_ollama(system_prompt, testo_utente, schema, cfg):
    import ollama
    client = ollama.Client(host=cfg.get("ollama_host", "http://127.0.0.1:11434"))
    response = client.chat(
        model=cfg.get("ollama_model", "qwen2.5:3b-instruct-q4_K_M"),
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": testo_utente},
        ],
        format=schema,  # Ollama vincola l'output allo schema JSON
        options={"num_ctx": cfg.get("num_ctx", 2048), "temperature": cfg.get("temperature", 0.1)},
    )
    return json.loads(response.message.content)


def _brain_cloud(system_prompt, testo_utente, schema, cfg):
    """Groq / OpenAI e qualunque endpoint compatibile OpenAI."""
    from openai import OpenAI
    nome_var = cfg.get("api_key_env", "GROQ_API_KEY")
    api_key = os.getenv(nome_var)
    if not api_key:
        raise RuntimeError(
            "Chiave API mancante: crea un file '.env' con la riga  %s=la_tua_chiave  "
            "(vedi .env.example)." % nome_var
        )
    client = OpenAI(api_key=api_key, base_url=cfg.get("base_url", "https://api.groq.com/openai/v1"))
    sys_completo = system_prompt + "\n\n" + _istruzioni_json(schema)
    response = client.chat.completions.create(
        model=cfg.get("model", "openai/gpt-oss-20b"),
        messages=[
            {"role": "system", "content": sys_completo},
            {"role": "user", "content": testo_utente},
        ],
        temperature=cfg.get("temperature", 0.1),
        response_format={"type": "json_object"},  # garantisce JSON valido
    )
    return json.loads(response.choices[0].message.content)


def interroga(system_prompt, testo_utente, schema, brain_cfg):
    """Punto unico: restituisce il JSON dell'intento. Sceglie cloud o locale dalla config."""
    provider = (brain_cfg or {}).get("provider", "ollama").lower()
    try:
        if provider == "ollama":
            return _brain_ollama(system_prompt, testo_utente, schema, brain_cfg)
        else:
            return _brain_cloud(system_prompt, testo_utente, schema, brain_cfg)
    except Exception as e:
        return {"error": "Errore cervello (%s): %s" % (provider, e)}


# ----------------------------------------------------------------------
# CHIACCHIERA LIBERA: risposta in testo normale (niente JSON).
# Serve per i commenti liberi, es. "che ne pensi del titolo Apple" dove al
# modello passiamo i dati VERI e gli chiediamo di spiegarli a parole.
# ----------------------------------------------------------------------
def chat_libero(system_prompt, testo_utente, brain_cfg):
    provider = (brain_cfg or {}).get("provider", "ollama").lower()
    cfg = brain_cfg or {}
    try:
        if provider == "ollama":
            import ollama
            client = ollama.Client(host=cfg.get("ollama_host", "http://127.0.0.1:11434"))
            r = client.chat(
                model=cfg.get("ollama_model", "qwen2.5:3b-instruct-q4_K_M"),
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": testo_utente},
                ],
                options={"num_ctx": cfg.get("num_ctx", 2048), "temperature": cfg.get("temperature", 0.3)},
            )
            return r.message.content.strip()
        else:
            from openai import OpenAI
            nome_var = cfg.get("api_key_env", "GROQ_API_KEY")
            api_key = os.getenv(nome_var)
            if not api_key:
                raise RuntimeError("Chiave API mancante (vedi .env.example).")
            client = OpenAI(api_key=api_key, base_url=cfg.get("base_url", "https://api.groq.com/openai/v1"))
            r = client.chat.completions.create(
                model=cfg.get("model", "openai/gpt-oss-20b"),
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": testo_utente},
                ],
                temperature=cfg.get("temperature", 0.3),
            )
            return r.choices[0].message.content.strip()
    except Exception as e:
        return "Non riesco a commentare ora (%s)." % e
