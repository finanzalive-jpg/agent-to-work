"""
atlas_app.py - App desktop Atlas con cervello 3D e mini pill.

Doppia modalita':
  1. Finestra BRAIN: mostra cervello_atlas.html (nebulosa neurale 3D)
  2. Mini PILL: barretta stile Siri vicino al clock, sempre in primo piano
  3. Icona TRAY: click destro -> Mostra cervello / Esci

Il motore vocale (assistente_gui.py) comunica con il cervello via:
  window.atlas.setState('idle' | 'speaking' | 'reasoning')
  window.atlas.setLevel(0-1)
  window.atlas.fire('Nome Skill')

Avvio:  python atlas_app.py
Richiede:  pip install pywebview pystray pillow
"""
import os
import sys
import threading
import time

# --- Percorsi ---
DIR = os.path.dirname(os.path.abspath(__file__))
BRAIN_HTML = os.path.join(DIR, "cervello_atlas.html")

# --- Verifica dipendenze ---
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


# ============================================================
#  TRAY ICON
# ============================================================
def _crea_icona_tray():
    """Crea un'icona rotonda blu per il system tray."""
    img = Image.new("RGBA", (64, 64), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    draw.ellipse([4, 4, 60, 60], fill=(74, 240, 255, 255))
    draw.ellipse([18, 18, 46, 46], fill=(3, 7, 18, 255))
    return img


class AtlasApp:
    """Gestisce le due finestre (brain + pill) e il tray."""

    def __init__(self):
        self.brain_window = None
        self.pill_window = None
        self.tray_icon = None
        self._running = True
        self._brain_visible = True

    # ---- Brain window ----
    def _crea_brain(self):
        """Finestra principale col cervello 3D."""
        self.brain_window = webview.create_window(
            "Atlas Brain",
            url=BRAIN_HTML,
            width=1100,
            height=750,
            min_size=(600, 400),
            background_color="#030712",
            text_select=False,
        )
        self.brain_window.events.closed += self._on_brain_closed

    def _on_brain_closed(self):
        self._brain_visible = False

    # ---- Pill window (mini barra Siri) ----
    def _pill_html(self):
        """HTML inline per la mini pill - onda luminosa."""
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
.pill.speaking .dot{background:#ff5fa0;box-shadow:0 0 8px rgba(255,95,160,.6);animation:speak .6s infinite}
.pill.reasoning .dot{background:#ffc84a;box-shadow:0 0 8px rgba(255,200,74,.6);animation:think 1s infinite}
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
  setState:function(s){
    var p=document.getElementById('pill');
    p.className='pill'+(s!=='idle'?' '+s:'');
  }
};
</script>
</body></html>"""

    def _crea_pill(self):
        """Mini finestra pill sempre in primo piano."""
        self.pill_window = webview.create_window(
            "Atlas",
            html=self._pill_html(),
            width=240,
            height=54,
            x=0,  # verra' spostata dopo
            y=0,
            frameless=True,
            on_top=True,
            transparent=True,
            background_color="#000000",
            easy_drag=True,
        )

    # ---- Tray ----
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

    # ---- API esposta a pywebview (pill -> brain) ----
    class JsApi:
        def __init__(self, app):
            self._app = app

        def mostra_brain(self):
            """Chiamata dalla pill: mostra/nasconde il cervello."""
            self._app._toggle_brain()

    # ---- Motore: aggiorna stato nelle finestre ----
    def set_state(self, stato):
        """Chiamato dal motore vocale per aggiornare entrambe le finestre."""
        if self.brain_window:
            try:
                self.brain_window.evaluate_js(
                    f"window.atlas && window.atlas.setState('{stato}')"
                )
            except Exception:
                pass
        if self.pill_window:
            try:
                self.pill_window.evaluate_js(
                    f"window.atlasPill && window.atlasPill.setState('{stato}')"
                )
            except Exception:
                pass

    def fire_skill(self, nome):
        """Accende una skill specifica nel cervello."""
        if self.brain_window:
            try:
                self.brain_window.evaluate_js(
                    f"window.atlas && window.atlas.fire('{nome}')"
                )
            except Exception:
                pass

    # ---- Posiziona pill in basso a destra ----
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
            pass  # non Windows, la pill resta dove e'

    # ---- Avvio ----
    def avvia(self):
        """Avvia l'app Atlas con cervello + pill + tray."""
        self._crea_brain()
        self._crea_pill()

        # API per la pill
        if self.pill_window:
            self.pill_window.expose(self.JsApi(self))

        def _dopo_avvio():
            time.sleep(1.5)
            self._posiziona_pill()
            self._avvia_tray()

        threading.Thread(target=_dopo_avvio, daemon=True).start()

        # webview.start blocca - gira su tutte le finestre
        webview.start(debug=False)


# ============================================================
#  ENTRY POINT
# ============================================================
if __name__ == "__main__":
    if not os.path.isfile(BRAIN_HTML):
        print(f"[!] File cervello non trovato: {BRAIN_HTML}")
        print("    Assicurati che cervello_atlas.html sia nella cartella del progetto.")
        sys.exit(1)

    app = AtlasApp()
    app.avvia()
