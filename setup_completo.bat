@echo off
title Installazione Agent-to-Work
echo [1/4] Verifica di Python nel sistema...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERRORE] Python non e installato o non e configurato nel PATH.
    pause
    exit /b
)

echo [2/4] Creazione dell'ambiente virtuale (venv)...
python -m venv venv
if %errorlevel% neq 0 (
    echo [ERRORE] Impossibile creare l'ambiente virtuale.
    pause
    exit /b
)

echo [3/4] Installazione delle dipendenze...
call venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install customtkinter

echo [4/4] Configurazione iniziale dell'hardware e del sistema...
python install.py

echo.
echo [OK] Installazione e configurazione completate con successo!
echo @echo off > Avvia_Interfaccia.bat
echo start venv\Scripts\pythonw.exe gui.py >> Avvia_Interfaccia.bat

pause
