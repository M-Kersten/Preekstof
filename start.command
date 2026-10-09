#!/bin/bash
# Preekstof voor de Mac: dubbelklik dit bestand.
#
# Alles staat in functies die pas op de laatste regel worden aangeroepen. bash leest een
# script terwijl het loopt; een update die dit bestand vervangt zou het anders halverwege
# veranderen. Zo heeft bash het hele bestand al gelezen voordat er iets gebeurt.

fail() {
  echo
  echo "Er ging iets mis. Lees de meldingen hierboven en druk dan op Enter om te sluiten."
  read -r
  exit 1
}

apply_update() {
  # Een versie die de app zelf heeft opgehaald, gaat op zijn plek voordat er iets start.
  # Je eigen werk staat in ~/Preekstof en wordt hier niet aangeraakt.
  echo "De nieuwe versie van Preekstof wordt neergezet ..."
  if cp -R .update/new/. ./ ; then
    rm -rf .update
  else
    echo "Bijwerken is niet gelukt. De vorige versie start gewoon."
    rm -f .update/ready
  fi
  exec /bin/bash "$APP/start.command"
}

find_python() {
  for candidate in python3.13 python3.12 python3.11 python3.10 python3; do
    if command -v "$candidate" >/dev/null 2>&1 && "$candidate" -c 'import sys; sys.exit(0 if sys.version_info >= (3,10) else 1)' >/dev/null 2>&1; then
      echo "$candidate"
      return
    fi
  done
}

main() {
  APP="$(cd "$(dirname "$0")" && pwd)" || exit 1
  cd "$APP" || exit 1

  if [ -f ".update/ready" ] && [ -d ".update/new" ]; then
    apply_update
  fi

  # macOS markeert alles wat uit een gedownloade zip komt. Dit bestand mocht je al openen;
  # de rest van de app (Python, de onderdelen) moet daarna ook mogen draaien.
  if xattr -p com.apple.quarantine "$APP/launcher.py" >/dev/null 2>&1; then
    xattr -dr com.apple.quarantine "$APP" 2>/dev/null
  fi

  if [ -x "python/bin/python3" ]; then
    # De download voor de Mac heeft zijn eigen Python, met alles erin.
    RUN="python/bin/python3"
  else
    PY="$(find_python)"
    if [ -z "$PY" ]; then
      if command -v brew >/dev/null 2>&1; then
        echo "Python is niet gevonden. Het wordt nu geïnstalleerd met Homebrew ..."
        brew install python || fail
        PY="python3"
      else
        echo "Python 3.10 of nieuwer is niet gevonden."
        echo "Haal liever de download voor de Mac op: daar zit alles al in."
        echo "Of installeer Python via https://www.python.org/downloads/macos/ en start dit opnieuw."
        fail
      fi
    fi
    if [ ! -x ".venv/bin/python" ]; then
      echo "De app wordt voor het eerst klaargezet, dit duurt een paar minuten ..."
      "$PY" -m venv .venv || fail
      .venv/bin/python -m pip install --upgrade pip >/dev/null 2>&1
    fi
    RUN=".venv/bin/python"
  fi

  "$RUN" launcher.py "$@"
  status=$?
  if [ "$status" -eq 75 ]; then
    # De app vroeg om opnieuw te starten, met een nieuwe versie klaar.
    exec /bin/bash "$APP/start.command"
  fi
  if [ "$status" -ne 0 ]; then
    fail
  fi
}

main "$@"; exit $?
