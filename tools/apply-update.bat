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
robocopy "%APP%\.update\new" "%APP%" /E /MOVE /R:3 /W:2 /NFL /NDL /NJH /NJS /NP >nul
if errorlevel 8 (
    echo Bijwerken is niet gelukt. De vorige versie start gewoon.
    del /q "%APP%\.update\ready" >nul 2>&1
) else (
    rmdir /s /q "%APP%\.update" >nul 2>&1
)
"%APP%\start.bat"
