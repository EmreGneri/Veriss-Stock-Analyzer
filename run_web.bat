@echo off
cd /d "%~dp0"
echo Starting Veriss web server at http://127.0.0.1:8000
venv\Scripts\python.exe -m uvicorn web.main:app --host 127.0.0.1 --port 8000
pause
