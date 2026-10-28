import customtkinter as ctk
import subprocess
import threading
import os
import sys

ctk.set_appearance_mode("System")  
ctk.set_default_color_theme("blue") 

class AgentGUI(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Local AI Agent Orchestrator - Dashboard")
        self.geometry("700x520")

        self.title_label = ctk.CTkLabel(self, text="AGENT-TO-WORK", font=ctk.CTkFont(size=24, weight="bold"))
        self.title_label.pack(pady=20)

        self.status_label = ctk.CTkLabel(self, text="Stato: Agente Spento", text_color="gray", font=ctk.CTkFont(size=14))
        self.status_label.pack(pady=5)

        self.start_button = ctk.CTkButton(self, text="Avvia Agente (Jarvis)", command=self.start_agent_thread, fg_color="green", hover_color="darkgreen")
        self.start_button.pack(pady=15)

        self.log_label = ctk.CTkLabel(self, text="Console Output:")
        self.log_label.pack(anchor="w", padx=40)
        
        self.textbox = ctk.CTkTextbox(self, width=620, height=250)
        self.textbox.pack(pady=10, padx=40)
        self.textbox.configure(state="disabled")

    def log(self, message):
        self.textbox.configure(state="normal")
        self.textbox.insert("end", message + "\n")
        self.textbox.configure(state="disabled")
        self.textbox.yview("end")

    def start_agent_thread(self):
        self.start_button.configure(state="disabled")
        self.status_label.configure(text="Stato: Agente in esecuzione...", text_color="green")
        threading.Thread(target=self.run_agent, daemon=True).start()

    def run_agent(self):
        script_path = "jarvis.py"
        if not os.path.exists(script_path):
            self.log("Errore: Impossibile trovare jarvis.py")
            self.reset_ui()
            return

        python_exe = os.path.join("venv", "Scripts", "python.exe") if os.path.exists("venv") else "python"
        
        try:
            process = subprocess.Popen(
                [python_exe, script_path],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
            )
            for line in iter(process.stdout.readline, ''):
                self.log(line.strip())
            process.stdout.close()
            process.wait()
        except Exception as e:
            self.log(f"Errore: {str(e)}")
        
        self.reset_ui()

    def reset_ui(self):
        self.start_button.configure(state="normal")
        self.status_label.configure(text="Stato: Agente Terminato", text_color="red")

if __name__ == "__main__":
    app = AgentGUI()
    app.mainloop()

