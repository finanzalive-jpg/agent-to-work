import os
import sys
import json
import subprocess
import shutil

def get_total_ram():
    """Rileva la RAM totale del sistema in GB."""
    try:
        import psutil
        return round(psutil.virtual_memory().total / (1024 ** 3))
    except ImportError:
        if sys.platform.startswith('linux'):
            with open('/proc/meminfo', 'r') as f:
                for line in f:
                    if 'MemTotal' in line:
                        return round(int(line.split()) / (1024 ** 2))
        return 8

def select_model_profile(ram_gb):
    """Seleziona il modello e il contesto ideale in base alla RAM."""
    if ram_gb < 6:
        return {
            "profile": "Basic - Hardware limitato",
            "model": "llama3.2:1b-instruct-q4_K_M",
            "num_ctx": 1024,
            "msg": "Modalità Basic. Solo comandi vocali diretti e veloci."
        }
    elif 6 <= ram_gb < 12:
        return {
            "profile": "Medium - Configurazione Bilanciata",
            "model": "qwen2.5:3b-instruct-q4_K_M",
            "num_ctx": 2048,
            "msg": "Rilevati 8GB di RAM. Configurazione ideale per il tuo PC attuale."
        }
    elif 12 <= ram_gb < 24:
        return {
            "profile": "Advanced - Ottimale",
            "model": "qwen2.5:7b-instruct-q4_K_M",
            "num_ctx": 2048,
            "msg": "Hardware eccellente. Tutte le skill avanzate attive."
        }
    else:
        return {
            "profile": "Ultra - Jarvis Full",
            "model": "qwen2.5:14b-instruct-q4_K_M",
            "num_ctx": 4096,
            "msg": "Potenza massima attiva. Ragionamento profondo offline."
        }

def install_ollama_linux():
    """Verifica e installa Ollama se su Linux."""
    if shutil.which("ollama") is None:
        print("[-] Ollama non trovato. Installazione in corso...")
        try:
            subprocess.run("curl -fsSL https://ollama.com | sh", shell=True, check=True)
        except subprocess.CalledProcessError:
            print("[X] Errore installazione Ollama. Fallo manualmente da ollama.com")
            sys.exit(1)

def main():
    print("="*60)
    print("      AGENT-TO-WORK: CONFIGURATORE HARDWARE ADATTIVO      ")
    print("="*60)
    
    ram = get_total_ram()
    print(f"[*] Sistema operativo: {sys.platform.upper()}")
    print(f"[*] RAM Rilevata: {ram} GB")
    
    profilo = select_model_profile(ram)
    print(f"[+] Profilo Assegnato: {profilo['profile']}")
    print(f"[*] Modello IA Scelto: {profilo['model']}")
    print(f"\n👉 {profilo['msg']}\n")
    
    if sys.platform.startswith('linux'):
        install_ollama_linux()
    else:
        print("[!] Assicurati che l'applicazione Ollama per Windows sia aperta in background.")
        
    print(f"[-] Download del modello {profilo['model']} (Attendere)...")
    try:
        subprocess.run(["ollama", "pull", profilo["model"]], check=True)
        print("[+] Modello scaricato con successo.")
    except Exception as e:
        print(f"[X] Errore durante il download del modello: {e}")
        
    config_data = {
        "assistant_name": "Sara",
        "detected_ram_gb": ram,
        "model_in_use": profilo["model"],
        "num_ctx": profilo["num_ctx"]
    }
    
    with open("config.json", "w") as f:
        json.dump(config_data, f, indent=4)
    print("[+] Configurazione salvata in 'config.json'.")

if __name__ == "__main__":
    main()
