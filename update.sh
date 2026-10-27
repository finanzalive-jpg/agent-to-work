#!/bin/bash
echo "=== SESSIONE UPDATE: Aggiornamento Skill da Git... ==="
git pull origin main
echo "=== AGGIORNAMENTO DIPENDENZE PIP ==="
pip install -r requirements.txt --upgrade
echo "=== UPDATE COMPLETATO CON SUCCESSO! ==="
