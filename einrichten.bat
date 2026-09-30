@echo off
title Nasdaq-Grid einrichten
cd /d "%~dp0"
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
python einrichten.py
echo.
pause
