@echo off
title Nasdaq-Grid Short-Bot
cd /d "%~dp0"
if not exist config-short.json (
  echo config-short.json fehlt. Zuerst einrichten.bat starten.
  pause
  exit /b
)
:loop
if exist update.py python update.py
python grid.py config-short.json
echo.
echo [%date% %time%] Bot beendet - Neustart in 10 Sekunden. Fenster zu = Bot aus.
timeout /t 10 /nobreak >nul
goto loop
