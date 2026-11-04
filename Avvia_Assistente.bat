@echo off
cd /d "%~dp0"
python assistente_gui.py
if errorlevel 1 pause
