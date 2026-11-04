"""
atlas_unificato.py - App unificata Atlas: cervello 3D + voce + pill + tray.

UN SOLO COMANDO PER TUTTO:
  python atlas_unificato.py

Cosa parte:
  1. Finestra BRAIN: cervello 3D (cervello_atlas.html) con chat overlay e input testo
  2. Mini PILL: barretta stile Siri vicino al clock, sempre in primo piano
  3. Icona TRAY: click destro -> Mostra cervello / Esci
  4. Motore VOCE: ascolto continuo, attivazione per nome, silenzio detection

Il cervello si anima IN SYNC con la voce:
  attesa   -> idle (pulsazione lenta)
  ascolto  -> idle + livello microfono
  pensiero -> reasoning (nodi accesi, impulsi veloci)
  parlo    -> speaking (pulsazione ritmica)

Richiede:  pip install -r requirements.txt
"""
import os
import sys
import time
import queue
import wave
import difflib
import tempfile
import threading

# --- Percorsi ---
DIR = os.path.dirname(os.path.abspath(__file__))
BRAIN_HTML = os.path.join(DIR, "cervello_atlas.html")

# --- Moduli interni ---
import jarvis
import voce

# --- Dipendenze esterne ---
try:
    import webview
except ImportError:
    print("[!] Installa pywebview: pip install pywebview")
    sys.exit(1)

try:
    import pystray
    from PIL import Image, ImageDraw
except ImportError:
    pystray = None
    print("[i] pystray/pillow non trovati - niente icona nel tray. pip install pystray pillow")

# --- Costanti audio ---
SR = 16000
BLOCCO = 1600
SILENZIO_STOP = 14
MIN_BLOCCHI_VOCE = 2


# ============================================================
#  TRAY ICON
# ============================================================
def _crea_icona_tray():
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([4, 4, 60, 60], fill=(74, 240, 255, 255))
    draw.ellipse([18, 18, 46, 46], fill=(3, 7, 18, 255))
    return img


# ============================================================
#  API JavaScript esposta a pywebview
# ============================================================
class BrainApi:
    """Funzioni chiamabili dalla pagina HTML via pywebview.api.*"""

    def __init__(self, app):
        self._app = app

    def mostra_brain(self):
        """Pill -> toggle cervello."""
        self._app._toggle_brain()

    def invia_testo(self, testo):
        """Input testo dalla barra nella pagina HTML."""
        if not testo or not testo.strip():
            return
        self._app._audio_q.put(("testo", testo.strip()))

    def toggle_mic(self, on):
        """Attiva/disattiva microfono dal pulsante HTML."""
        self._app.mic_attivo = bool(on)
        if not on:
            self._app._js_q.put(("stato", "attesa"))

    def ferma_voce(self):
        """Interrompe la voce."""
        self._app._interrompi = True

    def toggle_fullscreen(self):
        """Attiva/disattiva schermo intero."""
        try:
            w = self._app.brain_window
            w.toggle_fullscreen()
        except Exception as e:
            print(f"[ATLAS] Errore fullscreen: {e}")


# ============================================================
#  APP UNIFICATA
# ============================================================
class AtlasUnificato:
    def __init__(self):
        # --- Finestre ---
        self.brain_window = None
        self.pill_window = None
        self.tray_icon = None
        self._running = True
        self._brain_visible = True

        # --- Stato voce ---
        self.nome = jarvis.NOME_ASSISTENTE.capitalize()
        self.wake = jarvis.NOME_ASSISTENTE.lower()
        self.wake_attivo = True
        self.attiva_fino = 0.0
        self.mic_attivo = True
        self.sta_elaborando = False
        self._forza = False
        self._bypass_wake = False
        self._soglia = 500.0
        self._interrompi = False
        self._audio_on = False
        self._audio_q = queue.Queue()

        # --- Coda JS: il thread audio NON chiama mai evaluate_js direttamente ---
        # Mette comandi qui, e un bridge thread li consuma e li invia al browser.
        self._js_q = queue.Queue()

    # ================================================================
    #  BRAIN WINDOW
    # ================================================================
    def _crea_brain(self):
        self.brain_window = webview.create_window(
            "Atlas Brain",
            url=BRAIN_HTML,
            width=520,
            height=750,
            min_size=(400, 500),
            background_color="#030712",
            text_select=False,
        )
        self.brain_window.events.closed += self._on_brain_closed

    def _on_brain_closed(self):
        self._brain_visible = False

    # ================================================================
    #  PILL WINDOW
    # ================================================================
    def _pill_html(self):
        return """<!DOCTYPE html>
<html><head><meta charset="utf-8">
<style>
*{margin:0;padding:0}
html,body{height:100%;overflow:hidden;background:transparent;user-select:none;-webkit-app-region:drag}
.pill{
  width:220px;height:44px;margin:0 auto;border-radius:22px;
  background:rgba(3,7,18,.85);border:1px solid rgba(74,240,255,.3);
  display:flex;align-items:center;justify-content:center;gap:8px;
  backdrop-filter:blur(12px);cursor:pointer;
  box-shadow:0 4px 20px rgba(0,0,0,.5),inset 0 0 20px rgba(74,240,255,.05);
}
.dot{width:10px;height:10px;border-radius:50%;background:#4af0ff;
  box-shadow:0 0 8px rgba(74,240,255,.6);animation:pulse 2s infinite}
.label{color:#dde7f6;font:500 13px/1 'Segoe UI',system-ui;letter-spacing:.1em}
@keyframes pulse{0%,100%{opacity:.6;transform:scale(1)}50%{opacity:1;transform:scale(1.3)}}
.pill.ascolto .dot{background:#22c55e;box-shadow:0 0 8px rgba(34,197,94,.6);animation:speak .8s infinite}
.pill.pensiero .dot{background:#f59e0b;box-shadow:0 0 8px rgba(245,158,11,.6);animation:think 1s infinite}
.pill.parlo .dot{background:#a855f7;box-shadow:0 0 8px rgba(168,85,247,.6);animation:speak .6s infinite}
@keyframes speak{0%,100%{transform:scale(1)}50%{transform:scale(1.5)}}
@keyframes think{0%,100%{opacity:.5}50%{opacity:1}}
</style></head>
<body>
<div class="pill" id="pill" onclick="window.pywebview&&window.pywebview.api&&window.pywebview.api.mostra_brain()">
  <div class="dot" id="dot"></div>
  <div class="label">ATLAS</div>
</div>
<script>
window.atlasPill={
  setVoiceState:function(s){
    var p=document.getElementById('pill');
    p.className='pill'+(s!=='attesa'?' '+s:'');
  }
};
</script>
</body></html>"""

    def _crea_pill(self):
        self.pill_window = webview.create_window(
            "Atlas",
            html=self._pill_html(),
            width=240,
            height=54,
            x=0, y=0,
            frameless=True,
            on_top=True,
            transparent=True,
            background_color="#000000",
            easy_drag=True,
        )

    # ================================================================
    #  TRAY
    # ================================================================
    def _avvia_tray(self):
        if not pystray:
            return
        menu = pystray.Menu(
            pystray.MenuItem("Mostra cervello", self._toggle_brain, default=True),
            pystray.MenuItem("Esci", self._esci),
        )
        self.tray_icon = pystray.Icon("Atlas", _crea_icona_tray(), "Atlas AI", menu)
        threading.Thread(target=self.tray_icon.run, daemon=True).start()

    def _toggle_brain(self, icon=None, item=None):
        if self.brain_window:
            try:
                if self._brain_visible:
                    self.brain_window.hide()
                    self._brain_visible = False
                else:
                    self.brain_window.show()
                    self._brain_visible = True
            except Exception:
                pass

    def _esci(self, icon=None, item=None):
        self._running = False
        self._audio_on = False
        if self.tray_icon:
            try:
                self.tray_icon.stop()
            except Exception:
                pass
        try:
            if self.brain_window:
                self.brain_window.destroy()
            if self.pill_window:
                self.pill_window.destroy()
        except Exception:
            pass

    # ================================================================
    #  BRIDGE JS: thread dedicato che consuma la coda e chiama evaluate_js
    #  Cosi' il thread audio non si blocca MAI su IPC.
    # ================================================================
    def _avvia_js_bridge(self):
        threading.Thread(target=self._js_bridge_loop, daemon=True).start()

    def _js_bridge_loop(self):
        """Consuma la coda JS e invia comandi al browser. Throttle: max ~15 cmd/s."""
        ultimo_livello = 0
        while self._running:
            try:
                tipo, dato = self._js_q.get(timeout=0.1)
            except queue.Empty:
                continue
            try:
                if tipo == "stato":
                    # Aggiorna stato voce in entrambe le finestre
                    if self.brain_window:
                        self.brain_window.evaluate_js(
                            f"window.atlas && window.atlas.setVoiceState('{dato}')"
                        )
                    if self.pill_window:
                        self.pill_window.evaluate_js(
                            f"window.atlasPill && window.atlasPill.setVoiceState('{dato}')"
                        )
                elif tipo == "livello":
                    # Throttle: salta aggiornamenti troppo vicini
                    now = time.monotonic()
                    if now - ultimo_livello < 0.12:
                        continue
                    ultimo_livello = now
                    if self.brain_window:
                        self.brain_window.evaluate_js(
                            f"window.atlas && window.atlas.setLevel({dato:.3f})"
                        )
                elif tipo == "msg":
                    who, text = dato
                    safe = text.replace("\\", "\\\\").replace("'", "\\'").replace("\n", "\\n")
                    who_safe = who.replace("'", "\\'")
                    if self.brain_window:
                        self.brain_window.evaluate_js(
                            f"window.atlas && window.atlas.addMessage('{who_safe}','{safe}')"
                        )
                elif tipo == "fire":
                    safe = dato.replace("'", "\\'")
                    if self.brain_window:
                        self.brain_window.evaluate_js(
                            f"window.atlas && window.atlas.fire('{safe}')"
                        )
            except Exception:
                pass

    # --- Metodi comodi che mettono in coda (thread-safe, non bloccanti) ---
    def _set_voice_state(self, stato):
        self._js_q.put(("stato", stato))

    def _set_level(self, v):
        self._js_q.put(("livello", v))

    def _fire_skill(self, nome):
        self._js_q.put(("fire", nome))

    def _add_message(self, who, text):
        self._js_q.put(("msg", (who, text)))

    # ================================================================
    #  MOTORE VOCE (da assistente_gui.py)
    # ================================================================
    def _esegui_e_parla(self, testo_utente):
        if not testo_utente.strip():
            return
        self._add_message("Tu", testo_utente)
        self._set_voice_state("pensiero")
        try:
            risposta = jarvis.rispondi(testo_utente)
        except Exception as e:
            risposta = f"Si è verificato un errore: {e}"
        self._add_message(self.nome, risposta)
        self._set_voice_state("parlo")
        self._interrompi = False
        try:
            voce.parla(risposta, jarvis.config.get("voce"), interrompi=lambda: self._interrompi)
        except Exception:
            pass
        self._interrompi = False
        if getattr(jarvis, "IN_ATTESA_SCELTA", False):
            self.attiva_fino = time.time() + 12

    def _parla_breve(self, frase):
        self._add_message(self.nome, frase)
        self._set_voice_state("parlo")
        try:
            voce.parla(frase, jarvis.config.get("voce"))
        except Exception:
            pass
        self.attiva_fino = time.time() + 7

    def _match_wake(self, testo):
        low = testo.lower().replace(",", " ").replace(".", " ")
        parole = low.split()
        for i, p in enumerate(parole[:2]):
            if self.wake in p or difflib.SequenceMatcher(None, p, self.wake).ratio() >= 0.7:
                return True, " ".join(parole[i + 1:]).strip(" ,.:;!?-")
        pos = low.find(self.wake)
        if pos != -1:
            return True, low[pos + len(self.wake):].strip(" ,.:;!?-")
        return False, ""

    def _instrada(self, testo, bypass):
        t = (testo or "").strip()
        if not t:
            return
        if bypass or not self.wake_attivo:
            self._esegui_e_parla(t)
            return
        if time.time() < self.attiva_fino:
            self.attiva_fino = 0.0
            self._esegui_e_parla(t)
            return
        trovato, comando = self._match_wake(t)
        if not trovato:
            return
        if comando:
            self._esegui_e_parla(comando)
        else:
            self._parla_breve("Dimmi.")

    # ================================================================
    #  WORKER THREAD (trascrizione + esecuzione)
    # ================================================================
    def _worker(self):
        import numpy as np
        print("[WORKER] Thread worker avviato")
        while self._audio_on:
            try:
                item = self._audio_q.get(timeout=0.5)
            except queue.Empty:
                continue
            try:
                if item[0] == "voce":
                    _, audio_raw, bypass = item
                    livello = int(np.max(np.abs(audio_raw)))
                    print(f"[WORKER] Ricevuto audio: {len(audio_raw)} campioni, picco={livello}, bypass={bypass}")
                    testo = self._trascrivi(audio_raw, np)
                    print(f"[WORKER] Trascrizione: '{testo}'")
                    if testo and testo.strip():
                        self._instrada(testo, bypass)
                    else:
                        print("[WORKER] Testo vuoto, ignoro")
                elif item[0] == "testo":
                    self._esegui_e_parla(item[1])
            except Exception as e:
                print(f"[WORKER] ERRORE: {e}")
                self._add_message(self.nome, f"Errore: {e}")
            finally:
                self.sta_elaborando = False
                if getattr(jarvis, "IN_ATTESA_SCELTA", False) or time.time() < self.attiva_fino:
                    self._set_voice_state("ascolto")
                else:
                    self._set_voice_state("attesa")

    def _trascrivi(self, audio_raw, np):
        picco_raw = int(np.max(np.abs(audio_raw)))
        if picco_raw < 500:
            print(f"[TRASCRIVI] Audio troppo basso (picco={picco_raw}), scarto")
            return ""
        print(f"[TRASCRIVI] Audio OK (picco={picco_raw}), invio a Whisper...")
        self._set_voice_state("pensiero")
        audio = audio_raw.astype("float32")
        picco = float(np.max(np.abs(audio))) or 1.0
        if picco < 32767 * 0.9:
            audio = audio * (32767 * 0.9 / picco)
        audio = np.clip(audio, -32768, 32767).astype("int16")
        percorso = tempfile.mktemp(suffix=".wav")
        try:
            with wave.open(percorso, "wb") as wf:
                wf.setnchannels(1)
                wf.setsampwidth(2)
                wf.setframerate(SR)
                wf.writeframes(audio.tobytes())
            return voce.trascrivi(percorso, jarvis.BRAIN_CFG)
        except Exception as e:
            self._add_message(self.nome, f"Non ho capito l'audio: {e}")
            return ""
        finally:
            try:
                os.remove(percorso)
            except Exception:
                pass

    # ================================================================
    #  LOOP AUDIO (rilevamento voce) — NON chiama mai evaluate_js
    # ================================================================
    def _avvia_audio(self):
        self._audio_on = True
        print("[AUDIO] Avvio thread worker e loop audio...")
        threading.Thread(target=self._worker, daemon=True).start()
        threading.Thread(target=self._loop_audio, daemon=True).start()

    def _loop_audio(self):
        try:
            import sounddevice as sd
            import numpy as np
            print(f"[AUDIO] sounddevice OK - dispositivo default: {sd.default.device}")
        except Exception as e:
            print(f"[AUDIO] ERRORE import: {e}")
            self._add_message(self.nome, f"Microfono non disponibile ({e}). Usa l'icona tastiera per scrivere.")
            return

        from collections import deque
        finestra = deque(maxlen=40)
        preroll = deque(maxlen=3)
        MAX_BLOCCHI = 70

        while self._audio_on:
            frames = []
            registrando = False
            silenzio = 0
            blocchi_voce = 0
            try:
                print("[AUDIO] Apro stream microfono...")
                with sd.InputStream(samplerate=SR, channels=1, dtype="int16", blocksize=BLOCCO) as stream:
                    print("[AUDIO] Microfono attivo - in ascolto!")
                    while self._audio_on:
                        try:
                            blk, _ = stream.read(BLOCCO)
                        except Exception:
                            break

                        if not self.mic_attivo or self.sta_elaborando:
                            frames, registrando, silenzio, blocchi_voce = [], False, 0, 0
                            preroll.clear()
                            self._set_level(0)   # va in coda, non blocca
                            continue

                        rms = float(np.sqrt(np.mean(blk.astype("float32") ** 2)) or 0)
                        finestra.append(rms)
                        rumore = max(min(finestra), 50.0)
                        soglia_on = rumore * 2.0 + 70
                        soglia_off = rumore * 1.5 + 40
                        self._soglia = soglia_on
                        lev = max(0.0, min((rms - rumore) / (rumore * 3.0 + 200), 1.0))
                        self._set_level(lev)    # va in coda, non blocca

                        if not registrando:
                            preroll.append(blk.copy())
                            if rms > soglia_on or self._forza:
                                registrando = True
                                frames = list(preroll)
                                blocchi_voce = 1 if rms > soglia_on else 0
                                silenzio = 0
                                self._forza = False
                                self._set_voice_state("ascolto")  # coda
                        else:
                            frames.append(blk.copy())
                            if rms > soglia_off:
                                blocchi_voce += 1
                                silenzio = 0
                            else:
                                silenzio += 1
                            if silenzio >= SILENZIO_STOP or len(frames) >= MAX_BLOCCHI:
                                registrando = False
                                if (blocchi_voce >= MIN_BLOCCHI_VOCE or self._bypass_wake) and not self.sta_elaborando:
                                    bypass = self._bypass_wake
                                    self._bypass_wake = False
                                    self.sta_elaborando = True
                                    print(f"[AUDIO] Voce rilevata! {blocchi_voce} blocchi, invio a trascrizione...")
                                    self._audio_q.put(("voce", np.concatenate(frames, axis=0), bypass))
                                else:
                                    self._set_voice_state("attesa")  # coda
                                frames, silenzio, blocchi_voce = [], 0, 0
                                preroll.clear()
            except Exception as e:
                print(f"[AUDIO] ERRORE stream: {e}")
            if self._audio_on:
                time.sleep(0.4)

    # ================================================================
    #  POSIZIONA PILL
    # ================================================================
    def _posiziona_pill(self):
        if not self.pill_window:
            return
        try:
            import ctypes
            user32 = ctypes.windll.user32
            sw = user32.GetSystemMetrics(0)
            sh = user32.GetSystemMetrics(1)
            self.pill_window.move(sw - 280, sh - 90)
        except Exception:
            pass

    # ================================================================
    #  AVVIO PRINCIPALE
    # ================================================================
    def avvia(self):
        self._crea_brain()
        self._crea_pill()

        # Esponi le API JavaScript per entrambe le finestre
        api = BrainApi(self)
        if self.brain_window:
            self.brain_window.expose(api.invia_testo)
            self.brain_window.expose(api.toggle_mic)
            self.brain_window.expose(api.ferma_voce)
        if self.pill_window:
            self.pill_window.expose(api.mostra_brain)

        def _dopo_avvio():
            time.sleep(2.0)
            self._posiziona_pill()
            self._avvia_tray()
            # Bridge JS: thread dedicato per communicate con il browser
            self._avvia_js_bridge()
            time.sleep(0.3)
            self._avvia_audio()
            # Messaggio di benvenuto
            time.sleep(0.5)
            self._add_message(self.nome, f"Ciao! Sono {self.nome}. Dimmi il mio nome o premi l'icona tastiera per scrivere.")

        threading.Thread(target=_dopo_avvio, daemon=True).start()

        # webview.start() blocca il thread principale
        webview.start(debug=False, gui='edgechromium')


# ============================================================
#  ENTRY POINT
# ============================================================
if __name__ == "__main__":
    if not os.path.isfile(BRAIN_HTML):
        print(f"[!] File cervello non trovato: {BRAIN_HTML}")
        print("    Assicurati che cervello_atlas.html sia nella cartella del progetto.")
        sys.exit(1)

    if not os.path.exists("config.json"):
        print("[X] Esegui prima: python install.py")
        sys.exit(1)

    print(f"[ATLAS] Avvio unificato: cervello 3D + voce + pill + tray")
    print(f"[ATLAS] Nome assistente: {jarvis.NOME_ASSISTENTE}")
    print(f"[ATLAS] Premi l'icona tastiera nel cervello per scrivere")
    print(f"[ATLAS] Oppure di' il nome dell'assistente per attivare la voce")

    app = AtlasUnificato()
    app.avvia()
