#!/bin/bash
# Build Preekstof.app and Preekstof.dmg on a Mac with an Apple chip.
#
#   bash desktop/build-mac.sh
#
# Needs Python 3.12 (python.org, Homebrew or uv) and the command line tools (xcode-select
# --install). No Apple Developer account: the app is signed ad hoc, as PyInstaller does by
# default, and a church opens it once through System Settings (desktop/README.md).
set -euo pipefail
cd "$(dirname "$0")/.."
PY="${PYTHON:-python3.12}"
if [ ! -x desktop/.venv/bin/python ]; then
  "$PY" -m venv desktop/.venv
fi
desktop/.venv/bin/python -m pip install --quiet --upgrade pip
desktop/.venv/bin/python -m pip install --quiet -r backend/requirements.txt -r desktop/requirements.txt
# PyAV stays out of the app (desktop/stubs/av explains why).
desktop/.venv/bin/python -m pip uninstall --yes --quiet av || true
desktop/.venv/bin/python desktop/build.py "$@"
