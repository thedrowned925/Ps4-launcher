@echo off
setlocal
cd /d "%~dp0.."
if not exist ".venv\Scripts\python.exe" (
  echo Creating isolated Python environment...
  py -3 -m venv .venv
  if errorlevel 1 (echo Python 3.11+ required. & pause & exit /b 1)
)
echo Installing/checking PySide6...
".venv\Scripts\python.exe" -m pip install -r apps\pc-manager\requirements-gui.txt
if errorlevel 1 (echo Dependency setup failed. & pause & exit /b 1)
set "PYTHONPATH=%CD%\apps\pc-manager"
".venv\Scripts\python.exe" -m odium_pc.gui
if errorlevel 1 (echo PC Manager failed to start. & pause & exit /b 1)
endlocal
