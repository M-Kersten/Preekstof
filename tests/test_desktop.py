"""The desktop app (desktop/app.py): what can be checked without a screen.

The window itself is checked where there is one, on the Mac and Windows runners of the
release workflow (desktop/build.py --smoke). This is everything around it.
"""

import importlib
import json
import socket
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "desktop"))

import app as desktop  # noqa: E402  desktop/app.py

from backend import jobs as jobs_module  # noqa: E402
from backend import places, updates  # noqa: E402


# --- one app at a time --------------------------------------------------------------------


def test_no_lock_means_no_other_app(tmp_path):
    assert desktop.Lock(tmp_path).other() is None


def test_a_lock_left_by_a_crash_is_not_another_app(tmp_path):
    (tmp_path / ".desktop.json").write_text(json.dumps({"pid": 999999, "port": 1}))
    assert desktop.Lock(tmp_path).other() is None, "niets antwoordt op die poort"


def test_the_lock_is_ours_to_release_and_nobody_elses(tmp_path):
    lock = desktop.Lock(tmp_path)
    lock.take(8765)
    assert json.loads(lock.path.read_text())["port"] == 8765
    lock.release()
    assert not lock.path.exists()
    lock.path.write_text(json.dumps({"pid": 999999, "port": 8765}))
    lock.release()
    assert lock.path.exists(), "een ander zijn slot blijft liggen"


def test_the_port_stays_the_same_while_it_is_free(monkeypatch):
    """The interface remembers settings per address; a new port each time forgets them."""
    monkeypatch.delenv("PREEKSTOF_PORT", raising=False)
    first = desktop.pick_port()
    assert first == desktop.pick_port() and first in desktop.PORTS


def test_a_taken_port_moves_on_to_the_next(monkeypatch):
    monkeypatch.delenv("PREEKSTOF_PORT", raising=False)
    first = desktop.pick_port()
    with socket.socket() as taken:
        taken.bind(("127.0.0.1", first))
        taken.listen()
        assert desktop.pick_port() != first


def test_something_else_on_a_port_is_not_preekstof():
    with socket.socket() as other:
        other.bind(("127.0.0.1", 0))
        other.listen()
        assert not desktop.answers(other.getsockname()[1], timeout=0.5)


# --- the pages it shows itself --------------------------------------------------------------


def test_trouble_is_said_in_dutch_with_the_log_to_send(tmp_path):
    page = desktop.trouble_page("De app kon niet starten: <poort>", tmp_path / "preekstof.log")
    assert "Preekstof kon niet starten" in page and "&lt;poort&gt;" in page
    assert "preekstof.log" in page


def test_starting_and_already_open_pages_are_whole_pages():
    for page in (desktop.starting_page(), desktop.already_open_page()):
        assert page.startswith("<!doctype html>") and "</html>" in page


# --- stopping when the window closes ----------------------------------------------------------


def test_closing_stops_what_is_running():
    manager = jobs_module.JobManager()

    def work(job):
        while True:
            job.check()
            time.sleep(0.01)

    manager.start("dienst", work)
    assert manager.running() == ["dienst"]
    assert manager.cancel_all() == ["dienst"]
    for _ in range(200):
        if not manager.running():
            break
        time.sleep(0.01)
    assert manager.get("dienst").status == "cancelled"


# --- the backend inside a packed app ------------------------------------------------------------


def test_the_packed_app_keeps_the_person_model_with_the_churchs_work(monkeypatch):
    from backend import vision

    monkeypatch.setattr(places, "FROZEN", True)
    try:
        packed = importlib.reload(vision)
        assert packed.PERSON_MODEL.parent == places.DATA / "vision"
        assert packed.FACE_MODEL.parent == places.ROOT / "vision", "het gezichtsmodel komt mee met de app"
    finally:
        monkeypatch.setattr(places, "FROZEN", False)
        importlib.reload(vision)


def test_the_packed_app_is_updated_by_its_installer_not_by_the_button(monkeypatch):
    monkeypatch.setattr(places, "FROZEN", True)
    release = updates.Release(version="99.0.0", url="https://example.org",
                              assets=[updates.Asset("Preekstof-Mac.zip", "https://example.org/x")])
    assert updates.kind() == "desktop"
    assert updates.asset_for(release) is None
    assert "installeer" in updates.why_not(release)


def test_the_stand_in_for_pyav_imports_and_refuses_to_open_anything():
    sys.path.insert(0, str(ROOT / "desktop" / "stubs"))
    try:
        sys.modules.pop("av", None)
        stand_in = importlib.import_module("av")
        assert Path(stand_in.__file__).parent.parent == ROOT / "desktop" / "stubs"
        with pytest.raises(RuntimeError):
            stand_in.open("dienst.wav")
    finally:
        sys.path.remove(str(ROOT / "desktop" / "stubs"))
        sys.modules.pop("av", None)


def test_the_desktop_folder_stays_out_of_the_zips():
    from tools import release

    assert release.wanted(["desktop/app.py", "backend/main.py"]) == ["backend/main.py"]


def test_the_windows_build_files_keep_windows_line_endings():
    for name in ("desktop/installer.iss", "desktop/build-windows.ps1"):
        raw = (ROOT / name).read_bytes()
        assert raw.count(b"\r\n") == raw.count(b"\n"), name


class FakeWindow:
    """A window that, like WKWebView on a quick start, can end up back on the starting page."""

    def __init__(self, landings):
        import threading
        from types import SimpleNamespace

        self.landings = list(landings)
        self.asked: list[str] = []
        self.now = "about:blank"
        loaded = threading.Event()
        loaded.set()
        self.events = SimpleNamespace(loaded=loaded)

    def load_url(self, url):
        self.asked.append(url)
        self.now = self.landings.pop(0) if self.landings else url

    def get_current_url(self):
        return self.now


def test_the_app_is_shown_even_when_the_starting_page_wins_the_race(monkeypatch):
    monkeypatch.setattr(desktop.time, "sleep", lambda _s: None)
    window = FakeWindow(["about:blank", "http://127.0.0.1:8766/"])
    desktop.show_the_app(window, "http://127.0.0.1:8766")
    assert window.asked == ["http://127.0.0.1:8766"] * 2
    assert window.now.startswith("http://127.0.0.1:8766")


def test_once_there_it_asks_no_more(monkeypatch):
    monkeypatch.setattr(desktop.time, "sleep", lambda _s: None)
    window = FakeWindow(["http://127.0.0.1:8766/"])
    desktop.show_the_app(window, "http://127.0.0.1:8766")
    assert len(window.asked) == 1
