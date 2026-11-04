"""
navigazione.py - Navigazione web autonoma con Browser Use + Groq.

Atlas puo' aprire un browser vero e navigare siti, compilare form, estrarre dati
e interagire con pagine web come farebbe un umano. Usa il modello Groq come "cervello"
per decidere dove cliccare, cosa scrivere e come interpretare le pagine.

Requisiti:
  pip install browser-use langchain-groq playwright
  playwright install chromium

Uso:
  risultato = naviga_web("vai su amazon e cerca le cuffie bluetooth sotto 50 euro")
  risultato = cerca_in_pagina("https://example.com", "trova il prezzo del prodotto principale")
  risultato = compila_form("https://example.com/contatti", "compila il form con nome Mario Rossi, email mario@test.it")
"""
import os
import asyncio
import json

# Carica .env per GROQ_API_KEY
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass


def _get_llm(brain_cfg=None):
    """Crea l'istanza LLM per browser-use, usando il ChatGroq INTERNO di browser-use.

    browser-use ha le sue classi LLM in browser_use.llm che gestiscono
    automaticamente provider, attributi extra e formato risposte.
    Usare langchain_groq o langchain_openai direttamente non funziona
    perche' mancano gli adattamenti interni.
    """
    # Importa ChatGroq da browser-use, NON da langchain_groq!
    try:
        from browser_use.llm import ChatGroq
    except ImportError:
        try:
            # Fallback: versioni precedenti di browser-use
            from langchain_groq import ChatGroq
        except ImportError:
            raise ImportError(
                "Installa browser-use: pip install browser-use"
            )

    api_key = os.getenv("GROQ_API_KEY", "")
    if not api_key:
        raise ValueError("GROQ_API_KEY non trovata nel file .env")

    # openai/gpt-oss-20b: supporta tools + structured_outputs,
    # e ha limiti TPM piu' alti sul piano gratuito Groq rispetto al 120b
    modello = "openai/gpt-oss-20b"
    if brain_cfg:
        modello = brain_cfg.get("browser_model", modello)

    return ChatGroq(
        model=modello,
        api_key=api_key,
        temperature=0.0,
    )


def _get_agent(compito, brain_cfg=None, url_partenza=None):
    """Crea un agente browser-use configurato."""
    try:
        from browser_use import Agent, Browser
        # v0.11+ usa BrowserProfile, versioni precedenti BrowserConfig
        try:
            from browser_use import BrowserProfile as BrowserConfig
        except ImportError:
            from browser_use import BrowserConfig
    except ImportError:
        raise ImportError(
            "Installa browser-use: pip install browser-use && playwright install chromium"
        )

    llm = _get_llm(brain_cfg)

    # Configurazione browser
    browser_config = BrowserConfig(
        headless=False,  # Visibile: l'utente vede cosa sta facendo Atlas
        disable_security=False,
    )

    # Istruzioni sistema in italiano
    system_prompt = (
        "Sei Atlas, un assistente AI italiano che naviga il web per conto dell'utente. "
        "Naviga in modo efficiente, clicca sui link giusti, compila form se richiesto. "
        "Rispondi SEMPRE in italiano. Quando hai trovato l'informazione richiesta, "
        "riportala in modo chiaro e conciso."
    )

    # v0.11+: Browser non accetta più config=, si passa browser_profile all'Agent
    try:
        agent = Agent(
            task=compito,
            llm=llm,
            browser_profile=browser_config,
        )
    except TypeError:
        # Fallback per versioni precedenti
        try:
            agent = Agent(
                task=compito,
                llm=llm,
                browser=Browser(config=browser_config),
            )
        except TypeError:
            agent = Agent(
                task=compito,
                llm=llm,
            )

    return agent


async def _esegui_navigazione(compito, brain_cfg=None):
    """Esegue la navigazione in modo asincrono e restituisce il risultato."""
    try:
        agent = _get_agent(compito, brain_cfg)
        risultato = await agent.run()

        # Estrai il testo finale dal risultato
        if risultato:
            # browser-use restituisce un AgentHistory; prendiamo l'ultimo messaggio
            if hasattr(risultato, 'final_result') and risultato.final_result:
                return str(risultato.final_result())
            elif hasattr(risultato, 'history') and risultato.history:
                ultimo = risultato.history[-1]
                if hasattr(ultimo, 'result') and ultimo.result:
                    for r in ultimo.result:
                        if hasattr(r, 'extracted_content') and r.extracted_content:
                            return str(r.extracted_content)
            return str(risultato)
        return "Navigazione completata, ma non ho trovato risultati specifici."

    except ImportError as e:
        return f"Errore: modulo mancante - {e}. Esegui: pip install browser-use langchain-groq && playwright install chromium"
    except Exception as e:
        return f"Errore durante la navigazione: {e}"


def naviga_web(compito, brain_cfg=None):
    """
    Navigazione web autonoma. Atlas apre un browser e esegue il compito.

    Args:
        compito: descrizione in linguaggio naturale di cosa fare
                 es. "vai su amazon.it e cerca cuffie bluetooth sotto 30 euro"
        brain_cfg: configurazione del cervello (opzionale)

    Returns:
        str: risultato della navigazione in testo
    """
    print(f"[BROWSER] Avvio navigazione: {compito}")
    try:
        # Crea un nuovo event loop se non ce n'e' uno attivo
        try:
            loop = asyncio.get_running_loop()
            # Se siamo gia' in un loop asincrono, usiamo run_coroutine_threadsafe
            import concurrent.futures
            future = asyncio.run_coroutine_threadsafe(
                _esegui_navigazione(compito, brain_cfg), loop
            )
            return future.result(timeout=120)
        except RuntimeError:
            # Nessun loop attivo: ne creiamo uno
            return asyncio.run(_esegui_navigazione(compito, brain_cfg))
    except Exception as e:
        return f"Errore nella navigazione web: {e}"


def cerca_in_pagina(url, cosa_cercare, brain_cfg=None):
    """
    Apre una pagina specifica e cerca informazioni.

    Args:
        url: indirizzo della pagina da aprire
        cosa_cercare: cosa estrarre dalla pagina
        brain_cfg: configurazione del cervello (opzionale)

    Returns:
        str: informazione trovata
    """
    compito = f"Vai su {url} e {cosa_cercare}"
    return naviga_web(compito, brain_cfg)


def compila_form(url, istruzioni, brain_cfg=None):
    """
    Apre una pagina e compila un form seguendo le istruzioni.

    Args:
        url: indirizzo della pagina col form
        istruzioni: cosa compilare e come
        brain_cfg: configurazione del cervello (opzionale)

    Returns:
        str: esito della compilazione
    """
    compito = f"Vai su {url} e {istruzioni}. Non inviare il form, aspetta conferma."
    return naviga_web(compito, brain_cfg)


def interagisci_pagina(url, azione, brain_cfg=None):
    """
    Interazione generica con una pagina web.

    Args:
        url: indirizzo della pagina
        azione: cosa fare sulla pagina
        brain_cfg: configurazione del cervello (opzionale)

    Returns:
        str: risultato dell'azione
    """
    compito = f"Vai su {url} e {azione}"
    return naviga_web(compito, brain_cfg)


# --- Test rapido ---
if __name__ == "__main__":
    print("=== Test Navigazione Atlas ===")
    print("Scrivi un compito di navigazione (es. 'cerca su google il meteo di Roma')")
    print("Scrivi 'esci' per uscire.\n")

    while True:
        compito = input("Compito: ").strip()
        if compito.lower() == "esci":
            break
        if not compito:
            continue
        risultato = naviga_web(compito)
        print(f"\n[RISULTATO]: {risultato}\n")
