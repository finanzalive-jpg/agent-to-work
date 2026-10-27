@echo off
SETLOCAL EnableDelayedExpansion
echo =================================================================
echo        AGENT-TO-WORK: INSTALLATORE AUTOMATICO UNIFICATO
echo =================================================================

:: 1. CONTROLLO E INSTALLAZIONE DI GIT
where git >nul 2>nul
if %errorlevel% neq 0 (
    echo [*] Git non trovato. Download e installazione in corso...
    curl -GA -L -o git_installer.exe "https://github.com"
    start /wait "" git_installer.exe /VERYSILENT /NORESTART
    del git_installer.exe
    set "PATH=%PATH%;C:\Program Files\Git\cmd"
)
echo [OK] Git verificato.

:: 2. CONTROLLO E INSTALLAZIONE DI PYTHON
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [*] Python non trovato. Download e installazione in corso...
    curl -L -o python_installer.exe "https://python.org"
    start /wait "" python_installer.exe /quiet InstallAllUsers=1 PrependPath=1
    del python_installer.exe
)
echo [OK] Python verificato.

:: 3. CONTROLLO E INSTALLAZIONE DI OLLAMA
where ollama >nul 2>nul
if %errorlevel% neq 0 (
    echo [*] Ollama non trovato. Download e installazione in corso...
    curl -L -o ollama_installer.exe "https://ollama.com"
    start /wait "" ollama_installer.exe /silent
    del ollama_installer.exe
    start "" "C:\Users\%USERNAME%\AppData\Local\Programs\Ollama\ollama app.exe"
    timeout /t 10 /nobreak >nul
)
echo [OK] Ollama verificato.

:: 4. RILEVAMENTO RAM E SCELTA MODELLO
echo [*] Analisi delle caratteristiche hardware in corso...
for /f "tokens=2 delims==" %%a in ('wmic os get TotalVisibleMemorySize /value') do set "RAM_KB=%%a"
set /a RAM_GB=!RAM_KB! / 1024 / 1024
echo [INFO] RAM Totale Rilevata: !RAM_GB! GB

set "MODELLO=qwen2.5:0.5b-instruct"
if !RAM_GB! GTR 6 set "MODELLO=qwen2.5:3b-instruct-q4_K_M"
if !RAM_GB! GTR 14 set "MODELLO=qwen2.5:7b-instruct-q4_K_M"
echo [*] Modello selezionato: !MODELLO!

:: 5. SCARICAMENTO MODELLO
echo [*] Download del modello AI locale...
ollama pull !MODELLO!

:: 6. CLONAZIONE SEQUENZIALE PULITA (Senza blocchi condizionali complessi)
echo [*] Download dei file sorgenti di Agent-to-Work...
git clone https://github.com

:: Spostamento dentro la cartella del progetto scaricato
cd agent-to-work

:: 7. DIPENDENZE E CONFIGURAZIONE
echo [*] Installazione librerie Python...
pip install -r requirements.txt --upgrade
echo [*] Generazione configurazione locale...
python install.py

echo =================================================================
echo   [CONFIGURAZIONE COMPLETATA] IL PC ORA E PRONTO E INTELLIGENTE!
echo   Per avviare Jarvis scrivi: python jarvis.py
echo =================================================================
pause
