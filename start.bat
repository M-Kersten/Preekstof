@echo off
setlocal enabledelayedexpansion
title Preekstof
cd /d "%~dp0"

rem --- 1. A Python that came with the download needs nothing else -----------------
rem It has no venv module and does not need one: the launcher installs the packages into
rem it on the first run, the same way it would into a virtual environment.
if exist "python\python.exe" (
    "python\python.exe" launcher.py
    if errorlevel 1 goto :fail
    exit /b 0
)

rem --- 2. Otherwise find a Python 3.10+ on this machine ---------------------------
set "PY="
py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1 && set "PY=py -3"
if not defined PY python -c "import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)" >nul 2>&1 && set "PY=python"

if not defined PY (
    echo Python is niet gevonden. Even installeren, dit duurt een paar minuten ...
    winget install -e --id Python.Python.3.12 --accept-source-agreements --accept-package-agreements
    if errorlevel 1 goto :nopython

    rem winget does not refresh this window's PATH, and asking the user to close it and
    rem start again is where a willing church stops. So look where it just landed.
    for %%D in (
        "%LOCALAPPDATA%\Programs\Python\Python313\python.exe"
        "%LOCALAPPDATA%\Programs\Python\Python312\python.exe"
        "%LOCALAPPDATA%\Programs\Python\Python311\python.exe"
        "%ProgramFiles%\Python313\python.exe"
        "%ProgramFiles%\Python312\python.exe"
        "%ProgramFiles%\Python311\python.exe"
    ) do (
        if not defined PY if exist %%D set "PY=%%~D"
    )
    if not defined PY py -3 -c "import sys" >nul 2>&1 && set "PY=py -3"
    if not defined PY goto :restart
    echo Python is geinstalleerd. De app gaat gewoon verder.
)

rem --- 3. Create the Python environment on first run ----------------------------
if not exist ".venv\Scripts\python.exe" (
    echo De app wordt voor het eerst klaargezet, dit duurt een paar minuten ...
    %PY% -m venv .venv || goto :fail
    ".venv\Scripts\python.exe" -m pip install --upgrade pip >nul
)

rem --- 4. Start (installs/updates packages and FFmpeg when needed, opens the browser) ---
".venv\Scripts\python.exe" launcher.py
if errorlevel 1 goto :fail
exit /b 0

:nopython
echo.
echo Python kon niet geinstalleerd worden. Haal Python 3.12 op bij
echo https://www.python.org/downloads/windows/ en zet tijdens het installeren
echo een vinkje bij "Add python.exe to PATH". Start daarna start.bat opnieuw.
pause
exit /b 1

:restart
echo.
echo Python is geinstalleerd, maar dit venster ziet hem nog niet.
echo Sluit dit venster en klik start.bat nog een keer aan.
pause
exit /b 0

:fail
echo.
echo Er ging iets mis. Lees de meldingen hierboven en druk dan op een toets.
pause >nul
exit /b 1
