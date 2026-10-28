@echo off
title Avvio Agent-to-Work
echo [-] Controllo pre-requisiti in corso...

:: Verifica se Python è installato nel sistema
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERRORE] Python non e installato o non e configurato nel PATH.
    echo Per favore scarica Python da python.org e spunta "Add Python to PATH".
    pause
    exit /b
)

echo [-] Verifica e installazione dei moduli grafici di base...
:: Installa le librerie fondamentali sul Python globale per far partire l'interfaccia
python -m pip install --quiet customtkinter psutil

echo [OK] Avvio dell'assistente grafico...
:: Avvia l'interfaccia usando il Python globale (senza aprire la finestra nera di sfondo)
start pythonw gui.py
