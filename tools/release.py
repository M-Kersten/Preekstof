"""Build the zips a church downloads, out of what git already tracks.

Nobody at a pilot church is going to install git. So a release is one file they unpack
wherever they like and double-click, holding exactly what `git clone` would have given
them: the code, the fonts, the face model, start.bat and start.command.

    .venv/bin/python -m tools.release
    .venv/bin/python -m tools.release --out dist --version 0.9.1

That is the plain zip, which asks the machine for a Python of its own. The downloads per
computer also carry a Python with the packages already installed, so the first start has
nothing to install (the release workflow builds them on a Windows and a Mac runner):

    python -m tools.release --bundle windows-x64 --python python
    python -m tools.release --bundle mac-arm64 --python python

What is deliberately not in any of them: everything the app fetches on the machine that
runs it. FFmpeg, the speech models and the person model are downloaded on first use, which
keeps the zips small and keeps the GPL-built FFmpeg and the AGPL-licensed person model out of
anything that gets handed on. PyAV goes the same way, for the same reason: its wheel carries
an FFmpeg built with x264 and x265. The bundle notes its version in bundle.json and the
launcher fetches exactly that one on the first start (see NOTICE).
"""

import argparse
import json
import os
import shutil
import stat
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend import version  # noqa: E402
from backend.updates import BUNDLES  # noqa: E402

# Kept out of the zip even though git tracks them: nothing a church runs needs them, and
# every megabyte is a download somebody is waiting on.
LEAVE_OUT = ("docs/", "evaluation/", "tests/", ".github/", "site/", "tools/evaluate.py",
             "tools/speechbench.py", "tools/release.py", "tools/check_bundle.py",
             ".gitignore", ".gitattributes")

# Installed with the rest while the bundle is prepared, and taken out again before it is
# zipped. Each is fetched on the church's own computer at the first start instead.
FETCHED_THERE = ("av",)


def tracked() -> list[str]:
    """What git has, which is the only honest definition of what a clone would give."""
    said = subprocess.run(["git", "-C", str(ROOT), "ls-files"],
                          capture_output=True, text=True, check=True)
    return [line for line in said.stdout.splitlines() if line.strip()]


def wanted(paths: list[str]) -> list[str]:
    return [p for p in paths if not p.startswith(LEAVE_OUT) and p not in LEAVE_OUT]


# Every file in the zip gets the same date, and the built interface gets a later one.
# The launcher rebuilds the interface when its source looks newer than the build, and on a
# machine with no Node that ends in a warning nobody can act on. Whatever the working tree's
# timestamps happen to say, in the zip the build is always the younger of the two.
STAMPED = (1980, 1, 1, 0, 0, 0)
BUILT = (1980, 1, 2, 0, 0, 0)
IS_BUILD = "frontend/dist/"


def entry(name: str, date: tuple, runnable: bool) -> zipfile.ZipInfo:
    made = zipfile.ZipInfo(name)
    made.date_time = date
    made.compress_type = zipfile.ZIP_DEFLATED
    # The whole Unix mode, file type included, the way Info-ZIP writes it. With the rights
    # alone, ditto (which is what a double-click on a Mac uses) drops them, and start.command
    # and the Python both come out unrunnable.
    made.create_system = 3
    made.external_attr = (stat.S_IFREG | (0o755 if runnable else 0o644)) << 16
    return made


def build(out: Path, number: str, python: Path | None = None, bundle: str | None = None,
          fetch: dict[str, str] | None = None) -> Path:
    """Write the zip and hand back where it landed.

    `python` is a prepared Python, which goes in as `python/`. start.bat and start.command
    run that one straight away when it is there, so a computer with no Python of its own
    gets through the first double-click without a second one. `bundle` says which computer
    it is for: it names the file the way the download page and the update button look for
    it, and goes in as bundle.json together with what was left out to `fetch` there.
    Leaving both out gives the ordinary zip, which works everywhere and asks the machine
    for its own Python.
    """
    out.mkdir(parents=True, exist_ok=True)
    if bundle:
        target = out / BUNDLES[bundle]
        inside = "Preekstof"
    else:
        target = out / (f"preekstof-{number}-windows.zip" if python else f"preekstof-{number}.zip")
        inside = f"preekstof-{number}"
    files = wanted(tracked())
    if not files:
        raise SystemExit("git ls-files gaf niets terug; draait dit wel in de repository?")
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for name in files:
            source = ROOT / name
            if not source.is_file():
                continue  # a submodule or a link git knows about and the disk does not
            zip_file.writestr(entry(f"{inside}/{name}", BUILT if name.startswith(IS_BUILD) else STAMPED,
                                    name.endswith((".sh", ".command"))), source.read_bytes())
        if python:
            # Links are followed and written as the file they point at: the update unpacks
            # with zipfile, which has no idea what a link is.
            for found in sorted(python.rglob("*")):
                if not found.is_file():
                    continue
                name = f"{inside}/python/{found.relative_to(python).as_posix()}"
                zip_file.writestr(entry(name, STAMPED, True), found.read_bytes())
        if bundle:
            said = {"kind": bundle, "version": number, "fetch": dict(sorted((fetch or {}).items()))}
            zip_file.writestr(entry(f"{inside}/bundle.json", STAMPED, False),
                              json.dumps(said, indent=2) + "\n")
    return target


def interpreter(python: Path) -> Path:
    """The program inside a prepared Python folder, on Windows or on a Mac."""
    for candidate in (python / "python.exe", python / "bin" / "python3"):
        if candidate.is_file():
            return candidate
    raise SystemExit(f"{python} ziet er niet uit als een Python: geen python.exe of bin/python3.")


def prepare(python: Path) -> dict[str, str]:
    """Install everything into the Python that goes in the bundle, then take out again what
    a church fetches itself. Hands back those, with the version that was installed.

    The launcher does the installing, the same way it does on a church's computer, so the
    stamp it leaves in the Python folder tells the first start there is nothing left to do.
    """
    program = interpreter(python)
    with tempfile.TemporaryDirectory() as data:
        env = {**os.environ, "PREEKSTOF_DATA": data}
        subprocess.run([str(program), str(ROOT / "launcher.py"), "--prepare"], cwd=ROOT, env=env,
                       stdin=subprocess.DEVNULL, check=True)
    fetch = {}
    for package in FETCHED_THERE:
        said = subprocess.run([str(program), "-c", "import importlib.metadata as m, sys; "
                               f"print(m.version({package!r}))"], capture_output=True, text=True)
        if said.returncode != 0:
            continue  # not pulled in by anything this time
        fetch[package] = said.stdout.strip()
        subprocess.run([str(program), "-m", "pip", "uninstall", "--yes", "--quiet", package], check=True)
    # The zip gives every file one date, and a .pyc that checks its source's date would
    # then be thrown away and rebuilt on the church's computer, all of them, during the
    # first start. These do not check: what is in the folder is what was compiled.
    subprocess.run([str(program), "-m", "compileall", "-q", "--invalidation-mode", "unchecked-hash",
                    str(python)], stdin=subprocess.DEVNULL)
    # Left behind by the install and of no use to anybody: the bootstrap pip already ran
    # from, and on Windows the little .exe launchers pip made, with this runner's paths
    # baked into them. The app always runs python -m, never those.
    (python / "get-pip.py").unlink(missing_ok=True)
    shutil.rmtree(python / "Scripts", ignore_errors=True)
    return fetch


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, default=ROOT / "dist", help="where to write it")
    parser.add_argument("--version", default=version.VERSION, help="the number in the filename")
    parser.add_argument("--python", type=Path, default=None,
                        help="a Python to put in as python/ (with --bundle: installed into first)")
    parser.add_argument("--bundle", choices=sorted(BUNDLES), default=None,
                        help="build the download for this computer, with --python")
    args = parser.parse_args()

    fetch: dict[str, str] = {}
    if args.bundle:
        if not args.python:
            raise SystemExit("--bundle heeft --python nodig: de Python die erin gaat.")
        fetch = prepare(args.python)
    elif args.python:
        interpreter(args.python)
    built = build(args.out, args.version, args.python, args.bundle, fetch)
    size = built.stat().st_size / 1e6
    with zipfile.ZipFile(built) as zip_file:
        count = len(zip_file.namelist())
    print(f"{built}  ({size:.1f} MB, {count} bestanden)")
    if fetch:
        print("Bij de eerste start opgehaald: " + ", ".join(f"{k} {v}" for k, v in fetch.items()))
    print("Uitpakken en start.bat of start.command aanklikken. Verder is er niets nodig.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
