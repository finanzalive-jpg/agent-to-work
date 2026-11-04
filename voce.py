"""
voce.py - Orecchie e Bocca dell'assistente.

- ASCOLTO (STT): registra dal microfono e trascrive con Whisper su Groq.
- VOCE (TTS): fa parlare l'assistente in italiano con Edge-TTS (gratis, voce naturale).

Entrambi sono GRATIS. Whisper usa la stessa chiave Groq del cervello.
Edge-TTS non richiede nessuna chiave.

Modalita' PUSH-TO-TALK: premi INVIO, parli, premi di nuovo INVIO per inviare.
"""
import os
import tempfile
import threading
import wave

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

SAMPLERATE = 16000  # Whisper lavora bene a 16 kHz


# ----------------------------------------------------------------------
# ASCOLTO (microfono -> testo)
# ----------------------------------------------------------------------
def registra_push_to_talk():
    """Registra dal microfono tra due INVIO. Restituisce il percorso di un file .wav."""
    import sounddevice as sd
    import numpy as np

    frames = []

    def callback(indata, n, t, status):
        frames.append(indata.copy())

    input("🎤 Premi INVIO e parla...")
    stream = sd.InputStream(samplerate=SAMPLERATE, channels=1, dtype="int16", callback=callback)
    with stream:
        input("🔴 Sto registrando... premi INVIO per fermare.")

    if not frames:
        return None

    audio = np.concatenate(frames, axis=0)
    percorso = tempfile.mktemp(suffix=".wav")
    with wave.open(percorso, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)  # int16 = 2 byte
        wf.setframerate(SAMPLERATE)
        wf.writeframes(audio.tobytes())
    return percorso


def trascrivi(percorso_wav, cfg=None, lingua="it"):
    """Manda l'audio a Whisper (Groq) e torna il testo."""
    cfg = cfg or {}
    from openai import OpenAI
    api_key = os.getenv(cfg.get("api_key_env", "GROQ_API_KEY"))
    client = OpenAI(api_key=api_key, base_url=cfg.get("base_url", "https://api.groq.com/openai/v1"))
    # Parole-guida: aiutano Whisper a riconoscere i termini che usiamo spesso
    guida = ("desktop, cartella, rinomina, crea, preventivo, mercati, borsa, "
             "titolo, azione, Apple, Microsoft, Tesla, bitcoin, notiziario, buongiorno")
    with open(percorso_wav, "rb") as f:
        r = client.audio.transcriptions.create(
            model=cfg.get("stt_model", "whisper-large-v3-turbo"),
            file=f,
            language=lingua,
            prompt=guida,
            temperature=0.0,   # niente "fantasia": meno parole inventate
        )
    return (r.text or "").strip()


def ascolta(cfg=None):
    """Push-to-talk completo: registra e restituisce il testo trascritto (o '')."""
    percorso = registra_push_to_talk()
    if not percorso:
        return ""
    try:
        testo = trascrivi(percorso, cfg)
    finally:
        try:
            os.remove(percorso)
        except Exception:
            pass
    return testo


# ----------------------------------------------------------------------
# VOCE (testo -> audio parlato)
# ----------------------------------------------------------------------
VOCE_DEFAULT = "it-IT-DiegoNeural"   # alternativa femminile: it-IT-ElsaNeural


def _pulisci_per_voce(testo):
    """Toglie i simboli che la voce leggerebbe ad alta voce (asterischi, cancelletti,
    trattini di elenco, e il contenuto tra parentesi tipo i disclaimer)."""
    import re
    if not testo:
        return ""
    t = testo
    t = re.sub(r"\([^)]*\)", "", t)   # via tutto quello tra parentesi tonde
    t = t.replace("*", "").replace("#", "").replace("`", "").replace("_", " ")
    t = re.sub(r"^\s*[-•]\s*", "", t, flags=re.MULTILINE)  # trattini di elenco a inizio riga
    t = re.sub(r"[ \t]+", " ", t)
    t = re.sub(r"\n{2,}", "\n", t)
    return t.strip()


def parla(testo, voce=None, interrompi=None):
    """Sintetizza 'testo' con Edge-TTS (gratis) e lo riproduce.
    interrompi: funzione che, se restituisce True, ferma subito la voce (barge-in)."""
    testo = _pulisci_per_voce(testo)
    if not testo:
        return
    import asyncio
    import edge_tts

    voce = voce or VOCE_DEFAULT
    percorso = tempfile.mktemp(suffix=".mp3")

    async def _genera():
        com = edge_tts.Communicate(testo, voce)
        await com.save(percorso)

    try:
        asyncio.run(_genera())
        _riproduci(percorso, interrompi)
    except Exception as e:
        print("[voce] Impossibile parlare: %s" % e)
    finally:
        try:
            os.remove(percorso)
        except Exception:
            pass


def _riproduci(percorso_mp3, interrompi=None):
    """Riproduce un mp3. Se possibile in modo INTERROMPIBILE (pulsante Stop / barge-in)."""
    # 1) Metodo interrompibile: decodifica con soundfile e riproduci con sounddevice
    #    (pacchetti pronti su Windows, nessun compilatore richiesto)
    try:
        import time
        import soundfile as sf
        import sounddevice as sd

        data, sr = sf.read(percorso_mp3, dtype="float32")
        durata = len(data) / float(sr) if sr else 0
        scadenza = time.time() + durata + 1.0   # tetto: non resta mai appeso
        sd.play(data, sr)
        while time.time() < scadenza:
            if interrompi and interrompi():
                break
            try:
                st = sd.get_stream()
                if st is None or not st.active:
                    break
            except Exception:
                break
            time.sleep(0.05)
        sd.stop()   # garantisce lo stop in ogni caso
        return
    except Exception:
        pass
    # 2) Fallback non interrompibile: playsound
    try:
        from playsound import playsound
        playsound(percorso_mp3)
        return
    except Exception:
        pass
    # 3) Ultima spiaggia: lettore di sistema
    try:
        import sys
        if sys.platform.startswith("win"):
            os.startfile(percorso_mp3)
        elif sys.platform.startswith("darwin"):
            import subprocess
            subprocess.run(["afplay", percorso_mp3])
        else:
            import subprocess
            subprocess.run(["xdg-open", percorso_mp3])
    except Exception as e:
        print("[voce] Nessun lettore audio disponibile: %s" % e)


if __name__ == "__main__":
    # Piccolo test manuale del modulo voce
    print("Test VOCE: ora dovrei parlare.")
    parla("Ciao, sono il tuo assistente. La voce funziona correttamente.")
    print("Test ASCOLTO: parla dopo aver premuto INVIO.")
    cfg = {"api_key_env": "GROQ_API_KEY", "base_url": "https://api.groq.com/openai/v1"}
    print("Hai detto:", ascolta(cfg))
