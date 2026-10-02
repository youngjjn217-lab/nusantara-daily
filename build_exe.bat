@echo off
setlocal
cd /d "%~dp0"
python -m pip install -r requirements.txt
if errorlevel 1 goto :error
python -m pip install -r requirements-desktop.txt
if errorlevel 1 goto :error
python -m PyInstaller --noconfirm --clean --onefile --windowed ^
  --name "NusantaraDaily" ^
  --add-data "static;static" ^
  --collect-all webview ^
  --collect-all yfinance ^
  app_desktop.py
if errorlevel 1 goto :error
if exist config.json copy /y config.json dist\config.json >nul
echo.
echo Build complete: dist\NusantaraDaily.exe
pause
exit /b 0
:error
echo.
echo Build failed. Check the message above.
pause
exit /b 1
