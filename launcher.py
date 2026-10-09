"""One-click launcher for Preekstof.

Started by start.bat (Windows) or start.command (macOS), with the Python that came with the
download or one they found on the machine. This script:

  1. moves a church's work out of the app folder into its own folder, once (places.py),
  2. installs or updates the Python packages when backend/requirements.txt changed,
  3. loads config.env (API key, model choices),
  4. fetches the NVIDIA libraries when config.env asks for the graphics card,
  5. makes sure ffmpeg/ffprobe are available (downloads a build into tools/ if not),
  6. starts the web server, opens the browser and fetches the models in the background.

Everything it says, it says in Dutch: the person reading the black window is a volunteer.

    python launcher.py             start the app
    python launcher.py --prepare   only install the packages, then stop (the release build)
    python launcher.py --smoke     start, check that the app answers and can render, then stop
"""

import asyncio
import importlib.util
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

from backend import places  # plain standard library, so it works before anything is installed

ROOT = Path(__file__).resolve().parent
TOOLS = ROOT / "tools" / "ffmpeg"
CONFIG = places.CONFIG
CONFIG_EXAMPLE = ROOT / "config.example.env"
RESTART = 75  # the exit code start.bat and start.command start the app again on
RESTARTING = places.DATA / ".herstart"  # the browser tab is still open; do not open another
PORT = int(os.environ.get("PORT", "8000").split("#")[0].strip() or "8000")

FFMPEG_DOWNLOADS = {
    "Windows": [("https://www.gyan.dev/ffmpeg/builds/ffmpeg-release-essentials.zip", ("ffmpeg.exe", "ffprobe.exe"))],
    # One build per kind of Mac. An Intel build on Apple Silicon only runs with Rosetta,
    # which a Mac does not have until something asks for it.
    "Darwin-arm64": [
        ("https://ffmpeg.martin-riedl.de/redirect/latest/macos/arm64/release/ffmpeg.zip", ("ffmpeg",)),
        ("https://ffmpeg.martin-riedl.de/redirect/latest/macos/arm64/release/ffprobe.zip", ("ffprobe",)),
    ],
    "Darwin-x86_64": [
        ("https://ffmpeg.martin-riedl.de/redirect/latest/macos/amd64/release/ffmpeg.zip", ("ffmpeg",)),
        ("https://ffmpeg.martin-riedl.de/redirect/latest/macos/amd64/release/ffprobe.zip", ("ffprobe",)),
    ],
}


def ffmpeg_downloads() -> list[tuple[str, tuple[str, ...]]] | None:
    system = platform.system()
    if system == "Darwin":
        return FFMPEG_DOWNLOADS.get(f"Darwin-{platform.machine()}")
    return FFMPEG_DOWNLOADS.get(system)


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

    if sys.stdout.isatty():  # the window's title; in a log it is only noise
        print(f"\33]0;Preekstof {full()}\a", end="", flush=True)
    say(f"versie {full()}")


# --- python packages ----------------------------------------------------------

REQUIREMENTS = ROOT / "backend" / "requirements.txt"
INSTALLED_STAMP = Path(sys.prefix) / "requirements.installed"


def ensure_pip() -> None:
    """Make sure this interpreter can install things, which an embeddable Python cannot.

    The embeddable Python from python.org, which the Windows download is built on, ships
    without pip. The release build gives it one before zipping, so the download has it; this
    is for an embeddable Python somebody put together by hand, with `get-pip.py` beside it.

    An ordinary Python has pip already and never comes in here.
    """
    if importlib.util.find_spec("pip") is not None:
        return
    bootstrap = Path(sys.executable).parent / "get-pip.py"
    if not bootstrap.is_file():
        raise SystemExit(
            "Deze Python kan geen onderdelen installeren en get-pip.py staat er niet bij. "
            "Haal de app opnieuw op, of installeer Python van python.org en start opnieuw.")
    say("Deze Python krijgt eenmalig zijn installatieprogramma …")
    if subprocess.run([sys.executable, str(bootstrap), "--no-warn-script-location"]).returncode != 0:
        raise SystemExit("Het installatieprogramma kon niet opgezet worden. Controleer de "
                         "internetverbinding en start opnieuw.")


INSTALL_LOG = places.LOGS / "installatie.log"


def quietly(command: list[str], doing: str) -> bool:
    """Run pip without its pages of English, and show one line that keeps moving instead.

    What pip says goes to logs/installatie.log in the church's own folder, and the last of it
    comes onto the screen when something goes wrong, which is the only time anyone reads it.
    """
    INSTALL_LOG.parent.mkdir(parents=True, exist_ok=True)
    began = time.monotonic()
    with INSTALL_LOG.open("a", encoding="utf-8") as log:
        log.write(f"\n--- {time.strftime('%Y-%m-%d %H:%M:%S')}  {' '.join(command)}\n")
        log.flush()
        try:
            process = subprocess.Popen(command, stdout=log, stderr=subprocess.STDOUT)
        except OSError as exc:
            log.write(f"{exc}\n")
            return False
        # A line that keeps moving in a window; in a log (CI, a pipe) it would be one line
        # of a thousand, so there it is said once.
        moving = sys.stdout.isatty()
        if not moving:
            print(f"[Preekstof] {doing} …", flush=True)
        while process.poll() is None:
            took = int(time.monotonic() - began)
            if moving:
                print(f"\r[Preekstof] {doing} · {took // 60} min {took % 60:02d} s ", end="", flush=True)
            time.sleep(1)
    if moving:
        print()
    if process.returncode == 0:
        return True
    lines = INSTALL_LOG.read_text(encoding="utf-8", errors="replace").splitlines()[-15:]
    print("\n".join(lines))
    say(f"Wat er precies gebeurde staat in {INSTALL_LOG}.")
    return False


def ensure_requirements() -> None:
    """Install the packages from requirements.txt whenever that file changed since the last install.

    A download that came with everything already installed has the stamp, and passes here
    in a moment, apart from what it left out on purpose (fetch_left_out).
    """
    wanted = REQUIREMENTS.read_text(encoding="utf-8")
    if INSTALLED_STAMP.exists() and INSTALLED_STAMP.read_text(encoding="utf-8") == wanted:
        fetch_left_out()
        return
    ensure_pip()
    say("De onderdelen van de app worden geïnstalleerd. De eerste keer duurt dat een paar minuten.")
    done = quietly([sys.executable, "-m", "pip", "install", "--disable-pip-version-check",
                    "--no-warn-script-location", "--progress-bar", "off", "-r", str(REQUIREMENTS)],
                   "Onderdelen installeren")
    if not done:
        raise SystemExit("Het installeren van de onderdelen is mislukt. Controleer de internetverbinding "
                         "en start opnieuw.")
    INSTALLED_STAMP.write_text(wanted, encoding="utf-8")
    say("De onderdelen zijn geïnstalleerd.")


BUNDLE = ROOT / "bundle.json"


def left_out() -> dict[str, str]:
    """What the download for this computer left out on purpose, with the version to fetch.

    PyAV, for now: its wheel carries an FFmpeg built with x264 and x265, and that is the
    kind of thing this app has a church fetch for itself rather than hand on (see NOTICE).
    The release build wrote down the version it took out, so the one fetched here is the
    one the rest was installed against.
    """
    try:
        said = json.loads(BUNDLE.read_text(encoding="utf-8")).get("fetch")
    except (OSError, ValueError, AttributeError):
        return {}
    if not isinstance(said, dict):
        return {}
    return {str(name): str(number) for name, number in said.items()
            if importlib.util.find_spec(str(name)) is None}


def fetch_left_out() -> None:
    missing = left_out()
    if not missing:
        return
    ensure_pip()
    say("Eén onderdeel wordt eenmalig opgehaald; dat mag de download zelf niet meebrengen.")
    pinned = [f"{name}=={number}" if number else name for name, number in sorted(missing.items())]
    done = quietly([sys.executable, "-m", "pip", "install", "--disable-pip-version-check",
                    "--no-warn-script-location", "--progress-bar", "off", "--no-deps", *pinned],
                   "Onderdeel ophalen")
    if not done:
        raise SystemExit("Een onderdeel kon niet opgehaald worden. Controleer de internetverbinding "
                         "en start opnieuw.")
    importlib.invalidate_caches()


# --- config.env ---------------------------------------------------------------


def load_config() -> None:
    if not CONFIG.exists() and CONFIG_EXAMPLE.exists():
        CONFIG.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy(CONFIG_EXAMPLE, CONFIG)
        say(f"De instellingen staan in {CONFIG}. De sleutel voor Claude vul je in de app zelf in.")
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


def download(url: str, target: Path, tries: int = 3) -> None:
    """Fetch one file, saying how far it is, and try again when the line drops."""
    for attempt in range(1, tries + 1):
        try:
            from backend import version  # plain standard library

            request = urllib.request.Request(url, headers={"User-Agent": version.USER_AGENT})
            with urllib.request.urlopen(request, timeout=120) as res, target.open("wb") as out:
                total = int(res.headers.get("content-length") or 0)
                done = 0
                moving = sys.stdout.isatty()  # in a log, a hundred lines of percentages say nothing
                while chunk := res.read(1024 * 256):
                    out.write(chunk)
                    done += len(chunk)
                    if total and moving:
                        # Of how many, not just how far: "12 MB" says nothing about how long
                        # this is going to take, and this is the first thing a new install waits on.
                        print(f"\r  {done * 100 // total:3d}%  ({done // 1_000_000} van "
                              f"{total // 1_000_000} MB)", end="", flush=True)
                if moving:
                    print()
                else:
                    print(f"  {done // 1_000_000} MB binnen", flush=True)
            return
        except OSError as exc:
            print()
            if attempt == tries:
                raise
            say(f"Het ophalen haperde ({exc}); nog een keer …")
            time.sleep(2 * attempt)


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
    downloads = ffmpeg_downloads()
    if not downloads:
        raise SystemExit("FFmpeg is niet geïnstalleerd. Installeer het met de pakketbeheerder van deze "
                         "computer (bijvoorbeeld: sudo apt install ffmpeg) en start opnieuw.")
    say("FFmpeg, het programma dat de video's maakt, wordt eenmalig opgehaald (ongeveer 100 MB) …")
    for url, names in downloads:
        archive = TOOLS.parent / "download.zip"
        TOOLS.parent.mkdir(parents=True, exist_ok=True)
        try:
            download(url, archive)
        except OSError as exc:
            raise SystemExit(f"FFmpeg kon niet opgehaald worden ({exc}). Controleer de internetverbinding "
                             "en start opnieuw.") from exc
        extract_binaries(archive, names)
        archive.unlink()
    os.environ["PATH"] = str(TOOLS) + os.pathsep + os.environ.get("PATH", "")
    if not ffmpeg_ready():
        raise SystemExit("FFmpeg kwam niet goed binnen. Start opnieuw; lukt het dan nog niet, installeer "
                         "FFmpeg dan zelf via https://ffmpeg.org/download.html.")
    say("FFmpeg staat klaar.")


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
    return (f"Node.js {'.'.join(str(n) for n in version)} in {node} is te oud om het scherm te bouwen; "
            f"er is {wanted} nodig. Installeer een nieuwere Node.js via https://nodejs.org (22 is de "
            "veilige keus) en start opnieuw.")


def carry_on_or_stop(built: Path, trouble: str) -> None:
    """Start with the interface that is already there, or stop when there is none.

    A build that will not run is a reason to say so loudly, not a reason to keep a church
    from using the app: the built interface is committed, so there is nearly always one to
    fall back on. That it may be older than the code is exactly what has to be said.
    """
    say(trouble)
    if not built.exists():
        raise SystemExit("Er is geen gebouwd scherm om op terug te vallen (frontend/dist ontbreekt), dus "
                         "de app kan niet starten. Los het bovenstaande op, of vraag een ontwikkelaar om "
                         "`npm run build` te draaien in frontend/.")
    say("Het scherm dat met de app meekwam wordt gebruikt. Dat werkt, maar wat je net hebt binnengehaald "
        "zit er pas in als het bouwen lukt.")


def ensure_frontend() -> None:
    if not frontend_is_stale():
        return
    frontend = ROOT / "frontend"
    built = frontend / "dist" / "index.html"
    npm = shutil.which("npm")
    if npm is None:
        carry_on_or_stop(built, "Het scherm is veranderd, maar Node.js is niet geïnstalleerd, dus het kan "
                                "niet opnieuw gebouwd worden. Installeer Node.js via https://nodejs.org en "
                                "start opnieuw.")
        return
    old = node_too_old(frontend)
    if old:
        carry_on_or_stop(built, old)
        return
    say("Het scherm van de app wordt gebouwd …")
    try:
        if not (frontend / "node_modules").is_dir():
            subprocess.run([npm, "install"], cwd=frontend, check=True)
        subprocess.run([npm, "run", "build"], cwd=frontend, check=True)
    except subprocess.CalledProcessError:
        carry_on_or_stop(built, "Het bouwen van het scherm is mislukt; wat er misging staat hierboven.")


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
            say(f"Opent de browser niet vanzelf? Ga dan naar {url}")
            webbrowser.open(url)
            return
        time.sleep(0.5)


def fetch_models() -> None:
    """The speech model and the person model, fetched while nobody is waiting on them yet.

    They are not in the download: the speech model is 460 MB, and the person model is
    AGPL-licensed and only ever fetched by the computer that uses it (NOTICE). Fetched here,
    on the first start, they are there by the time somebody picks a service.
    """
    def run() -> None:
        try:
            from backend import transcription, vision

            vision.ensure_models()
        except Exception:  # noqa: BLE001  following the speaker fetches it again when needed
            pass
        try:
            transcription.prefetch(say)
        except Exception:  # noqa: BLE001  the first transcription fetches it then
            pass

    threading.Thread(target=run, daemon=True).start()


def smoke() -> None:
    """Start, check that the app answers and that FFmpeg can make a video, then stop.

    The release build runs this on a real Windows and a real Mac, through start.bat and
    start.command, so a download that cannot start never reaches a church.
    """
    import urllib.error

    def ask(path: str) -> bytes:
        with urllib.request.urlopen(f"http://127.0.0.1:{PORT}{path}", timeout=30) as answer:
            return answer.read()

    server = threading.Thread(target=lambda: asyncio.run(serve()), daemon=True)
    server.start()
    for _ in range(120):
        if port_in_use(PORT):
            break
        time.sleep(0.5)
    try:
        health = json.loads(ask("/health"))
        page = ask("/")
        fonts = json.loads(ask("/fonts"))
    except (urllib.error.URLError, OSError, ValueError) as exc:
        raise SystemExit(f"Rooktest: de app antwoordt niet ({exc}).") from exc
    if b"<div id=\"root\">" not in page or not fonts:
        raise SystemExit("Rooktest: het scherm of de lettertypes ontbreken.")
    for name in ("faster_whisper", "ctranslate2", "onnxruntime", "av"):
        if importlib.util.find_spec(name) is None:
            raise SystemExit(f"Rooktest: het onderdeel {name} ontbreekt.")
    import tempfile

    from backend import selftest

    with tempfile.TemporaryDirectory() as work:
        video = selftest.make_video(Path(work))
        made, _clip = selftest.step_clip(Path(work), video, "Rooktest")
    if not made.ok:
        raise SystemExit(f"Rooktest: een clip maken lukt niet ({made.detail}).")
    say(f"Rooktest geslaagd: versie {health.get('version')}, {len(fonts)} lettertypes, {made.detail}.")


def main() -> None:
    os.chdir(ROOT)
    flags = set(sys.argv[1:])
    moved = places.move_in()  # before anything opens a file in the church's folder
    ensure_requirements()
    keep_the_window()  # before anything else has a chance to fail
    announce()  # after the install, so the import of backend.version can succeed
    if moved:
        say(f"Je eigen werk staat voortaan in {places.DATA}, los van de app. Bijwerken laat het "
            f"daar met rust. ({len(moved)} onderdelen verhuisd.)")
    if "--prepare" in flags:
        # The release build stops here. FFmpeg never goes into a download (see NOTICE), and
        # the configuration belongs to whoever runs it.
        say("De onderdelen voor de download zijn geïnstalleerd.")
        return
    load_config()
    # The speech model cache falls back to copies on Windows without developer mode; that is fine.
    os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
    ensure_cuda()  # after load_config: WHISPER_DEVICE lives in config.env
    ensure_ffmpeg()
    ensure_frontend()
    if "--smoke" in flags:
        smoke()
        return
    mention_updates()
    url = f"http://localhost:{PORT}"
    if port_in_use(PORT):
        say(f"Preekstof draait al; {url} wordt geopend.")
        webbrowser.open(url)
        return
    restarted = RESTARTING.exists()
    RESTARTING.unlink(missing_ok=True)
    say(f"Preekstof draait op {url}")
    say("Laat dit venster open zolang je met Preekstof werkt. Sluit je het, dan stopt de app.")
    if not restarted:  # after an update the page that asked for it is still open, and reloads itself
        threading.Thread(target=open_browser_when_ready, args=(url,), daemon=True).start()
    fetch_models()
    asyncio.run(serve())
    from backend import lifecycle

    if lifecycle.wanted:
        RESTARTING.parent.mkdir(parents=True, exist_ok=True)
        RESTARTING.write_text("1", encoding="utf-8")
        say("Preekstof start opnieuw …")
        raise SystemExit(RESTART)


def _ignore_dropped_connections(loop: asyncio.AbstractEventLoop, context: dict) -> None:
    """Browsers open spare connections and drop them unused; on Windows the Proactor loop
    reports each one as a ConnectionResetError. Those are harmless, so keep them out of the log."""
    if isinstance(context.get("exception"), (ConnectionResetError, ConnectionAbortedError, BrokenPipeError)):
        return
    loop.default_exception_handler(context)


async def serve() -> None:
    import uvicorn

    from backend import lifecycle

    asyncio.get_running_loop().set_exception_handler(_ignore_dropped_connections)
    config = uvicorn.Config("backend.main:app", host=os.environ.get("HOST", "127.0.0.1"), port=PORT, log_level="warning")
    server = uvicorn.Server(config)
    lifecycle.attach(lambda: setattr(server, "should_exit", True))
    await server.serve()


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        pass
    except SystemExit as exc:
        if exc.code == RESTART:
            raise
        if exc.code not in (None, 0):
            say(str(exc.code))
            if sys.stdin and sys.stdin.isatty():
                input("Druk op Enter om dit venster te sluiten.")
            raise
