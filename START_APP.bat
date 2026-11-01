@echo off
title TechLab Institute Asset Manager
cd /d "%~dp0"

echo ========================================================
echo   TechLab Institute Laptop & Asset Management System
echo ========================================================
echo.
echo Server start ho raha hai...
echo.

set PYTHONPATH=.
start "" http://localhost:8000
python -m uvicorn backend.main:app --port 8000

pause
