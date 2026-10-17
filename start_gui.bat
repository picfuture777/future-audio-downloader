@echo off
rem Musicdl GUI launcher - double click to start
cd /d "%~dp0"
if not exist "%~dp0.venv\Scripts\pythonw.exe" (
    echo [ERROR] venv not found at %~dp0.venv
    echo Please make sure the environment is set up first.
    pause
    exit /b 1
)
start "" "%~dp0.venv\Scripts\pythonw.exe" "%~dp0musicdl_gui.py"
