#!/bin/bash

echo "================================================================="
echo "       AGENT-TO-WORK: INSTALLATORE AUTOMATICO PER LINUX"
echo "================================================================="

# Aggiorna l'indice dei pacchetti
echo "[*] Aggiornamento dei repository di sistema..."
sudo apt update -y

# 1. CONTROLLO E INSTALLAZIONE DI GIT
if ! command -v git &> /dev/null; then
    echo "[*] Git non trovato. Installazione in corso..."
    sudo apt install git -y
    echo "[OK] Git installato con successo."
else
    echo "[OK] Git è già presente nel sistema."
fi

# 2. CONTROLLO E INSTALLAZIONE DI PYTHON E PIP
if ! command -v python3 &> /dev/null; then
    echo "[*] Python3 non trovato. Installazione in corso..."
    sudo apt install python3 python3-pip python3-venv -y
    echo "[OK] Python3 installato con successo."
else
    echo "[OK] Python3 è già presente nel sistema."
    # Si assicura che pip sia installato
    sudo apt install python3-pip python3-venv -y &> /dev/null
fi

# 3. CONTROLLO E INSTALLAZIONE DI OLLAMA
if ! command -v ollama &> /dev/null; then
    echo "[*] Ollama non trovato. Download e installazione ufficiale..."
    curl -fsSL https://ollama.com | sh
    echo "[OK] Ollama installato. Avvio del servizio..."
    sudo systemctl enable ollama
    sudo systemctl start ollama
    sleep 5
else
    echo "[OK] Ollama è già presente nel sistema."
fi

# 4. RILEVAMENTO RAM E SCELTA INTELLIGENTE DEL MODELLO AI
echo "[*] Analisi della memoria RAM in corso..."
TOTAL_RAM_KB=$(grep MemTotal /proc/meminfo | awk '{print $2}')
RAM_GB=$((TOTAL_RAM_KB / 1024 / 1024))
echo "[INFO] RAM Totale Rilevata: $RAM_GB GB"

MODELLO="qwen2.5:0.5b-instruct"
if [ $RAM_GB -gt 6 ]; then
    MODELLO="qwen2.5:3b-instruct-q4_K_M"
fi
if [ $RAM_GB -gt 14 ]; then
    MODELLO="qwen2.5:7b-instruct-q4_K_M"
fi
echo "[*] Configurazione hardware adatta per il modello: $MODELLO"

# 5. SCARICAMENTO DEL MODELLO DENTRO OLLAMA
echo "[*] Download del modello AI locale (Potrebbe richiedere tempo)..."
ollama pull $MODELLO

# 6. CLONAZIONE DEL PROGETTO AGENT-TO-WORK
if [ ! -d "agent-to-work" ]; then
    echo "[*] Download dei file sorgenti di Agent-to-Work..."
    git clone https://github.com
    cd agent-to-work || exit
else
    cd agent-to-work || exit
    git pull origin main
fi

# 7. INSTALLAZIONE DIPENDENZE E CONFIGURAZIONE LOCALE
echo "[*] Installazione librerie Python..."
pip3 install -r requirements.txt --upgrade --break-system-packages 2>/dev/null || pip3 install -r requirements.txt --upgrade

echo "[*] Generazione file di configurazione hardware locale..."
python3 install.py

echo "================================================================="
echo "   [CONFIGURAZIONE COMPLETATA] IL PC LINUX ORA È PRONTO!"
echo "   Per avviare Jarvis scrivi: python3 jarvis.py"
echo "================================================================="
