"""Preekstof as a desktop app: the same server, in a window of its own.

PyInstaller packs this file, the backend and the built interface into Preekstof.app on a
Mac and Preekstof.exe on Windows (desktop/preekstof.spec). Nothing here replaces what the
browser version does: the backend is the same FastAPI app, served on 127.0.0.1, and the
window is a native web view (WKWebView on a Mac, WebView2 on Windows) pointed at it.
launcher.py with start.bat and start.command keeps working as before, and so does the
Vite dev server.

What this file adds is what a double-clicked app has to do by itself, with no black window
to read:

  - FFmpeg comes along inside the app and is put on PATH before anything looks for it.
  - Everything the app says goes to the same logs/preekstof.log as the browser version.
  - One app at a time: a second double-click says the first one is open.
  - The port stays the same between runs, because the interface remembers settings per
    address (frontend/src/remember.ts) and a new port would forget them.
  - Closing the window stops running work, so no FFmpeg is left behind.
  - Anything that goes wrong on the way up is shown in the window, in Dutch.

    python desktop/app.py                     run it from a checkout, the way the app runs
    python desktop/app.py --smoke --report r.json [--no-window]
                                              the release build's check, see smoke()
"""

import json
import os
import shutil
import socket
import subprocess
import sys
import threading
import time
import urllib.request
from pathlib import Path

if not getattr(sys, "frozen", False):
    # From a checkout: backend/ and launcher.py live one folder up.
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

TITLE = "Preekstof"
PORTS = range(8765, 8785)  # the first free one; normally always the first
WAIT_FOR_SERVER = 90.0  # seconds; a first start on a slow laptop imports a lot


# --- before anything else is imported ------------------------------------------------


def give_output_somewhere() -> None:
    """A windowed app has no console: sys.stdout is None, and the first print that is not
    a plain print() (a progress bar, a log handler) takes the app down. Point it at nothing;
    the log file gets everything once logbook takes over."""
    if sys.stdout is None:
        sys.stdout = open(os.devnull, "w", encoding="utf-8")  # noqa: SIM115
    if sys.stderr is None:
        sys.stderr = open(os.devnull, "w", encoding="utf-8")  # noqa: SIM115


def no_console_windows() -> None:
    """On Windows every FFmpeg the app starts would flash a black console window, because
    the app itself has none to share. Every subprocess is started without one."""
    if sys.platform != "win32":
        return
    original = subprocess.Popen

    class Popen(original):  # type: ignore[misc, valid-type]
        def __init__(self, *args, **kwargs):
            kwargs["creationflags"] = kwargs.get("creationflags", 0) | subprocess.CREATE_NO_WINDOW
            super().__init__(*args, **kwargs)

    subprocess.Popen = Popen  # type: ignore[misc]


def bundled() -> Path:
    """Where PyInstaller unpacked the app, or the checkout when run from source."""
    return Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent.parent))


def ffmpeg_on_path(data: Path) -> Path | None:
    """Put the FFmpeg that came with the app first on PATH, and say where it is.

    On a Mac the files of a downloaded app carry the quarantine flag, and macOS refuses to
    start a flagged program even when the app around it was allowed to open. The flag is
    taken off in place; when the app is somewhere it cannot write (a disk image, a
    translocated copy), FFmpeg is copied to the church's own folder and started from there.
    """
    folder = bundled() / "ffmpeg"
    if not folder.is_dir():
        from launcher import TOOLS  # a checkout: whatever the launcher downloaded, if anything

        folder = TOOLS
    if not folder.is_dir():
        return None
    if sys.platform == "darwin":
        folder = unquarantined(folder, data / ".ffmpeg")
    os.environ["PATH"] = str(folder) + os.pathsep + os.environ.get("PATH", "")
    return folder


def unquarantined(folder: Path, spare: Path) -> Path:
    flagged = [f for f in folder.iterdir() if f.is_file() and has_quarantine(f)]
    if not flagged:
        return folder
    if all(subprocess.run(["xattr", "-d", "com.apple.quarantine", str(f)],
                          capture_output=True).returncode == 0 for f in flagged):
        return folder
    spare.mkdir(parents=True, exist_ok=True)
    for f in folder.iterdir():
        if f.is_file():
            shutil.copy2(f, spare / f.name)
            subprocess.run(["xattr", "-d", "com.apple.quarantine", str(spare / f.name)], capture_output=True)
    return spare


def has_quarantine(path: Path) -> bool:
    return subprocess.run(["xattr", "-p", "com.apple.quarantine", str(path)],
                          capture_output=True).returncode == 0


# --- one app at a time, on a port that stays the same ------------------------------


def answers(port: int, timeout: float = 1.5) -> bool:
    """Is a Preekstof listening there? Something else on the port is not good enough."""
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/health", timeout=timeout) as reply:
            return "version" in json.loads(reply.read(200_000))
    except Exception:  # noqa: BLE001
        return False


def free(port: int) -> bool:
    with socket.socket() as s:
        try:
            s.bind(("127.0.0.1", port))
        except OSError:
            return False
    return True


class Lock:
    """The file that says this app is running, and on which port."""

    def __init__(self, data: Path):
        self.path = data / ".desktop.json"

    def other(self) -> int | None:
        """The port of another desktop app that is really running, or nothing."""
        try:
            said = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        port = said.get("port") if isinstance(said, dict) else None
        if isinstance(port, int) and said.get("pid") != os.getpid() and answers(port):
            return port
        return None

    def take(self, port: int) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(json.dumps({"pid": os.getpid(), "port": port}), encoding="utf-8")

    def release(self) -> None:
        try:
            said = json.loads(self.path.read_text(encoding="utf-8"))
            if said.get("pid") == os.getpid():
                self.path.unlink()
        except (OSError, ValueError, AttributeError):
            pass


def pick_port() -> int:
    wanted = os.environ.get("PREEKSTOF_PORT", "").strip()
    if wanted.isdigit():
        return int(wanted)
    for port in PORTS:
        if free(port):
            return port
    raise RuntimeError("Er is geen vrije poort gevonden voor Preekstof (8765 tot 8784).")


# --- the server --------------------------------------------------------------------


class Server:
    """uvicorn on its own thread, with the app object handed over directly: PyInstaller
    cannot follow the "backend.main:app" string uvicorn usually imports from."""

    def __init__(self, port: int):
        self.port = port
        self.url = f"http://127.0.0.1:{port}"
        self.uvicorn = None
        self.failed: BaseException | None = None
        self.thread = threading.Thread(target=self._run, name="server", daemon=True)

    def _run(self) -> None:
        try:
            import asyncio

            import uvicorn

            import launcher
            from backend import lifecycle
            from backend.main import app

            config = uvicorn.Config(app, host="127.0.0.1", port=self.port, log_level="warning",
                                    log_config=None)
            self.uvicorn = uvicorn.Server(config)
            lifecycle.attach(self.stop)

            async def serve() -> None:
                asyncio.get_running_loop().set_exception_handler(launcher._ignore_dropped_connections)
                await self.uvicorn.serve()

            asyncio.run(serve())
        except BaseException as exc:  # noqa: BLE001  shown in the window, see start()
            self.failed = exc
            import traceback

            traceback.print_exc()

    def start(self) -> None:
        self.thread.start()
        began = time.monotonic()
        while time.monotonic() - began < WAIT_FOR_SERVER:
            if self.failed is not None:
                raise RuntimeError(f"De app kon niet starten: {self.failed}")
            if answers(self.port):
                return
            time.sleep(0.25)
        raise RuntimeError("De app startte niet op tijd. Start Preekstof opnieuw.")

    def stop(self) -> None:
        if self.uvicorn is not None:
            self.uvicorn.should_exit = True

    def wait(self, seconds: float) -> None:
        self.thread.join(timeout=seconds)


def stop_work(seconds: float = 8.0) -> None:
    """Ask every running job to stop, and give it a moment to stop its FFmpeg."""
    try:
        from backend.main import jobs
    except Exception:  # noqa: BLE001  the server never got that far
        return
    if not jobs.cancel_all():
        return
    print("[Preekstof] Het venster is gesloten; het werk dat nog liep wordt gestopt.", flush=True)
    began = time.monotonic()
    while jobs.running() and time.monotonic() - began < seconds:
        time.sleep(0.2)


# --- what the window shows of its own ------------------------------------------------


PAGE = """<!doctype html><html lang="nl"><head><meta charset="utf-8"><style>
body {{ margin: 0; height: 100vh; display: grid; place-items: center; background: #2A1140; color: #EDE6F4;
       font: 16px/1.5 -apple-system, "Segoe UI", system-ui, sans-serif; }}
main {{ max-width: 34rem; padding: 2rem; text-align: center; }}
h1 {{ color: #FFF; font-size: 1.6rem; margin: 0 0 .6rem; }}
p {{ margin: .4rem 0; }} code {{ background: rgba(255,255,255,.1); padding: .1rem .35rem; border-radius: 4px; }}
.bar {{ width: 12rem; height: 4px; margin: 1.4rem auto 0; border-radius: 2px; background: rgba(255,255,255,.15); overflow: hidden; }}
.bar i {{ display: block; width: 40%; height: 100%; background: #C9971C; animation: go 1.2s ease-in-out infinite alternate; }}
@keyframes go {{ from {{ margin-left: 0 }} to {{ margin-left: 60% }} }}
</style></head><body><main>{body}</main></body></html>"""


def starting_page() -> str:
    return PAGE.format(body="<h1>Preekstof start</h1><p>Even geduld, dit duurt een paar tellen.</p>"
                            "<div class='bar'><i></i></div>")


def trouble_page(message: str, log: Path) -> str:
    from html import escape

    return PAGE.format(body=f"<h1>Preekstof kon niet starten</h1><p>{escape(message)}</p>"
                            f"<p>Wat er precies gebeurde staat in <code>{escape(str(log))}</code>. "
                            "Stuur dat bestand mee als je om hulp vraagt.</p>")


def already_open_page() -> str:
    return PAGE.format(body="<h1>Preekstof is al geopend</h1><p>Kijk in het Dock of de taakbalk: "
                            "daar staat het venster dat al draait. Dit venster kun je sluiten.</p>")


# --- Windows without WebView2 --------------------------------------------------------


def has_webview2() -> bool:
    """WebView2 is part of Windows 11 and nearly every Windows 10 by now. Nearly."""
    if sys.platform != "win32":
        return True
    import winreg

    client = r"Microsoft\EdgeUpdate\Clients\{F3017226-FE2A-4295-8BDF-00C3A9A7E4C5}"
    for root, path in ((winreg.HKEY_LOCAL_MACHINE, rf"SOFTWARE\WOW6432Node\{client}"),
                       (winreg.HKEY_LOCAL_MACHINE, rf"SOFTWARE\{client}"),
                       (winreg.HKEY_CURRENT_USER, rf"SOFTWARE\{client}")):
        try:
            with winreg.OpenKey(root, path) as key:
                version, _ = winreg.QueryValueEx(key, "pv")
                if version and version != "0.0.0.0":
                    return True
        except OSError:
            continue
    return False


def in_the_browser_instead(url: str) -> None:
    """No WebView2: the app opens in the browser, and a plain Windows message box is what
    keeps it running. OK closes Preekstof."""
    import ctypes
    import webbrowser

    webbrowser.open(url)
    ctypes.windll.user32.MessageBoxW(
        0, "Preekstof is geopend in je browser, op " + url + ".\n\n"
        "Dit venster houdt de app draaiende. Klik op OK als je klaar bent; dan stopt Preekstof.",
        TITLE, 0x40)


# --- the app -------------------------------------------------------------------------


def localization() -> dict[str, str]:
    return {"global.ok": "OK", "global.cancel": "Annuleer", "global.quit": "Afsluiten",
            "global.quitConfirmation": "Wil je Preekstof afsluiten?",
            "global.saveFile": "Bewaar", "cocoa.menu.about": "Over Preekstof",
            "cocoa.menu.services": "Voorzieningen", "cocoa.menu.view": "Weergave",
            "cocoa.menu.hide": "Verberg Preekstof", "cocoa.menu.hideOthers": "Verberg andere",
            "cocoa.menu.showAll": "Toon alles", "cocoa.menu.quit": "Stop Preekstof",
            "cocoa.menu.fullscreen": "Schermvullende weergave"}


def start_up(data: Path, models: bool = True) -> tuple[Server, Lock, Path | None]:
    """Everything up to a running server. Raises RuntimeError with a Dutch reason."""
    import launcher
    from backend import places

    if not places.FROZEN:  # from a checkout, an older install's work moves out once, as with the launcher
        places.move_in()
    launcher.keep_the_window()
    launcher.announce()
    ffmpeg = ffmpeg_on_path(data)
    launcher.say(f"FFmpeg: {ffmpeg or 'niet meegeleverd, gezocht op deze computer'}")
    launcher.load_config()
    os.environ.setdefault("HF_HUB_DISABLE_SYMLINKS_WARNING", "1")
    port = pick_port()
    os.environ["PORT"] = str(port)  # read by backend.main for the origins it accepts
    lock = Lock(data)
    lock.take(port)
    server = Server(port)
    server.start()
    launcher.say(f"Preekstof draait op {server.url}")
    if models:  # the speech model and the person model, in the background, as the launcher does
        launcher.fetch_models()
    return server, lock, ffmpeg


def run() -> int:
    import webview

    from backend import logbook, places

    data = places.DATA
    data.mkdir(parents=True, exist_ok=True)
    if Lock(data).other() is not None:
        webview.create_window(TITLE, html=already_open_page(), width=520, height=320)
        webview.start(localization=localization())
        return 0

    webview.settings["ALLOW_DOWNLOADS"] = True  # the finished clip is a download
    webview.settings["OPEN_EXTERNAL_LINKS_IN_BROWSER"] = True
    if not has_webview2():
        server, lock, _ = start_up(data)
        try:
            in_the_browser_instead(server.url)
        finally:
            shut_down(server, lock)
        return 0

    window = webview.create_window(TITLE, html=starting_page(), width=1360, height=900,
                                   min_size=(1024, 680), text_select=True, background_color="#2A1140")
    state: dict = {}

    def bring_up() -> None:
        try:
            server, lock, _ = start_up(data)
            state.update(server=server, lock=lock)
            show_the_app(window, server.url)
        except Exception as exc:  # noqa: BLE001
            import traceback

            traceback.print_exc()
            window.load_html(trouble_page(str(exc), logbook.CURRENT))

    # The browser storage stays between runs (not private), in the church's own folder.
    webview.start(bring_up, private_mode=False, storage_path=str(data / ".venster"),
                  localization=localization())
    shut_down(state.get("server"), state.get("lock"))
    return 0


def show_the_app(window, url: str, tries: int = 5) -> None:
    """Swap the starting page for the app, and make sure the swap held.

    The starting page is still loading when a quick start (a second, with everything
    cached) already has the server up. Asked to go to the app at that moment, the window
    went there and then finished drawing the starting page on top of it: a window that
    said "Preekstof start" for good, until the app was closed and opened again. So first
    the starting page is let finish, and afterwards the window is asked where it is.
    """
    window.events.loaded.wait(15)
    for _attempt in range(tries):
        window.load_url(url)
        window.events.loaded.wait(20)
        time.sleep(0.5)
        try:
            now = window.get_current_url() or ""
        except Exception:  # noqa: BLE001  a window that cannot say is given the benefit
            return
        if now.startswith(url.rstrip("/")):
            return
        print(f"[venster] nog niet bij de app ({now or 'leeg'}); opnieuw")


def shut_down(server: "Server | None", lock: "Lock | None") -> None:
    stop_work()
    if server is not None:
        server.stop()
        server.wait(5)
    if lock is not None:
        lock.release()


# --- the release build's check ---------------------------------------------------------


def smoke(report: Path | None, window: bool) -> int:
    """What the release workflow runs on the packed app, on a real Mac and Windows.

    The same checks as launcher.py --smoke, against this app's own server: the page and
    the fonts are served, a clip renders with subtitles through the bundled FFmpeg, the
    speaker is followed, and a sentence is written out with the tiny model. Then, unless
    --no-window, a real window opens on the app and the interface has to appear in it.
    The outcome goes to `report` as JSON, because a windowed app has no output to read.
    """
    import launcher
    from backend import places

    said: dict = {"ok": False, "data": str(places.DATA)}

    def write() -> None:
        if report:
            report.write_text(json.dumps(said, indent=2, ensure_ascii=False), encoding="utf-8")

    def give_up_after(seconds: float) -> None:
        def watch() -> None:
            time.sleep(seconds)
            said["error"] = f"De rooktest liep na {seconds:.0f} seconden nog."
            write()
            os._exit(3)

        threading.Thread(target=watch, daemon=True).start()

    give_up_after(780)
    server = lock = None
    try:
        # What run() does first when an earlier start left its lock behind: ask that port
        # whether a Preekstof answers. On a church's Mac that first request came before
        # the certificates were set up, and every https request after it failed. The
        # build machine never had an old lock, so this check never saw it.
        answers(pick_port())
        server, lock, ffmpeg = start_up(places.DATA, models=False)
        said["ffmpeg"] = str(ffmpeg) if ffmpeg else None
        said["ffmpegFound"] = shutil.which("ffmpeg")
        launcher.say("Rooktest: de app draait; nu het werk.")
        said["checks"] = launcher.smoke_checks(server.port)
        launcher.say("Rooktest: " + said["checks"])
        said["modules"] = packed_modules()
        launcher.say(f"Rooktest: onderdelen {said['modules']}")
        if window:
            write()
            launcher.say("Rooktest: het venster gaat open.")
            said["window"] = window_check(server.url)
            launcher.say(f"Rooktest: venster {said['window']}")
            if not said["window"].get("root"):
                raise RuntimeError(f"Het venster liet de app niet zien: {said['window']}")
        said["ok"] = True
    except SystemExit as exc:
        said["error"] = str(exc.code)
    except Exception as exc:  # noqa: BLE001
        import traceback

        traceback.print_exc()
        said["error"] = f"{type(exc).__name__}: {exc}"
    finally:
        write()
        shut_down(server, lock)
    print(json.dumps(said, ensure_ascii=False), flush=True)
    return 0 if said["ok"] else 1


def packed_modules() -> dict:
    """What the smoke test does not reach by working, imported, so a module PyInstaller
    missed shows up here and not on a Sunday: the Claude client, the link fetcher, the window."""
    import importlib

    seen = {}
    for name in ("anthropic", "yt_dlp", "huggingface_hub", "webview", "multipart"):
        module = importlib.import_module(name)
        seen[name] = getattr(module, "__version__", None) or "ok"
    import yt_dlp

    with yt_dlp.YoutubeDL({"quiet": True, "skip_download": True}) as fetcher:
        seen["yt_dlp_extractors"] = len(list(fetcher._ies)) or len(yt_dlp.extractor.gen_extractor_classes())
    return seen


def window_check(url: str) -> dict:
    """Open the real window on the app and wait for the interface to draw itself."""
    import webview

    seen: dict = {}
    window = webview.create_window(TITLE, url, width=1200, height=800)

    def look() -> None:
        print("[Preekstof] Rooktest: het venster is er; wachten op het scherm.", flush=True)
        began = time.monotonic()
        while time.monotonic() - began < 60:
            try:
                count = window.evaluate_js("document.querySelector('#root') ? "
                                           "document.querySelector('#root').children.length : -1")
                title = window.evaluate_js("document.title")
                if isinstance(count, int) and count > 0:
                    seen.update(root=count, title=title, seconds=round(time.monotonic() - began, 1))
                    break
            except Exception as exc:  # noqa: BLE001  not loaded yet
                seen["last"] = str(exc)
            time.sleep(0.5)
        print(f"[Preekstof] Rooktest: gezien {seen}; het venster gaat dicht.", flush=True)
        window.destroy()

    webview.start(look, private_mode=True, localization=localization())
    return seen


def main(argv: list[str]) -> int:
    give_output_somewhere()
    no_console_windows()
    # Before the first web request of any kind, the local check on an old lock included:
    # urllib keeps the settings of its first request for every one after it.
    from backend import certificates

    certificates.make_sure()
    if "--smoke" in argv:
        report = Path(argv[argv.index("--report") + 1]) if "--report" in argv else None
        return smoke(report, window="--no-window" not in argv)
    return run()


def leave(code: int) -> None:
    """Go, now. Everything that matters has been stopped and written by then; what is left
    are the window toolkit's own threads, which on a Mac can keep a closed app alive in the
    background, holding on to nothing but still there."""
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.flush()
        except Exception:  # noqa: BLE001
            pass
    os._exit(code)


if __name__ == "__main__":
    # First, before anything: a helper process a library starts (on a Mac, tqdm's lock
    # starts one) is this same program with other arguments. Without this it would start
    # a whole second Preekstof instead of doing its small job.
    import multiprocessing

    multiprocessing.freeze_support()
    leave(main(sys.argv[1:]))
