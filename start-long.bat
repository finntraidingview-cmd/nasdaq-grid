@echo off
title Nasdaq-Grid Long-Bot
cd /d "%~dp0"
if not exist config-long.json (
  echo config-long.json fehlt. Zuerst einrichten.bat starten.
  pause
  exit /b
)
:loop
if exist update.py python update.py
python grid.py config-long.json
echo.
echo [%date% %time%] Bot beendet - Neustart in 10 Sekunden. Fenster zu = Bot aus.
timeout /t 10 /nobreak >nul
goto loop
