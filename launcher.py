"""One-click launcher for Preekstof.

Started by start.bat (Windows) or start.command (macOS) after those scripts
have created the Python environment. This script:

  1. installs or updates the Python packages when backend/requirements.txt changed,
  2. loads config.env (API key, model choices),
  3. fetches the NVIDIA libraries when config.env asks for the graphics card,
  4. makes sure ffmpeg/ffprobe are available (downloads a build into tools/ if not),
  5. starts the web server and opens the browser.

It can also be run by hand:  python launcher.py
"""

import asyncio
import json
import os
import platform
import shutil
import socket
import stat
import subprocess
import sys
import threading
import time
import urllib.request
import webbrowser
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent
TOOLS = ROOT / "tools" / "ffmpeg"
CONFIG = ROOT / "config.env"
CONFIG_EXAMPLE = ROOT / "config.example.env"
PORT = int(os.environ.get("PORT", "8000").split("#")[0].strip() or "8000")

FFMPEG_DOWNLOADS = {
    "Windows": [("https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip", ("ffmpeg.exe", "ffprobe.exe"))],
    "Darwin": [
        ("https://evermeet.cx/ffmpeg/getrelease/zip", ("ffmpeg",)),
        ("https://evermeet.cx/ffmpeg/getrelease/ffprobe/zip", ("ffprobe",)),
    ],
}


def say(message: str) -> None:
    print(f"[Preekstof] {message}", flush=True)


def keep_the_window() -> None:
    """Write down what this window says, so a failure leaves something to send.

    Everything after this point goes to logs/preekstof.log as well as to the screen. It
    runs after the packages are installed, because it needs the backend, and before
    anything else, because the failures worth reading about are the early ones.
    """
    from backend import logbook

    kept = logbook.begin()
    if kept is None:
        say("Het logboek kon niet geopend worden; de app draait gewoon door.")


def announce() -> None:
    """Say which version this is, in the window and on its title bar.

    start.bat sets the title before Python exists, so it cannot carry the number; this can.
    A support mail that begins with a screenshot of the black window then already answers
    the first question.
    """
    from backend.version import full

    print(f"\33]0;Preekstof {full()}\a", end="", flush=True)
    say(f"versie {full()}")


# --- python packages ----------------------------------------------------------

REQUIREMENTS = ROOT / "backend" / "requirements.txt"
INSTALLED_STAMP = Path(sys.prefix) / "requirements.installed"


def ensure_requirements() -> None:
    """Install the packages from requirements.txt whenever that file changed since the last install."""
    wanted = REQUIREMENTS.read_text(encoding="utf-8")
    if INSTALLED_STAMP.exists() and INSTALLED_STAMP.read_text(encoding="utf-8") == wanted:
        return
    say("Onderdelen worden geïnstalleerd of bijgewerkt, dit kan een paar minuten duren …")
    result = subprocess.run([sys.executable, "-m", "pip", "install", "-r", str(REQUIREMENTS)])
    if result.returncode != 0:
        raise SystemExit("Het installeren van de onderdelen is mislukt. Controleer de internetverbinding en start opnieuw.")
    INSTALLED_STAMP.write_text(wanted, encoding="utf-8")
    say("Onderdelen zijn up-to-date.")


# --- config.env ---------------------------------------------------------------


def load_config() -> None:
    if not CONFIG.exists() and CONFIG_EXAMPLE.exists():
        shutil.copy(CONFIG_EXAMPLE, CONFIG)
        say(f"Created {CONFIG.name}. Put your ANTHROPIC_API_KEY in it to enable clip suggestions.")
    if not CONFIG.exists():
        return
    from backend import settings

    for line in CONFIG.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, raw = line.partition("=")
        # settings.clean drops the note someone wrote behind the value. Without that,
        # "LLM_EFFORT=medium  # of high" reaches the API as one long word and every
        # passage comes back a 400, and a number written that way stops the app dead.
        key, value = key.strip(), settings.clean(raw)
        if key and value and key not in os.environ:
            os.environ[key] = value


# --- the graphics card ---------------------------------------------------------

# What CTranslate2 links against and does not ship. Together about a gigabyte on Windows,
# which is why they are not in backend/requirements.txt: almost every church runs on the
# processor and would be downloading them for nothing.
CUDA_PACKAGES = ("nvidia-cublas-cu12", "nvidia-cudnn-cu12")


def wants_card() -> bool:
    """Did anyone ask for the graphics card? The default is the processor, quietly."""
    from backend import settings

    return settings.text("WHISPER_DEVICE", "cpu").lower() in ("cuda", "auto")


def card_present() -> bool:
    """Is there an NVIDIA card to talk to? nvidia-smi comes with the driver."""
    smi = shutil.which("nvidia-smi")
    if smi is None:
        return False
    try:
        return subprocess.run([smi, "-L"], capture_output=True, text=True, timeout=30).returncode == 0
    except (OSError, subprocess.SubprocessError):
        return False


def cuda_libraries_ready() -> bool:
    """Are cuBLAS and cuDNN sitting where backend/gpu.py will point CTranslate2 at them?"""
    from backend import gpu

    return bool(gpu.package_dirs())


def ensure_cuda() -> None:
    """Fetch what the card needs, for the person who asked for the card.

    A fresh install with WHISPER_DEVICE=cuda fails inside the speech library with "Library
    cublas64_12.dll is not found or cannot be loaded": CTranslate2 links against cuBLAS and
    cuDNN without shipping them. The app survives that by writing out on the processor,
    which is not what someone who went into config.env to ask for the card was after.

    Nothing at all happens on the default setting, so a church on the processor never waits
    for a gigabyte it has no use for.
    """
    if not wants_card():
        return
    if not card_present():
        say("WHISPER_DEVICE vraagt om de videokaart, maar er is geen NVIDIA-kaart gevonden. "
            "Het uitschrijven gebeurt op de processor.")
        return
    if cuda_libraries_ready():
        return
    say("De NVIDIA-onderdelen voor het uitschrijven ontbreken nog. Ze worden nu opgehaald; "
        "dat is ongeveer een gigabyte en duurt een paar minuten \u2026")
    try:
        done = subprocess.run([sys.executable, "-m", "pip", "install", *CUDA_PACKAGES]).returncode == 0
    except (OSError, subprocess.SubprocessError):
        done = False
    if not done or not cuda_libraries_ready():
        # Never fatal: the app runs on the processor and says so per service.
        say("Het ophalen van de NVIDIA-onderdelen is mislukt. De app start gewoon en schrijft uit "
            "op de processor, dat duurt alleen langer. Zet WHISPER_DEVICE=cpu in config.env om "
            "deze melding weg te halen.")
        return
    say("De videokaart kan gebruikt worden.")


# --- ffmpeg -------------------------------------------------------------------


def ffmpeg_ready() -> bool:
    return shutil.which("ffmpeg") is not None and shutil.which("ffprobe") is not None


def download(url: str, target: Path) -> None:
    say(f"Downloading {url}")
    with urllib.request.urlopen(url, timeout=120) as res, target.open("wb") as out:
        total = int(res.headers.get("content-length") or 0)
        done = 0
        while chunk := res.read(1024 * 256):
            out.write(chunk)
            done += len(chunk)
            if total:
                print(f"\r  {done * 100 // total:3d}%  ({done // 1_000_000} MB)", end="", flush=True)
        print()


def extract_binaries(archive: Path, names: tuple[str, ...]) -> None:
    TOOLS.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(archive) as zf:
        for member in zf.namelist():
            base = member.rsplit("/", 1)[-1]
            if base in names and not member.endswith("/"):
                target = TOOLS / base
                with zf.open(member) as src, target.open("wb") as dst:
                    shutil.copyfileobj(src, dst)
                target.chmod(target.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    if platform.system() == "Darwin":  # remove the quarantine flag so Gatekeeper lets the binaries run
        for name in names:
            subprocess.run(["xattr", "-d", "com.apple.quarantine", str(TOOLS / name)], capture_output=True)


def ensure_ffmpeg() -> None:
    if TOOLS.is_dir():
        os.environ["PATH"] = str(TOOLS) + os.pathsep + os.environ.get("PATH", "")
    if ffmpeg_ready():
        return
    downloads = FFMPEG_DOWNLOADS.get(platform.system())
    if not downloads:
        raise SystemExit("ffmpeg and ffprobe are not installed. Install them with your package manager "
                         "(for example: sudo apt install ffmpeg) and start again.")
    say("FFmpeg was not found. Downloading it once (about 100 MB) into tools/ffmpeg …")
    for url, names in downloads:
        archive = TOOLS.parent / "download.zip"
        TOOLS.parent.mkdir(parents=True, exist_ok=True)
        download(url, archive)
        extract_binaries(archive, names)
        archive.unlink()
    os.environ["PATH"] = str(TOOLS) + os.pathsep + os.environ.get("PATH", "")
    if not ffmpeg_ready():
        raise SystemExit("FFmpeg download failed. Install FFmpeg manually (https://ffmpeg.org/download.html) and start again.")
    say("FFmpeg is ready.")


# --- frontend -----------------------------------------------------------------


SOURCE_GLOBS = ("src/**/*", "index.html", "package.json", "package-lock.json", "vite.config.ts", "tsconfig.json")


def frontend_is_stale() -> bool:
    """Is the built interface older than the code it was built from?

    The build is committed, so a fresh clone can run without Node. That also means a pull
    brings new source and an old build side by side, and without this check the app would
    keep serving the old one after a restart.
    """
    frontend = ROOT / "frontend"
    built = frontend / "dist" / "index.html"
    if not built.exists():
        return True
    when = built.stat().st_mtime
    for pattern in SOURCE_GLOBS:
        for path in frontend.glob(pattern):
            if path.is_file() and path.stat().st_mtime > when:
                return True
    return False


# What the build tools ask of Node. Vite says so in its own package.json, which is read when
# it is installed; this is the answer for a machine where node_modules is still empty.
NODE_NEEDED = "^20.19.0 || >=22.12.0"


def as_numbers(text: str) -> tuple[int, int, int] | None:
    """"v20.11.1" -> (20, 11, 1). None when it is not a version at all."""
    parts = text.strip().lstrip("v").split(".")[:3]
    try:
        numbers = [int(part) for part in parts]
    except ValueError:
        return None
    while len(numbers) < 3:
        numbers.append(0)
    return numbers[0], numbers[1], numbers[2]


def fits(version: tuple[int, int, int], spec: str) -> bool | None:
    """Does this Node satisfy an engines line like "^20.19.0 || >=22.12.0"?

    Only the two shapes these packages actually use are understood. Anything else answers
    None, and the caller then lets the build go ahead rather than refuse on a guess: being
    wrong about a range must never be the reason a church cannot start the app.
    """
    answer = False
    for clause in spec.split("||"):
        clause = clause.strip()
        if clause.startswith("^"):
            low = as_numbers(clause[1:])
            if low is None:
                return None
            if low <= version < (low[0] + 1, 0, 0):
                answer = True
        elif clause.startswith(">="):
            low = as_numbers(clause[2:])
            if low is None:
                return None
            if version >= low:
                answer = True
        else:
            return None
    return answer


def node_wanted(frontend: Path) -> str:
    """The requirement the installed build tool states, or the one it stated when this was written."""
    try:
        engines = json.loads((frontend / "node_modules" / "vite" / "package.json")
                             .read_text(encoding="utf-8")).get("engines") or {}
        return engines.get("node") or NODE_NEEDED
    except Exception:  # noqa: BLE001  not installed yet, or a shape we did not expect
        return NODE_NEEDED


def node_too_old(frontend: Path) -> str | None:
    """What is wrong with the Node on this machine, when it cannot build the interface.

    A Node that is one minor version short crashes inside the build with a stack trace about
    a file nobody here wrote, so it is worth saying plainly beforehand.
    """
    node = shutil.which("node")
    if node is None:
        return None  # npm without node is odd enough to let the build itself complain
    try:
        found = subprocess.run([node, "--version"], capture_output=True, text=True, timeout=30).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    version = as_numbers(found)
    wanted = node_wanted(frontend)
    if version is None or fits(version, wanted) is not False:
        return None
    return (f"Node.js {'.'.join(str(n) for n in version)} at {node} is too old to build the interface; "
            f"it asks for {wanted}. Install a newer Node.js from https://nodejs.org (22 is the safe "
            "choice) and start again.")


def carry_on_or_stop(built: Path, trouble: str) -> None:
    """Start with the interface that is already there, or stop when there is none.

    A build that will not run is a reason to say so loudly, not a reason to keep a church
    from using the app: the built interface is committed, so there is nearly always one to
    fall back on. That it may be older than the code is exactly what has to be said.
    """
    say(trouble)
    if not built.exists():
        raise SystemExit("There is no built interface to fall back on (frontend/dist is missing), so the "
                         "app cannot start. Fix the above, or ask a developer to run `npm run build` in "
                         "frontend/.")
    say("The interface that came with the repository is used instead. It works, but anything you have "
        "just pulled will not be in it until the build runs.")


def ensure_frontend() -> None:
    if not frontend_is_stale():
        return
    frontend = ROOT / "frontend"
    built = frontend / "dist" / "index.html"
    npm = shutil.which("npm")
    if npm is None:
        carry_on_or_stop(built, "The interface has changed but Node.js is not installed, so it cannot "
                                "be rebuilt. Install Node.js from https://nodejs.org and start again.")
        return
    old = node_too_old(frontend)
    if old:
        carry_on_or_stop(built, old)
        return
    say("Building the web interface …")
    try:
        if not (frontend / "node_modules").is_dir():
            subprocess.run([npm, "install"], cwd=frontend, check=True)
        subprocess.run([npm, "run", "build"], cwd=frontend, check=True)
    except subprocess.CalledProcessError:
        carry_on_or_stop(built, "Building the interface failed; what went wrong is in the lines above.")


# --- server -------------------------------------------------------------------


def mention_updates() -> None:
    """Say once, on start, that there is a newer one. Never install it.

    On its own thread with a short timeout, because a church whose internet is down must
    not wait on GitHub to get to its own app. Anything that goes wrong here is silence.
    """
    def ask() -> None:
        try:
            from backend import updates

            said = updates.note()
        except Exception:  # noqa: BLE001  never a reason not to start
            return
        for line in said.splitlines():
            say(line)

    thread = threading.Thread(target=ask, daemon=True)
    thread.start()
    thread.join(timeout=8)


def port_in_use(port: int) -> bool:
    with socket.socket() as s:
        return s.connect_ex(("127.0.0.1", port)) == 0


def open_browser_when_ready(url: str) -> None:
    for _ in range(60):
        if port_in_use(PORT):
            say(f"Open {url} in your browser if it did not open by itself.")
            webbrowser.open(url)
            return
        time.sleep(0.5)


def main() -> None:
    os.chdir(ROOT)
    ensure_requirements()
    keep_the_window()  # before anything else has a chance to fail
    announce()  # after the install, so the import of backend.version can succeed
    load_config()
    # The speech model cache falls back to copies on Windows without developer mode; that is fine.
    os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
    ensure_cuda()  # after load_config: WHISPER_DEVICE lives in config.env
    ensure_ffmpeg()
    ensure_frontend()
    mention_updates()
    url = f"http://localhost:{PORT}"
    if port_in_use(PORT):
        say(f"Something is already running on port {PORT}; opening {url}.")
        webbrowser.open(url)
        return
    say(f"Starting the app at {url}  (close this window to stop it)")
    threading.Thread(target=open_browser_when_ready, args=(url,), daemon=True).start()
    asyncio.run(serve())


def _ignore_dropped_connections(loop: asyncio.AbstractEventLoop, context: dict) -> None:
    """Browsers open spare connections and drop them unused; on Windows the Proactor loop
    reports each one as a ConnectionResetError. Those are harmless, so keep them out of the log."""
    if isinstance(context.get("exception"), (ConnectionResetError, ConnectionAbortedError, BrokenPipeError)):
        return
    loop.default_exception_handler(context)


async def serve() -> None:
    import uvicorn

    asyncio.get_running_loop().set_exception_handler(_ignore_dropped_connections)
    config = uvicorn.Config("backend.main:app", host=os.environ.get("HOST", "127.0.0.1"), port=PORT, log_level="warning")
    await uvicorn.Server(config).serve()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    except SystemExit as exc:
        if exc.code not in (None, 0):
            say(str(exc.code))
            if sys.stdin and sys.stdin.isatty():
                input("Press Enter to close.")
            raise
