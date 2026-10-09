@echo off
setlocal
rem Puts a version Preekstof downloaded itself in place, then starts it.
rem
rem Run from a copy in TEMP by start.bat, because cmd cannot replace the batch file it is
rem reading. %1 is the app folder. Your own work lives in %USERPROFILE%\Preekstof and is
rem not in here, so nothing of it can be overwritten.
set "APP=%~1"
title Preekstof wordt bijgewerkt
echo De nieuwe versie van Preekstof wordt neergezet ...

rem The Python that came with the download is swapped whole, never merged: the packages of
rem two versions side by side in one folder is a Python nobody can predict. The old one waits
rem beside it until the new one is in, and goes back when that fails.
set "SWAPPED="
if exist "%APP%\.update\new\python\" if exist "%APP%\python\" (
    rmdir /s /q "%APP%\python.old" >nul 2>&1
    move "%APP%\python" "%APP%\python.old" >nul 2>&1 && set "SWAPPED=1"
)

robocopy "%APP%\.update\new" "%APP%" /E /MOVE /R:3 /W:2 /NFL /NDL /NJH /NJS /NP >nul
if errorlevel 8 (
    echo Bijwerken is niet gelukt. De vorige versie start gewoon.
    if defined SWAPPED (
        rmdir /s /q "%APP%\python" >nul 2>&1
        move "%APP%\python.old" "%APP%\python" >nul 2>&1
    )
    del /q "%APP%\.update\ready" >nul 2>&1
) else (
    if defined SWAPPED rmdir /s /q "%APP%\python.old" >nul 2>&1
    rmdir /s /q "%APP%\.update" >nul 2>&1
)
"%APP%\start.bat"
