import customtkinter as ctk
import subprocess
import threading
import os
import sys
import psutil
import webbrowser

ctk.set_appearance_mode("System")  
ctk.set_default_color_theme("blue") 

class AgentInstallerGUI(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Local AI Agent - Installatore e Dashboard")
        self.geometry("750x620") # Aumentata l'altezza per ospitare la barra di input
        
        self.ollama_installed = self.check_ollama_installed()
        self.ram_gb = round(psutil.virtual_memory().total / (1024**3))
        self.profile, self.recommended_model = self.detect_hardware()
        self.agent_process = None # Tiene traccia del processo jarvis

        # Titolo
        self.title_label = ctk.CTkLabel(self, text="AGENT-TO-WORK: SETUP AUTOMATICO", font=ctk.CTkFont(size=22, weight="bold"))
        self.title_label.pack(pady=15)

        # Tabella Hardware
        self.hw_frame = ctk.CTkFrame(self)
        self.hw_frame.pack(pady=5, padx=40, fill="x")
        ctk.CTkLabel(self.hw_frame, text=f"💻 Sistema Operativo: {sys.platform.upper()}", font=ctk.CTkFont(size=14)).pack(anchor="w", padx=15, pady=2)
        ctk.CTkLabel(self.hw_frame, text=f"📊 RAM Rilevata: {self.ram_gb} GB", font=ctk.CTkFont(size=14)).pack(anchor="w", padx=15, pady=2)
        ctk.CTkLabel(self.hw_frame, text=f"⚙️ Profilo Assegnato: {self.profile}", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=15, pady=2)
        ctk.CTkLabel(self.hw_frame, text=f"🤖 Modello Consigliato: {self.recommended_model}", font=ctk.CTkFont(size=14)).pack(anchor="w", padx=15, pady=2)

        # Stato Ollama
        self.ollama_frame = ctk.CTkFrame(self)
        self.ollama_frame.pack(pady=5, padx=40, fill="x")
        if self.ollama_installed:
            ctk.CTkLabel(self.ollama_frame, text="✅ Ollama rilevato sul sistema!", text_color="green", font=ctk.CTkFont(size=13, weight="bold")).pack(side="left", padx=15, pady=8)
        else:
            ctk.CTkLabel(self.ollama_frame, text="❌ Ollama NON trovato.", text_color="orange", font=ctk.CTkFont(size=13)).pack(side="left", padx=15, pady=8)
            ctk.CTkButton(self.ollama_frame, text="Scarica Ollama", command=self.open_ollama_web, fg_color="#E06666", hover_color="#CC0000").pack(side="right", padx=15, pady=5)

        # Console di Log
        ctk.CTkLabel(self, text="Console di Output ed Interazione:", font=ctk.CTkFont(size=12)).pack(anchor="w", padx=40, pady=(10,0))
        self.textbox = ctk.CTkTextbox(self, width=670, height=180)
        self.textbox.pack(pady=5, padx=40)
        self.textbox.configure(state="disabled")

        # BARRA DI INPUT UTENTE (Risolve il problema dell'EOF)
        self.input_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.input_frame.pack(pady=5, padx=40, fill="x")
        
        self.user_entry = ctk.CTkEntry(self.input_frame, placeholder_text="Scrivi un comando per Jarvis qui e premi Invio...", width=530, state="disabled")
        self.user_entry.pack(side="left", padx=(0, 10))
        self.user_entry.bind("<Return>", lambda event: self.send_command_to_agent())
        
        self.send_btn = ctk.CTkButton(self.input_frame, text="Invia", width=120, command=self.send_command_to_agent, state="disabled")
        self.send_btn.pack(side="right")

        # Pulsanti Inferiori
        self.actions_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.actions_frame.pack(pady=15, fill="x", padx=40)

        self.install_btn = ctk.CTkButton(self.actions_frame, text="1. Installa Ambiente e Modelli", command=self.start_install_thread, fg_color="#3D85C6")
        self.install_btn.pack(side="left", expand=True, fill="x", padx=5)

        self.start_btn = ctk.CTkButton(self.actions_frame, text="2. Avvia Jarvis Agente", command=self.start_agent_thread, fg_color="gray", state="disabled")
        self.start_btn.pack(side="right", expand=True, fill="x", padx=5)

    def check_ollama_installed(self):
        try:
            subprocess.run(["ollama", "--version"], stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
            return True
        except Exception:
            return False

    def detect_hardware(self):
        if self.ram_gb <= 8:
            return "Medium (Configurazione Bilanciata)", "qwen2.5:3b-instruct-q4_K_M"
        elif self.ram_gb <= 16:
            return "High (Performance Ottimali)", "llama3:8b"
        else:
            return "Ultra (Massima Precisione)", "llama3:8b"

    def open_ollama_web(self):
        webbrowser.open("https://ollama.com")
        self.log("[ℹ️] Apertura pagina Ollama nel browser. Installalo e riavvia.")

    def log(self, message):
        self.textbox.configure(state="normal")
        self.textbox.insert("end", message + "\n")
        self.textbox.configure(state="disabled")
        self.textbox.yview("end")

    def start_install_thread(self):
        self.install_btn.configure(state="disabled")
        threading.Thread(target=self.run_installation, daemon=True).start()

    def run_installation(self):
        self.log("[-] Avvio installazione componenti...")
        try:
            subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "pip"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8")
            if os.path.exists("requirements.txt"):
                subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, encoding="utf-8")
            self.log("[✅] Dipendenze installate.")
            
            if os.path.exists("install.py"):
                self.log("[-] Configurazione hardware adattiva...")
                env = os.environ.copy()
                env["OLLAMA_HOST"] = "127.0.0.1:11434"
                if self.ollama_installed:
                    subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env, creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
                
                process = subprocess.Popen([sys.executable, "install.py"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env, encoding="utf-8")
                for line in iter(process.stdout.readline, ''):
                    self.log(line.strip())
                process.wait()
                
            self.log("[🎉] Setup completato correttamente!")
            self.start_btn.configure(state="normal", fg_color="green", hover_color="darkgreen")
        except Exception as e:
            self.log(f"[❌] Errore: {str(e)}")
            self.install_btn.configure(state="normal")

    def start_agent_thread(self):
        self.start_btn.configure(state="disabled")
        self.user_entry.configure(state="normal")
        self.send_btn.configure(state="normal")
        threading.Thread(target=self.run_agent, daemon=True).start()

    def run_agent(self):
        self.log("[🚀] Avvio di Jarvis in corso...")
        if not os.path.exists("jarvis.py"):
            self.log("[❌] Impossibile trovare jarvis.py")
            return
            
        env = os.environ.copy()
        env["OLLAMA_HOST"] = "127.0.0.1:11434"
        
        try:
            self.agent_process = subprocess.Popen(
                [sys.executable, "jarvis.py"],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                env=env,
                encoding="utf-8",
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            )
            
            for line in iter(self.agent_process.stdout.readline, ''):
                cleaned_line = line.strip()
                # MODIFICA APPLICATA: Salta le righe vuote e i prompt duplicati inviati dal terminale di jarvis
                if cleaned_line and cleaned_line != "Tu:":
                    self.log(cleaned_line)
                
            self.agent_process.wait()
        except Exception as e:
            self.log(f"[❌] Errore esecuzione: {str(e)}")
            
        self.user_entry.configure(state="disabled")
        self.send_btn.configure(state="disabled")
        self.start_btn.configure(state="normal", fg_color="green")

    def send_command_to_agent(self):
        """Prende il testo scritto nella casella e lo passa all'input() di jarvis.py"""
        command = self.user_entry.get().strip()
        if command and self.agent_process and self.agent_process.poll() is None:
            self.log(f"Tu: {command}") # Visualizza cosa hai scritto nel log
            try:
                self.agent_process.stdin.write(command + "\n")
                self.agent_process.stdin.flush()
            except Exception as e:
                self.log(f"[X] Impossibile inviare comando: {str(e)}")
            self.user_entry.delete(0, "end")

if __name__ == "__main__":
    app = AgentInstallerGUI()
    app.mainloop()
