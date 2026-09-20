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

for /f "delims=" %%A in ('%PY% -c "from collector.proxy import resolve_proxy; print(resolve_proxy().url)"') do set "LOCAL_PROXY=%%A"
if defined LOCAL_PROXY (
    set "HTTP_PROXY=%LOCAL_PROXY%"
    set "HTTPS_PROXY=%LOCAL_PROXY%"
    echo Локальный прокси: %LOCAL_PROXY%
)

if not exist ".venv\Scripts\python.exe" (
    echo Создаю виртуальное окружение...
    %PY% -m venv .venv
    if errorlevel 1 (
        echo Не удалось создать .venv
        pause
        exit /b 1
    )
)

call ".venv\Scripts\activate.bat"
python -m pip install --upgrade pip >nul
python -m pip install -r requirements.txt
if errorlevel 1 (
    echo Не удалось установить зависимости.
    pause
    exit /b 1
)

python -m collector
if errorlevel 1 pause
