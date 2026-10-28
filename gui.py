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
        self.geometry("750x550")
        
        # Stato interno
        self.ollama_installed = self.check_ollama_installed()
        self.ram_gb = round(psutil.virtual_memory().total / (1024**3))
        self.profile, self.recommended_model = self.detect_hardware()

        # Titolo
        self.title_label = ctk.CTkLabel(self, text="AGENT-TO-WORK: SETUP AUTOMATICO", font=ctk.CTkFont(size=22, weight="bold"))
        self.title_label.pack(pady=15)

        # Tabella Hardware Rilevato
        self.hw_frame = ctk.CTkFrame(self)
        self.hw_frame.pack(pady=10, padx=40, fill="x")
        
        ctk.CTkLabel(self.hw_frame, text=f"💻 Sistema Operativo: {sys.platform.upper()}", font=ctk.CTkFont(size=14)).pack(anchor="w", padx=15, pady=2)
        ctk.CTkLabel(self.hw_frame, text=f"📊 RAM Rilevata: {self.ram_gb} GB", font=ctk.CTkFont(size=14)).pack(anchor="w", padx=15, pady=2)
        ctk.CTkLabel(self.hw_frame, text=f"⚙️ Profilo Assegnato: {self.profile}", font=ctk.CTkFont(size=14, weight="bold")).pack(anchor="w", padx=15, pady=2)
        ctk.CTkLabel(self.hw_frame, text=f"🤖 Modello Consigliato: {self.recommended_model}", font=ctk.CTkFont(size=14)).pack(anchor="w", padx=15, pady=2)

        # Stato Ollama
        self.ollama_frame = ctk.CTkFrame(self)
        self.ollama_frame.pack(pady=10, padx=40, fill="x")
        
        if self.ollama_installed:
            self.status_ollama = ctk.CTkLabel(self.ollama_frame, text="✅ Ollama rilevato sul sistema!", text_color="green", font=ctk.CTkFont(size=13, weight="bold"))
            self.status_ollama.pack(side="left", padx=15, pady=10)
            self.btn_ollama = None
        else:
            self.status_ollama = ctk.CTkLabel(self.ollama_frame, text="❌ Ollama NON trovato. È necessario per far girare l'IA offline.", text_color="orange", font=ctk.CTkFont(size=13))
            self.status_ollama.pack(side="left", padx=15, pady=10)
            self.btn_ollama = ctk.CTkButton(self.ollama_frame, text="Scarica Ollama (Sito Ufficiale)", command=self.open_ollama_web, fg_color="#E06666", hover_color="#CC0000")
            self.btn_ollama.pack(side="right", padx=15, pady=10)

        # Console di Log integrata
        ctk.CTkLabel(self, text="Avanzamento Installazione / Output:", font=ctk.CTkFont(size=12)).pack(anchor="w", padx=40, pady=(10,0))
        self.textbox = ctk.CTkTextbox(self, width=670, height=160)
        self.textbox.pack(pady=5, padx=40)
        self.textbox.configure(state="disabled")

        # Pulsanti di Azione Inferiori
        self.actions_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.actions_frame.pack(pady=15, fill="x", padx=40)

        self.install_btn = ctk.CTkButton(self.actions_frame, text="1. Installa Ambiente e Modelli", command=self.start_install_thread, fg_color="#3D85C6")
        self.install_btn.pack(side="left", expand=True, fill="x", padx=5)

        self.start_btn = ctk.CTkButton(self.actions_frame, text="2. Avvia Jarvis Agente", command=self.start_agent_thread, fg_color="green", state="disabled")
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
        self.log("[ℹ️] Ho aperto la pagina di download di Ollama nel browser. Installalo e riavvia questa applicazione.")

    def log(self, message):
        self.textbox.configure(state="normal")
        self.textbox.insert("end", message + "\n")
        self.textbox.configure(state="disabled")
        self.textbox.yview("end")

    def start_install_thread(self):
        self.install_btn.configure(state="disabled")
        threading.Thread(target=self.run_installation, daemon=True).start()

    def run_installation(self):
        self.log("[-] Avvio installazione dei componenti Python richiesti...")
        try:
            # Aggiorna pip e installa requirements
            subprocess.run([sys.executable, "-m", "pip", "install", "--upgrade", "pip"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            if os.path.exists("requirements.txt"):
                subprocess.run([sys.executable, "-m", "pip", "install", "-r", "requirements.txt"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
            
            self.log("[✅] Dipendenze Python installate con successo.")
            
            # Esecuzione di install.py per legare l'hardware
            if os.path.exists("install.py"):
                self.log("[-] Configurazione hardware in corso (Esecuzione di install.py)...")
                env = os.environ.copy()
                env["OLLAMA_HOST"] = "127.0.0.1:11434"
                
                # Avvia Ollama se installato e spento (tentativo automatico)
                if self.ollama_installed:
                    self.log("[-] Tentativo di sincronizzazione con Ollama...")
                    subprocess.Popen(["ollama", "serve"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=env, creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0)
                
                process = subprocess.Popen([sys.executable, "install.py"], stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True, env=env)
                for line in iter(process.stdout.readline, ''):
                    self.log(line.strip())
                process.wait()
                
            self.log("[🎉] Setup terminato! Ora puoi avviare l'agente locale.")
            self.start_btn.configure(state="normal")
        except Exception as e:
            self.log(f"[❌] Errore durante l'installazione: {str(e)}")
            self.install_btn.configure(state="normal")

    def start_agent_thread(self):
        self.start_btn.configure(state="disabled")
        threading.Thread(target=self.run_agent, daemon=True).start()

    def run_agent(self):
        self.log("[🚀] Avvio di Jarvis in corso...")
        if not os.path.exists("jarvis.py"):
            self.log("[❌] Errore: Impossibile trovare jarvis.py")
            self.start_btn.configure(state="normal")
            return
            
        env = os.environ.copy()
        env["OLLAMA_HOST"] = "127.0.0.1:11434"
        
        try:
            process = subprocess.Popen(
                [sys.executable, "jarvis.py"],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                env=env,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            )
            for line in iter(process.stdout.readline, ''):
                self.log(line.strip())
            process.wait()
        except Exception as e:
            self.log(f"[❌] Errore esecuzione Agente: {str(e)}")
        self.start_btn.configure(state="normal")

if __name__ == "__main__":
    app = AgentInstallerGUI()
    app.mainloop()
