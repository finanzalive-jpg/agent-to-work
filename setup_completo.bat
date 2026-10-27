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
    echo [OK] Git installato con successo.
) else (
    echo [OK] Git gia presente nel sistema.
)

:: 2. CONTROLLO E INSTALLAZIONE DI PYTHON
where python >nul 2>nul
if %errorlevel% neq 0 (
    echo [*] Python non trovato. Download e installazione in corso...
    curl -L -o python_installer.exe "https://python.org"
    start /wait "" python_installer.exe /quiet InstallAllUsers=1 PrependPath=1
    del python_installer.exe
    echo [OK] Python installato con successo.
) else (
    echo [OK] Python gia presente nel sistema.
)

:: 3. CONTROLLO E INSTALLAZIONE DI OLLAMA
where ollama >nul 2>nul
if %errorlevel% neq 0 (
    echo [*] Ollama non trovato. Download e installazione in corso...
    curl -L -o ollama_installer.exe "https://ollama.com"
    start /wait "" ollama_installer.exe /silent
    del ollama_installer.exe
    echo [OK] Ollama installato. Avvio del servizio in corso...
    start "" "C:\Users\%USERNAME%\AppData\Local\Programs\Ollama\ollama app.exe"
    timeout /t 10 /nobreak >nul
) else (
    echo [OK] Ollama gia presente nel sistema.
)

:: 4. RILEVAMENTO RAM E SCELTA INTELLIGENTE DEL MODELLO AI
echo [*] Analisi delle caratteristiche hardware in corso...
for /f "tokens=2 delims==" %%a in ('wmic os get TotalVisibleMemorySize /value') do set "RAM_KB=%%a"
set /a RAM_GB=!RAM_KB! / 1024 / 1024
echo [INFO] RAM Totale Rilevata: !RAM_GB! GB

set "MODELLO=qwen2.5:0.5b-instruct"
if !RAM_GB! GTR 6 (
    set "MODELLO=qwen2.5:3b-instruct-q4_K_M"
)
if !RAM_GB! GTR 14 (
    set "MODELLO=qwen2.5:7b-instruct-q4_K_M"
)
echo [*] Configurazione hardware adatta per il modello: !MODELLO!

:: 5. SCARICAMENTO DEL MODELLO DENTRO OLLAMA
echo [*] Download del modello AI locale (Potrebbe richiedere tempo)...
ollama pull !MODELLO!

:: 6. CLONAZIONE DEL PROGETTO SENZA PARENTESI COMPLESSE (RISOLUZIONE BUG)
if exist "agent-to-work" goto aggiorna_repo

echo [*] Download dei file sorgenti di Agent-to-Work...
git clone https://github.com
cd agent-to-work
goto avvia_config

:aggiorna_repo
echo [*] Cartella esistente. Verifica aggiornamenti in corso...
cd agent-to-work
git pull origin main

:avvia_config
:: 7. INSTALLAZIONE DIPENDENZE E CONFIGURAZIONE LOCALE
echo [*] Installazione librerie Python...
pip install -r requirements.txt --upgrade
echo [*] Generazione file di configurazione hardware locale...
python install.py

echo =================================================================
echo   [CONFIGURAZIONE COMPLETATA] IL PC ORA E PRONTO E INTELLIGENTE!
echo   Per avviare Jarvis scrivi: python jarvis.py
echo =================================================================
pause
