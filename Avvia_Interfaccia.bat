@echo off
if not exist venv (
    echo [ERRORE] Ambiente virtuale non trovato. Esegui prima 'setup_completo.bat'.
    pause
    exit /b
)
start venv\Scripts\pythonw.exe gui.py
