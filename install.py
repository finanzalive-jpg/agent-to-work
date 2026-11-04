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
                        return round(int(line.split()[1]) / (1024 ** 2))
        return 8

def select_model_profile(ram_gb):
    """Seleziona il modello e il contesto ideale in base alla RAM."""
    if ram_gb < 6:
        return {
            "profile": "Basic - Hardware limitato",
            "model": "llama3.2:1b-instruct-q4_K_M",
            "num_ctx": 1024,
            "msg": "Modalita Basic. Solo comandi vocali diretti e veloci."
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
    print(f"\n[!] {profilo['msg']}\n")
    
    if sys.platform.startswith('linux'):
        install_ollama_linux()
    else:
        print("[!] Assicurati che l'applicazione Ollama per Windows sia aperta in background.")
        
    print(f"[-] Download del modello {profilo['model']} (Attendere)...")
    try:
        env = os.environ.copy()
        env["OLLAMA_HOST"] = "127.0.0.1:11434"
        subprocess.run(["ollama", "pull", profilo["model"]], env=env, check=True)
        print("[+] Modello scaricato con successo.")
    except Exception as e:
        print(f"[X] Errore durante il download del modello: {e}")
        
    config_data = {
        "assistant_name": "Atlas",
        "detected_ram_gb": ram,
        "model_in_use": profilo["model"],
        "num_ctx": profilo["num_ctx"],

        # CERVELLO INTERCAMBIABILE
        # provider = "groq"   -> veloce, in cloud (metti la chiave in .env: GROQ_API_KEY=...)
        # provider = "ollama" -> tutto in locale (serve Ollama in esecuzione, nessuna chiave)
        # Per passare al locale domani: cambia solo "provider" in "ollama".
        "brain": {
            "provider": "groq",
            "model": "openai/gpt-oss-20b",
            "base_url": "https://api.groq.com/openai/v1",
            "api_key_env": "GROQ_API_KEY",
            "temperature": 0.1,

            "ollama_model": profilo["model"],
            "ollama_host": "http://127.0.0.1:11434",
            "num_ctx": profilo["num_ctx"],

            # Voce (gratis): Whisper su Groq per ascoltare, Edge-TTS per parlare
            "stt_model": "whisper-large-v3-turbo"
        },

        # Voce parlata (Edge-TTS, gratis). Femminile: it-IT-ElsaNeural
        "voce": "it-IT-DiegoNeural",

        # Citta' per il meteo del notiziario (cambia qui i tuoi valori)
        "meteo": {
            "citta": "Roma",
            "lat": 41.90,
            "lon": 12.50
        }
    }

    # Non sovrascrivere un config.json gia' esistente: l'utente potrebbe aver gia'
    # scelto il provider o cambiato il nome dell'assistente.
    if os.path.exists("config.json"):
        try:
            with open("config.json", "r") as f:
                vecchio = json.load(f)
            vecchio.update({k: v for k, v in config_data.items() if k != "brain"})
            vecchio.setdefault("brain", config_data["brain"])
            config_data = vecchio
            print("[!] config.json esistente aggiornato (provider del cervello invariato).")
        except Exception:
            pass

    with open("config.json", "w") as f:
        json.dump(config_data, f, indent=4)
    print("[+] Configurazione salvata in 'config.json'.")
    print("[i] Cervello impostato su '%s'. Per il cloud ricorda la chiave nel file .env." % config_data["brain"]["provider"])

if __name__ == "__main__":
    main()
