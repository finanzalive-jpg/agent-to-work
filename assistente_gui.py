"""
assistente_gui.py - Interfaccia stile Siri/Jarvis per Agent-to-Work.

- Ascolto A MANI LIBERE: non devi premere nulla. L'app sente quando inizi a
  parlare e quando smetti (rilevamento voce/silenzio) e invia da sola.
- Sfera luminosa che pulsa e cambia colore in base allo stato:
  blu = in attesa, verde = ti ascolto, arancione = sto pensando, viola = parlo.
- Casella di testo di riserva (puoi anche scrivere invece di parlare).

Avvio:  python assistente_gui.py
Richiede:  pip install -r requirements.txt   (customtkinter, sounddevice, numpy, edge-tts, playsound)
"""
import os
import sys
import math
import time
import queue
import difflib
import tempfile
import threading
import wave

import customtkinter as ctk

# Riusiamo il cervello e le skill gia' pronti in jarvis.py
import jarvis
import voce

SR = 16000          # frequenza microfono
BLOCCO = 1600       # 0.1s per blocco
SILENZIO_STOP = 14  # ~1.4s di silenzio = fine frase (ti lascia respirare tra le parole)
MIN_BLOCCHI_VOCE = 2  # almeno ~0.2s di voce per non partire col rumore

COLORI = {
    "attesa":   "#2563eb",   # blu
    "ascolto":  "#22c55e",   # verde
    "pensiero": "#f59e0b",   # arancione
    "parlo":    "#a855f7",   # viola
}
ETICHETTE = {
    "attesa":   "In attesa",
    "ascolto":  "Ti ascolto...",
    "pensiero": "Sto pensando...",
    "parlo":    "Parlo...",
}


class AssistenteApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.nome = jarvis.NOME_ASSISTENTE.capitalize()
        self.title(self.nome)
        self.geometry("520x680")
        ctk.set_appearance_mode("dark")
        ctk.set_default_color_theme("dark-blue")
        self.configure(fg_color="#0b0f1a")

        self.stato = "attesa"
        self.mic_attivo = True
        self.sta_elaborando = False
        self.coda = queue.Queue()      # messaggi dal thread audio alla UI
        self._fase_anim = 0.0

        # Parola di attivazione (il nome dell'assistente, da config.json -> assistant_name)
        self.wake = jarvis.NOME_ASSISTENTE.lower()
        self.wake_attivo = True        # si attiva solo se sente il nome
        self.attiva_fino = 0.0         # finestra per il comando dopo aver detto solo il nome

        self._forza = False            # pulsante "Parla": forza l'ascolto subito
        self._bypass_wake = False      # salta la parola di attivazione per questa frase
        self._soglia = 500.0           # soglia voce (aggiornata dalla calibrazione)
        self.sta_parlando = False      # True mentre l'assistente parla (per il barge-in)
        self._interrompi = False       # True quando l'utente la interrompe a voce

        self._costruisci_ui()
        self._avvia_audio()
        self.after(40, self._anima)
        self.after(80, self._svuota_coda)
        self.protocol("WM_DELETE_WINDOW", self._chiudi)

    # ---------------- UI ----------------
    def _costruisci_ui(self):
        self.lbl_titolo = ctk.CTkLabel(self, text=self.nome, font=("Segoe UI", 30, "bold"),
                                       text_color="#e5edff")
        self.lbl_titolo.pack(pady=(22, 2))

        self.lbl_stato = ctk.CTkLabel(self, text=ETICHETTE["attesa"], font=("Segoe UI", 15),
                                      text_color="#8aa0c6")
        self.lbl_stato.pack(pady=(0, 8))

        # Sfera (canvas)
        self.canvas = ctk.CTkCanvas(self, width=300, height=260, bg="#0b0f1a",
                                    highlightthickness=0)
        self.canvas.pack(pady=(2, 0))

        # Barretta livello microfono (per vedere se ti sente)
        self.lbl_mic = ctk.CTkLabel(self, text="🎤 livello microfono", font=("Segoe UI", 11),
                                    text_color="#6b7fa6")
        self.lbl_mic.pack(pady=(0, 0))
        self.bar_livello = ctk.CTkProgressBar(self, width=300, height=10)
        self.bar_livello.set(0)
        self.bar_livello.pack(pady=(2, 6))

        self.btn_stop = ctk.CTkButton(self, text="⏹  Ferma la voce", height=46, width=320,
                                      font=("Segoe UI", 15, "bold"),
                                      fg_color="#b91c1c", hover_color="#991b1b",
                                      command=self._ferma_voce)
        self.btn_stop.pack(pady=(0, 6))

        # Trascrizione / conversazione
        self.box = ctk.CTkTextbox(self, width=460, height=180, font=("Segoe UI", 13),
                                  fg_color="#111827", text_color="#d7e3ff", wrap="word")
        self.box.pack(pady=10)
        self.box.configure(state="disabled")

        # Riga in basso: casella di testo (riserva) + pulsante microfono
        riga = ctk.CTkFrame(self, fg_color="transparent")
        riga.pack(pady=4, fill="x", padx=30)

        self.entry = ctk.CTkEntry(riga, placeholder_text="...oppure scrivi qui", height=40)
        self.entry.pack(side="left", fill="x", expand=True)
        self.entry.bind("<Return>", lambda e: self._invia_testo())

        self.btn_invia = ctk.CTkButton(riga, text="Invia", width=70, height=40,
                                       command=self._invia_testo)
        self.btn_invia.pack(side="left", padx=(8, 0))

        riga2 = ctk.CTkFrame(self, fg_color="transparent")
        riga2.pack(pady=(8, 16))

        self.btn_parla = ctk.CTkButton(riga2, text="🎙️ Parla", height=40, width=120,
                                       fg_color="#1f2937", hover_color="#374151",
                                       command=self._parla_ora)
        self.btn_parla.pack(side="left", padx=4)

        self.btn_mic = ctk.CTkButton(riga2, text="🎤 Mic: ON", height=40, width=120,
                                     fg_color="#1f2937", hover_color="#374151",
                                     command=self._toggle_mic)
        self.btn_mic.pack(side="left", padx=4)

        self.btn_wake = ctk.CTkButton(riga2, text=f'🔔 "{self.nome}"', height=40, width=150,
                                      fg_color="#1f2937", hover_color="#374151",
                                      command=self._toggle_wake)
        self.btn_wake.pack(side="left", padx=4)

    def _scrivi(self, chi, testo):
        self.box.configure(state="normal")
        self.box.insert("end", f"{chi}: {testo}\n\n")
        self.box.see("end")
        self.box.configure(state="disabled")

    def _imposta_stato(self, s):
        self.stato = s
        testo = ETICHETTE.get(s, "")
        if s == "attesa" and self.wake_attivo:
            testo = f'Dì "{self.nome}..."'
        self.lbl_stato.configure(text=testo)

    # ---------------- Animazione sfera ----------------
    def _anima(self):
        self._fase_anim += 0.12
        self.canvas.delete("all")
        cx, cy = 150, 150
        base = 70
        pulse = 10 * math.sin(self._fase_anim) + (18 if self.stato in ("ascolto", "parlo") else 6)
        colore = COLORI.get(self.stato, "#2563eb")
        # aloni concentrici
        for i, r in enumerate((base + pulse + 46, base + pulse + 24, base + pulse)):
            self.canvas.create_oval(cx - r, cy - r, cx + r, cy + r, outline=colore,
                                    width=2 if i < 2 else 3)
        # nucleo
        r = base - 18
        self.canvas.create_oval(cx - r, cy - r, cx + r, cy + r, fill=colore, outline="")
        self.after(40, self._anima)

    # ---------------- Coda messaggi (thread -> UI) ----------------
    def _svuota_coda(self):
        try:
            while True:
                tipo, dato = self.coda.get_nowait()
                if tipo == "stato":
                    self._imposta_stato(dato)
                elif tipo == "tu":
                    self._scrivi("Tu", dato)
                elif tipo == "assistente":
                    self._scrivi(self.nome, dato)
                elif tipo == "livello":
                    try:
                        self.bar_livello.set(dato)
                    except Exception:
                        pass
        except queue.Empty:
            pass
        self.after(80, self._svuota_coda)

    # ---------------- Esecuzione (nel thread worker) ----------------
    def _esegui_e_parla(self, testo_utente):
        """Mostra, pensa, esegue e parla. Chiamato dal worker (sta_elaborando è già True)."""
        if not testo_utente.strip():
            return
        self.coda.put(("tu", testo_utente))
        self.coda.put(("stato", "pensiero"))
        try:
            risposta = jarvis.rispondi(testo_utente)
        except Exception as e:
            risposta = f"Si è verificato un errore: {e}"
        self.coda.put(("assistente", risposta))
        self.coda.put(("stato", "parlo"))
        self._interrompi = False
        try:
            voce.parla(risposta, jarvis.config.get("voce"), interrompi=lambda: self._interrompi)
        except Exception:
            pass
        self._interrompi = False
        if getattr(jarvis, "IN_ATTESA_SCELTA", False):
            self.attiva_fino = time.time() + 12

    def _parla_breve(self, frase):
        """Dice una frase corta (es. 'Dimmi') e apre la finestra per il comando."""
        self.coda.put(("assistente", frase))
        self.coda.put(("stato", "parlo"))
        try:
            voce.parla(frase, jarvis.config.get("voce"))
        except Exception:
            pass
        self.attiva_fino = time.time() + 7

    def _match_wake(self, testo):
        """Cerca il nome di attivazione in modo TOLLERANTE. Torna (trovato, comando_dopo_il_nome)."""
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
        """Decide se la frase è un comando (controlla la parola di attivazione)."""
        t = (testo or "").strip()
        if not t:
            return
        # Dal pulsante "Parla", da testo scritto, o attivazione disattivata: è sempre un comando
        if bypass or not self.wake_attivo:
            self._esegui_e_parla(t)
            return
        # Era stata chiamata da poco: questa frase è il comando
        if time.time() < self.attiva_fino:
            self.attiva_fino = 0.0
            self._esegui_e_parla(t)
            return
        trovato, comando = self._match_wake(t)
        if not trovato:
            return  # non chiamata: ignora i discorsi di stanza (nemmeno la mostra)
        if comando:
            self._esegui_e_parla(comando)      # "Atlas, apri la calcolatrice"
        else:
            self._parla_breve("Dimmi.")         # solo "Atlas"

    def _invia_testo(self):
        testo = self.entry.get().strip()
        if not testo:
            return
        self.entry.delete(0, "end")
        self.sta_elaborando = True
        self._audio_q.put(("testo", testo))

    def _parla_ora(self):
        """Forza un ascolto senza dover dire il nome."""
        if self.sta_elaborando:
            return
        self._bypass_wake = True
        self._forza = True
        self.coda.put(("stato", "ascolto"))

    def _ferma_voce(self):
        """Ferma subito la voce mentre sta parlando (un clic)."""
        self._interrompi = True

    def _toggle_mic(self):
        self.mic_attivo = not self.mic_attivo
        self.btn_mic.configure(text=f"🎤 Mic: {'ON' if self.mic_attivo else 'OFF'}")
        if not self.mic_attivo:
            self.coda.put(("stato", "attesa"))

    def _toggle_wake(self):
        self.wake_attivo = not self.wake_attivo
        if self.wake_attivo:
            self.btn_wake.configure(text=f'🔔 "{self.nome}"')
        else:
            self.btn_wake.configure(text="🔔 libera")
        self.attiva_fino = 0.0
        self.coda.put(("stato", "attesa"))

    # ---------------- Worker: trascrive ed esegue (separato dall'audio) ----------------
    def _worker(self):
        import numpy as np
        while self._audio_on:
            try:
                item = self._audio_q.get(timeout=0.5)
            except queue.Empty:
                continue
            try:
                if item[0] == "voce":
                    _, audio_raw, bypass = item
                    testo = self._trascrivi(audio_raw, np)
                    if testo and testo.strip():
                        self._instrada(testo, bypass)
                elif item[0] == "testo":
                    self._esegui_e_parla(item[1])
            except Exception as e:
                self.coda.put(("assistente", f"Errore: {e}"))
            finally:
                self.sta_elaborando = False
                if getattr(jarvis, "IN_ATTESA_SCELTA", False) or time.time() < self.attiva_fino:
                    self.coda.put(("stato", "ascolto"))
                else:
                    self.coda.put(("stato", "attesa"))

    def _trascrivi(self, audio_raw, np):
        """Da audio grezzo a testo (con filtro anti-silenzio e guadagno). '' se nulla."""
        if int(np.max(np.abs(audio_raw))) < 500:   # quasi silenzio -> non inventare
            return ""
        self.coda.put(("stato", "pensiero"))
        audio = audio_raw.astype("float32")
        picco = float(np.max(np.abs(audio))) or 1.0
        if picco < 32767 * 0.9:
            audio = audio * (32767 * 0.9 / picco)   # guadagno
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
            self.coda.put(("assistente", f"Non ho capito l'audio: {e}"))
            return ""
        finally:
            try:
                os.remove(percorso)
            except Exception:
                pass

    # ---------------- Thread audio: SOLO rilevamento voce (robusto) ----------------
    def _avvia_audio(self):
        self._audio_on = True
        self._audio_q = queue.Queue()
        threading.Thread(target=self._worker, daemon=True).start()
        threading.Thread(target=self._loop_audio, daemon=True).start()

    def _loop_audio(self):
        try:
            import sounddevice as sd
            import numpy as np
        except Exception as e:
            self.coda.put(("assistente", f"Microfono non disponibile ({e}). Usa la casella di testo."))
            return

        from collections import deque
        finestra = deque(maxlen=40)
        preroll = deque(maxlen=3)     # tiene gli ultimi ~0.3s PRIMA della voce (non taglia l'inizio)
        MAX_BLOCCHI = 70

        # Ciclo esterno: se il microfono cade, lo RIAPRE da solo (niente blocco permanente)
        while self._audio_on:
            frames = []
            registrando = False
            silenzio = 0
            blocchi_voce = 0
            try:
                with sd.InputStream(samplerate=SR, channels=1, dtype="int16", blocksize=BLOCCO) as stream:
                    while self._audio_on:
                        try:
                            blk, _ = stream.read(BLOCCO)
                        except Exception:
                            break   # stream caduto: esci e riapri

                        if not self.mic_attivo or self.sta_elaborando:
                            frames, registrando, silenzio, blocchi_voce = [], False, 0, 0
                            preroll.clear()
                            self.coda.put(("livello", 0))
                            continue

                        rms = float(np.sqrt(np.mean(blk.astype("float32") ** 2)) or 0)
                        finestra.append(rms)
                        rumore = max(min(finestra), 50.0)
                        soglia_on = rumore * 2.0 + 70
                        soglia_off = rumore * 1.5 + 40
                        self._soglia = soglia_on
                        self.coda.put(("livello", max(0.0, min((rms - rumore) / (rumore * 3.0 + 200), 1.0))))

                        if not registrando:
                            preroll.append(blk.copy())
                            if rms > soglia_on or self._forza:
                                registrando = True
                                frames = list(preroll)   # include il PRE-ROLL: non perde l'inizio
                                blocchi_voce = 1 if rms > soglia_on else 0
                                silenzio = 0
                                self._forza = False
                                self.coda.put(("stato", "ascolto"))
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
                                    # Passa il lavoro al worker (così l'audio non si blocca mai)
                                    bypass = self._bypass_wake
                                    self._bypass_wake = False
                                    self.sta_elaborando = True
                                    self._audio_q.put(("voce", np.concatenate(frames, axis=0), bypass))
                                else:
                                    self.coda.put(("stato", "attesa"))
                                frames, silenzio, blocchi_voce = [], 0, 0
                                preroll.clear()
            except Exception:
                pass
            # Microfono caduto o errore: breve pausa e riapri
            if self._audio_on:
                time.sleep(0.4)

    def _chiudi(self):
        self._audio_on = False
        self.destroy()


if __name__ == "__main__":
    if not os.path.exists("config.json"):
        print("[X] Esegui prima: python install.py")
        sys.exit(1)
    app = AssistenteApp()
    app.mainloop()
