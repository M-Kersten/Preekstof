@echo off
setlocal enabledelayedexpansion
title Preekstof
cd /d "%~dp0"

rem --- 0. Started from inside the zip --------------------------------------------
rem Windows lets you double-click a file inside a zip without unpacking it, and then
rem runs it from a temporary folder where the rest of the app is not.
if not exist "%~dp0launcher.py" (
    echo.
    echo Preekstof moet eerst uitgepakt worden.
    echo Klik met de rechtermuisknop op de zip, kies "Alles uitpakken" en open
    echo start.bat in de map die dan verschijnt.
    echo.
    pause
    exit /b 1
)

rem --- 1. A version the app downloaded itself goes in place first ---------------
rem cmd reads this file while it runs, so it cannot replace itself. A copy of the update
rem script in TEMP does the work and starts the new start.bat when it is done.
rem Your own work is in %USERPROFILE%\Preekstof and is not touched by this.
if exist ".update\ready" if exist ".update\new\tools\apply-update.bat" goto :update

rem --- 2. The Python that came with the download needs nothing else -------------
if exist "python\python.exe" (
    set "RUN=python\python.exe"
    goto :run
)

rem --- 3. Otherwise find a Python 3.10+ on this machine ---------------------------
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
    if not defined PY goto :restartwindow
    echo Python is geinstalleerd. De app gaat gewoon verder.
)

if not exist ".venv\Scripts\python.exe" (
    echo De app wordt voor het eerst klaargezet, dit duurt een paar minuten ...
    %PY% -m venv .venv || goto :fail
    ".venv\Scripts\python.exe" -m pip install --upgrade pip >nul 2>&1
)
set "RUN=.venv\Scripts\python.exe"

rem --- 4. Start (installs/updates packages and FFmpeg when needed, opens the browser) ---
:run
"%RUN%" launcher.py %*
set "STATUS=%errorlevel%"
if "%STATUS%"=="75" goto :again
if not "%STATUS%"=="0" goto :fail
exit /b 0

:again
rem The app asked to start again, with a new version ready. Starting this file anew, rather
rem than jumping back up, makes cmd read it from the start.
"%~f0"

:update
copy /y ".update\new\tools\apply-update.bat" "%TEMP%\preekstof-bijwerken.bat" >nul
"%TEMP%\preekstof-bijwerken.bat" "%~dp0."

:nopython
echo.
echo Python kon niet geinstalleerd worden. Haal liever de download voor Windows op:
echo daar zit alles al in. Of haal Python 3.12 op bij
echo https://www.python.org/downloads/windows/ en zet tijdens het installeren
echo een vinkje bij "Add python.exe to PATH". Start daarna start.bat opnieuw.
pause
exit /b 1

:restartwindow
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
