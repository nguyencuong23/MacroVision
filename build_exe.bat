@echo off
setlocal
cd /d "%~dp0"
echo === Macro Vision: build Windows EXE ===
where py >nul 2>nul
if errorlevel 1 (
  echo Python Launcher not found. Install Python 3.12 from python.org and run this file again.
  pause
  exit /b 1
)
py -3.12 --version >nul 2>nul
if errorlevel 1 (
  echo Python 3.12 not found. Install Python 3.12 from python.org and try again.
  pause
  exit /b 1
)
if not exist ".venv\Scripts\python.exe" (
  py -3.12 -m venv .venv
  if errorlevel 1 goto error
)
".venv\Scripts\python.exe" -m pip install -r requirements.txt pyinstaller
if errorlevel 1 goto error
".venv\Scripts\python.exe" -m PyInstaller --noconfirm --clean --onefile --windowed --uac-admin --icon icon.ico --add-data "icon.ico;." --name MacroVision app.py
if errorlevel 1 goto error
echo.
echo Build complete: %CD%\dist\MacroVision.exe
echo You can copy this EXE to another Windows computer.
pause
exit /b 0
:error
echo.
echo Build failed. Read the error messages above.
pause
exit /b 1
