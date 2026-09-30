@echo off
title Nasdaq-Grid Uebersicht
cd /d "%~dp0"
start "" http://localhost:8790
:loop
if exist update.py python update.py
python dashboard.py
echo [%date% %time%] Uebersicht beendet - Neustart in 3 Sekunden. Fenster zu = Uebersicht aus.
timeout /t 3 /nobreak >nul
goto loop
