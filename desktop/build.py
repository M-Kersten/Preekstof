"""Build the desktop app for the computer this runs on.

    python desktop/build.py                  FFmpeg, PyInstaller, check, package
    python desktop/build.py --no-window      the check without opening a window (no screen)
    python desktop/build.py --skip-check     build and package only

Run it with a Python that has backend/requirements.txt and desktop/requirements.txt
installed, and without PyAV (pip uninstall av): see desktop/README.md. What comes out, in
desktop/out/:

    Mac (Apple chip)   Preekstof.app, and Preekstof.dmg to hand out
    Windows (x64)      Preekstof/Preekstof.exe, and Preekstof-Setup.exe to hand out
                       (when Inno Setup is installed; otherwise the folder only)
    Linux              Preekstof/Preekstof, only to try the packing; no window, no package

FFmpeg comes from the same builders the launcher downloads from (launcher.FFMPEG_DOWNLOADS):
gyan.dev for Windows, martin-riedl.de for the Mac. It is a GPL build and runs as a program
of its own beside the app; its licence and where its source is go along in ffmpeg/ (NOTICE).
"""

import argparse
import json
import os
import platform
import shutil
import subprocess
import sys
import tempfile
import zipfile
from pathlib import Path

DESKTOP = Path(__file__).resolve().parent
ROOT = DESKTOP.parent
OUT = DESKTOP / "out"
FFMPEG = DESKTOP / "build" / "ffmpeg"
sys.path.insert(0, str(ROOT))

import launcher  # noqa: E402  standard library only at import
from backend import version  # noqa: E402


def say(message: str) -> None:
    print(f"[build] {message}", flush=True)


# --- FFmpeg ----------------------------------------------------------------------------


def fetch_ffmpeg() -> None:
    """FFmpeg and ffprobe for this computer into desktop/build/ffmpeg, with their licence."""
    shutil.rmtree(FFMPEG, ignore_errors=True)
    FFMPEG.mkdir(parents=True)
    downloads = launcher.ffmpeg_downloads()
    if not downloads:
        # Linux, to try the packing: the FFmpeg of this machine. Not something to hand out.
        for name in ("ffmpeg", "ffprobe"):
            found = shutil.which(name)
            if not found:
                raise SystemExit(f"{name} is niet gevonden op deze computer.")
            shutil.copy2(found, FFMPEG / name)
    else:
        with tempfile.TemporaryDirectory() as work:
            for url, names in downloads:
                archive = Path(work) / "download.zip"
                say(f"FFmpeg ophalen: {url}")
                launcher.download(url, archive)
                with zipfile.ZipFile(archive) as zipped:
                    for member in zipped.namelist():
                        base = member.rsplit("/", 1)[-1]
                        keep = base in names or (base in ("LICENSE", "README.txt") and "/" in member
                                                 and member.count("/") == 1)
                        if keep and not member.endswith("/"):
                            target = FFMPEG / (base if base in names else f"FFMPEG-{base}")
                            with zipped.open(member) as src, target.open("wb") as dst:
                                shutil.copyfileobj(src, dst)
                            target.chmod(0o755)
    program = FFMPEG / ("ffmpeg.exe" if os.name == "nt" else "ffmpeg")
    said = subprocess.run([str(program), "-hide_banner", "-version"], capture_output=True, text=True,
                          check=True).stdout
    first = said.splitlines()[0] if said else "onbekend"
    if "--enable-libass" not in said:
        raise SystemExit(f"Deze FFmpeg heeft geen libass; ondertitels inbranden kan dan niet. ({first})")
    (FFMPEG / "FFMPEG-LEESMIJ.txt").write_text(
        "FFmpeg en ffprobe in deze map zijn niet van Preekstof.\n\n"
        f"{first}\n\n"
        "FFmpeg valt onder de GNU GPL (versie 3 of later voor deze build, met x264 en libass).\n"
        "Preekstof start het als apart programma en is er niet mee gelinkt.\n"
        "De broncode van FFmpeg staat op https://ffmpeg.org/download.html en in\n"
        "https://github.com/FFmpeg/FFmpeg; de build komt van "
        + ("https://www.gyan.dev/ffmpeg/builds/" if os.name == "nt" else "https://ffmpeg.martin-riedl.de/")
        + ".\n\nVolledige configuratie:\n" + said,
        encoding="utf-8")
    say(f"FFmpeg klaar: {first}")


# --- PyInstaller -----------------------------------------------------------------------


def pyinstaller() -> None:
    # PyInstaller looks into packages in a Python of its own; the stand-in for PyAV has to
    # be findable there too, or faster-whisper cannot be imported and half of it is missed.
    stubs = str(DESKTOP / "stubs")
    env = {**os.environ, "PREEKSTOF_FFMPEG_DIR": str(FFMPEG),
           "PYTHONPATH": os.pathsep.join(filter(None, [stubs, os.environ.get("PYTHONPATH")]))}
    subprocess.run([sys.executable, "-m", "PyInstaller", str(DESKTOP / "preekstof.spec"),
                    "--noconfirm", "--clean", "--distpath", str(OUT), "--workpath", str(DESKTOP / "build" / "work")],
                   cwd=ROOT, env=env, check=True)


def folder() -> Path:
    """Where the packed app's files are: inside the .app on a Mac."""
    if sys.platform == "darwin":
        return OUT / "Preekstof.app" / "Contents"
    return OUT / "Preekstof"


def program() -> Path:
    if sys.platform == "darwin":
        return OUT / "Preekstof.app" / "Contents" / "MacOS" / "Preekstof"
    return OUT / "Preekstof" / ("Preekstof.exe" if os.name == "nt" else "Preekstof")


def no_pyav() -> None:
    """The real PyAV must not have come along: it would put x264 and x265 (GPL) inside the
    app's own process. Only the stand-in from desktop/stubs may be there."""
    # PyAV brings its FFmpeg libraries in a folder of its own (av.libs, or .dylibs inside av)
    # next to its compiled modules. The ffmpeg program in ffmpeg/ is something else: on a Mac
    # and on Windows it is one static file, and on Linux, for trying, the system's own.
    found = [path for path in folder().rglob("*")
             if path.is_dir() and path.name in ("av", "av.libs")
             and any(f.suffix in (".so", ".pyd", ".dylib", ".dll") for f in path.rglob("*"))]
    if found:
        raise SystemExit("PyAV is meegekomen in de app: " + ", ".join(str(f) for f in found[:5])
                         + ". Haal het weg met pip uninstall av en bouw opnieuw.")
    say("Geen PyAV in de app, alleen de vervanger.")


def macos_needed() -> None:
    """The macOS the app says it needs (Info.plist) must be at least what its parts need,
    measured the same way as for the zips: from the binaries themselves."""
    if sys.platform != "darwin":
        return
    from tools import release

    declared = os.environ.get("PREEKSTOF_MACOS", "14.0")
    needed = release.oldest_mac(folder())
    if needed and tuple(map(int, needed.split("."))) > tuple(map(int, declared.split("."))):
        raise SystemExit(f"De app zegt macOS {declared} nodig te hebben, maar iets erin vraagt {needed}.")
    say(f"Draait vanaf macOS {declared} (gemeten: {needed}).")


def check(window: bool) -> None:
    """Start the packed app the way the release does: --smoke, with a report to read."""
    with tempfile.TemporaryDirectory() as data:
        report = Path(data) / "rooktest.json"
        env = {**os.environ, "PREEKSTOF_DATA": str(Path(data) / "Preekstof")}
        command = [str(program()), "--smoke", "--report", str(report)] + ([] if window else ["--no-window"])
        say("Rooktest: " + " ".join(command))
        log = Path(env["PREEKSTOF_DATA"]) / "logs" / "preekstof.log"
        try:
            status = subprocess.run(command, env=env, timeout=900).returncode
        except subprocess.TimeoutExpired:
            status = "te lang"
        said = json.loads(report.read_text(encoding="utf-8")) if report.is_file() else {}
        if status != 0 or not said.get("ok"):
            if log.is_file():
                print(log.read_text(encoding="utf-8", errors="replace")[-6000:])
            raise SystemExit(f"De rooktest van de app mislukte ({status}): {said}")
        say(f"Rooktest: {said.get('checks')} Venster: {said.get('window', 'niet geopend')}")


# --- what is handed out -----------------------------------------------------------------


def dmg() -> Path:
    staging = DESKTOP / "build" / "dmg"
    shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True)
    subprocess.run(["ditto", str(OUT / "Preekstof.app"), str(staging / "Preekstof.app")], check=True)
    (staging / "Programma's").symlink_to("/Applications")
    target = OUT / "Preekstof.dmg"
    target.unlink(missing_ok=True)
    subprocess.run(["hdiutil", "create", "-volname", "Preekstof", "-srcfolder", str(staging),
                    "-ov", "-format", "UDZO", str(target)], check=True)
    return target


def inno_setup() -> Path | None:
    candidates = [shutil.which("iscc"), shutil.which("ISCC"),
                  r"C:\Program Files (x86)\Inno Setup 6\ISCC.exe", r"C:\Program Files\Inno Setup 6\ISCC.exe"]
    compiler = next((c for c in candidates if c and Path(c).is_file()), None)
    if compiler is None:
        say("Inno Setup is niet gevonden; alleen de map Preekstof is gemaakt.")
        return None
    subprocess.run([compiler, f"/DVersion={version.VERSION}", f"/DDist={OUT / 'Preekstof'}",
                    f"/DOut={OUT}", str(DESKTOP / "installer.iss")], check=True)
    return OUT / "Preekstof-Setup.exe"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--no-window", action="store_true", help="test without opening a window")
    parser.add_argument("--skip-check", action="store_true", help="do not start the built app")
    parser.add_argument("--skip-ffmpeg", action="store_true", help="use desktop/build/ffmpeg as it is")
    args = parser.parse_args()

    say(f"Preekstof {version.VERSION} voor {platform.system()} {platform.machine()}")
    if not args.skip_ffmpeg or not FFMPEG.is_dir():
        fetch_ffmpeg()
    pyinstaller()
    no_pyav()
    macos_needed()
    if not args.skip_check:
        check(window=not args.no_window and sys.platform in ("darwin", "win32"))
    made: list[Path] = []
    if sys.platform == "darwin":
        made.append(dmg())
    elif os.name == "nt":
        setup = inno_setup()
        if setup:
            made.append(setup)
    for path in made:
        say(f"{path}  ({path.stat().st_size / 1e6:.0f} MB)")
    say("Klaar.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
