@echo off
title Avvio Agent-to-Work
echo [-] Controllo pre-requisiti in corso...
python --version >nul 2>&1
if %errorlevel% neq 0 (
    echo [ERRORE] Python non installato. Per favore installalo e spunta "Add Python to PATH".
    pause
    exit /b
)
:: Installa customtkinter se manca per permettere alla GUI di partire al primo colpo
pip install customtkinter psutil >nul 2>&1
echo [OK] Avvio dell'assistente grafico...
start venv\Scripts\pythonw.exe gui.py 2>nul || start pythonw.exe gui.py
