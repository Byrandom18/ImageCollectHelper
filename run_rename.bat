@echo off
setlocal EnableExtensions
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
cd /d "%~dp0"

set "PY="
py -3 -c "import sys" >nul 2>&1 && set "PY=py -3"
if not defined PY python -c "import sys" >nul 2>&1 && set "PY=python"
if not defined PY (
    echo Python 3 не найден. Установите с https://www.python.org/downloads/ и отметьте Add python.exe to PATH.
    pause
    exit /b 1
)

if not exist ".venv\Scripts\python.exe" (
    echo Сначала один раз запустите run.bat, чтобы поставить зависимости.
    pause
    exit /b 1
)

call ".venv\Scripts\activate.bat"
python -m renamer
if errorlevel 1 pause
