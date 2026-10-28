@echo off
title installazione Agent-to-Work
echo [1/3] Verifica di Python nel sistema...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERRORE] Python non e installato o non e configurato nel PATH.
    echo Per favore installa Python e spunta la casella "Add Python to PATH".
    pause
    exit /b
)

echo [2/3] Creazione dell'ambiente virtuale (venv)...
python -m venv venv
if %errorlevel% neq 0 (
    echo [ERRORE] Impossibile creare l'ambiente virtuale.
    pause
    exit /b
)

echo [3/3] Installazione delle dipendenze...
call venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install customtkinter

echo [OK] Installazione completata con successo!
echo E stato creato il file 'Avvia_Interfaccia.bat' per avviare l'agente senza terminale.
echo @echo off > Avvia_Interfaccia.bat
echo start venv\Scripts\pythonw.exe gui.py >> Avvia_Interfaccia.bat
pause

