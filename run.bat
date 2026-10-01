@echo off
setlocal
cd /d "%~dp0"
python -c "import fastapi, uvicorn, requests, yfinance" >nul 2>&1
if errorlevel 1 (
  echo Required packages are being installed...
  python -m pip install -r requirements.txt
  if errorlevel 1 goto :error
)
python server.py
exit /b %errorlevel%
:error
echo Installation failed. Check your Python and network connection.
pause
exit /b 1
