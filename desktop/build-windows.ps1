# Build Preekstof.exe and Preekstof-Setup.exe on Windows (x64).
#
#   powershell -ExecutionPolicy Bypass -File desktop\build-windows.ps1
#
# Needs Python 3.12 from python.org (the py launcher) and, for the installer, Inno Setup 6
# (https://jrsoftware.org/isinfo.php, or: winget install JRSoftware.InnoSetup). No code
# signing certificate: Windows SmartScreen asks once, see desktop\README.md.
$ErrorActionPreference = "Stop"
Set-Location (Join-Path $PSScriptRoot "..")
$venv = "desktop\.venv\Scripts\python.exe"
if (-not (Test-Path $venv)) { py -3.12 -m venv desktop\.venv }
& $venv -m pip install --quiet --upgrade pip
& $venv -m pip install --quiet -r backend\requirements.txt -r desktop\requirements.txt
# PyAV stays out of the app (desktop\stubs\av explains why).
& $venv -m pip uninstall --yes --quiet av
& $venv desktop\build.py @args
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
