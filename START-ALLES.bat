@echo off
title Nasdaq-Grid starten
cd /d "%~dp0"
rem Startet Long-Bot, Short-Bot und Uebersicht in je eigenem Fenster. Die MT5-Terminals
rem startet der Bot selbst, falls sie noch zu sind (initialize mit dem Terminal-Pfad).
if not exist config-long.json goto fehlt
if not exist config-short.json goto fehlt
start "Nasdaq-Grid Long-Bot" cmd /k start-long.bat
timeout /t 3 /nobreak >nul
start "Nasdaq-Grid Short-Bot" cmd /k start-short.bat
timeout /t 3 /nobreak >nul
start "Nasdaq-Grid Uebersicht" cmd /k start-dashboard.bat
exit /b
:fehlt
echo Noch nicht eingerichtet - zuerst einrichten.bat starten.
pause
