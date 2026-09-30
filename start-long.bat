@echo off
title Nasdaq-Grid Long-Bot
cd /d "%~dp0"
if not exist config-long.json (
  echo config-long.json fehlt. Vorlage config-long.vorlage.json kopieren und ausfuellen.
  pause
  exit /b
)
:loop
call :update
python grid.py config-long.json
echo.
echo [%date% %time%] Bot beendet - Neustart in 10 Sekunden. Fenster zu = Bot aus.
timeout /t 10 /nobreak >nul
goto loop

:update
rem Laedt grid.py und VERSION aus dem Repo; ersetzt nur vollstaendige Downloads, Vorversion bleibt als .prev.
powershell -NoProfile -Command "$ProgressPreference='SilentlyContinue';$b='https://raw.githubusercontent.com/finntraidingview-cmd/nasdaq-grid/main/';foreach($f in @('grid.py','VERSION')){try{Invoke-RestMethod ($b+$f) -OutFile ($f+'.neulong') -TimeoutSec 25}catch{}}"
call :swap grid.py 8000
call :swap VERSION 3
exit /b

:swap
if not exist "%~1.neulong" exit /b
for %%F in ("%~1.neulong") do if %%~zF LSS %~2 (del "%~1.neulong" & exit /b)
if exist "%~1" copy /y "%~1" "%~1.prev" >nul
move /y "%~1.neulong" "%~1" >nul
exit /b
