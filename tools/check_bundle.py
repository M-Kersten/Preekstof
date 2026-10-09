"""Run a download the way a church would, on whatever machine CI hands us.

    python tools/check_bundle.py <the unpacked folder>

Everything goes through the start script a volunteer double-clicks, never through
launcher.py directly: start.bat and start.command are where Windows and the Mac differ, and
they are what nobody on the team ever runs.

  1. The first start, from nothing, with --smoke: the packages are found ready (or fetched,
     for what a download leaves out), FFmpeg is downloaded, the app answers and renders.
  2. An update: a new version waiting in .update is put in place by the start script, the
     Python that came with the download is swapped whole, and when the new version asks to
     start again (exit 75) the start script does so.

A fresh folder in the runner's temp holds the church's own work for the run.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# Stands in for the new version's launcher. Asks for a restart the first time, the way the
# real one does after an update was staged, and reports which Python ran it.
FAKE_LAUNCHER = '''import os, sys
from pathlib import Path
runs = Path(os.environ["PREEKSTOF_DATA"]) / "nieuwe-versie.json"
said = __import__("json").loads(runs.read_text()) if runs.exists() else []
said.append(sys.executable)
runs.write_text(__import__("json").dumps(said))
print(f"[proef] nieuwe versie draait, keer {len(said)}, met {sys.executable}", flush=True)
sys.exit(75 if len(said) == 1 else 0)
'''


def start(app: Path, env: dict, *flags: str) -> int:
    if os.name == "nt":
        command = ["cmd", "/c", str(app / "start.bat"), *flags]
    else:
        command = ["/bin/bash", str(app / "start.command"), *flags]
    print(f"\n=== {' '.join(command)}", flush=True)
    return subprocess.run(command, cwd=app, env=env, stdin=subprocess.DEVNULL, timeout=2400).returncode


def first_start(app: Path, env: dict) -> None:
    status = start(app, env, "--smoke")
    if status != 0:
        raise SystemExit(f"De eerste start met --smoke gaf {status}.")
    bundle = app / "bundle.json"
    if bundle.is_file():
        print("bundle.json:", bundle.read_text(encoding="utf-8").strip())


def update(app: Path, env: dict) -> None:
    with tempfile.TemporaryDirectory() as work:
        new = Path(work) / "new"
        new.mkdir()
        for name in ("start.bat", "start.command", "tools/apply-update.bat"):
            (new / name).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(app / name, new / name)
        (new / "launcher.py").write_text(FAKE_LAUNCHER, encoding="utf-8")
        bundled = (app / "python").is_dir()
        if bundled:
            shutil.copytree(app / "python", new / "python", symlinks=True)
            (new / "python" / "nieuw.txt").write_text("de nieuwe Python", encoding="utf-8")
            (app / "python" / "oud.txt").write_text("hoort na het bijwerken weg te zijn", encoding="utf-8")
        stage = app / ".update"
        shutil.rmtree(stage, ignore_errors=True)
        stage.mkdir()
        shutil.move(str(new), str(stage / "new"))
        (stage / "ready").write_text("99.0.0", encoding="utf-8")

    status = start(app, env)
    trouble = []
    if status != 0:
        trouble.append(f"de start na het bijwerken gaf {status}")
    runs_file = Path(env["PREEKSTOF_DATA"]) / "nieuwe-versie.json"
    runs = json.loads(runs_file.read_text(encoding="utf-8")) if runs_file.is_file() else []
    if len(runs) != 2:
        trouble.append(f"de nieuwe versie draaide {len(runs)} keer, niet twee (bijwerken, dan herstarten)")
    if (app / ".update").exists():
        trouble.append(".update staat er nog")
    if bundled:
        if not (app / "python" / "nieuw.txt").is_file():
            trouble.append("de nieuwe Python staat er niet")
        if (app / "python" / "oud.txt").exists():
            trouble.append("de oude Python is samengevoegd in plaats van vervangen")
        if (app / "python.old").exists():
            trouble.append("python.old is blijven staan")
        if runs and not all(Path(r).resolve().is_relative_to((app / "python").resolve()) for r in runs):
            trouble.append(f"niet de meegeleverde Python gebruikt: {runs}")
    if trouble:
        raise SystemExit("Bijwerken: " + "; ".join(trouble) + ".")
    swapped = " Python in zijn geheel vervangen," if bundled else ""
    print(f"Bijwerken: nieuwe versie neergezet,{swapped} herstart gelukt.", flush=True)


def main() -> int:
    if len(sys.argv) != 2:
        raise SystemExit(__doc__)
    app = Path(sys.argv[1]).resolve()
    if not (app / "launcher.py").is_file():
        raise SystemExit(f"{app} ziet er niet uit als een uitgepakte Preekstof.")
    with tempfile.TemporaryDirectory() as data:
        env = {**os.environ, "PREEKSTOF_DATA": data, "PORT": os.environ.get("PORT", "8137")}
        first_start(app, env)
        update(app, env)
    print("\nDe download doet wat hij moet doen.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
