@echo off
title Nasdaq-Grid Uebersicht
cd /d "%~dp0"
start "" http://localhost:8790
python dashboard.py
pause
