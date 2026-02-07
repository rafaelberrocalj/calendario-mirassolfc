#!/bin/bash
# Atualizar calendário do Mirassol FC

python scraper.py

if ! git diff --quiet mirassol_futebol_clube.ics; then
    git add mirassol_futebol_clube.ics
    git commit -m "Update Mirassol FC calendar"
fi
