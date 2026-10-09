"""The Python the Windows release brings with it, and the two things it cannot do alone.

An embeddable build ships without pip, and its ._pth file replaces sys.path outright, so
neither site-packages nor the app's own folder is on it. Both have to be dealt with or the
first double-click ends in an import error a volunteer cannot read.
"""

import json
import subprocess
import sys
from pathlib import Path

import pytest

import launcher

WORKFLOW = Path(__file__).resolve().parent.parent / ".github" / "workflows" / "release.yml"


# --- giving itself an installer -------------------------------------------------------


def test_a_python_that_already_has_pip_is_left_alone(monkeypatch):
    monkeypatch.setattr(launcher.subprocess, "run",
                        lambda *a, **k: pytest.fail("er hoeft niets opgezet te worden"))
    launcher.ensure_pip()  # this interpreter has pip


def test_a_python_without_pip_runs_the_bootstrap_beside_it(tmp_path, monkeypatch):
    (tmp_path / "get-pip.py").write_text("# net alsof", encoding="utf-8")
    monkeypatch.setattr(launcher.importlib.util, "find_spec", lambda _name: None)
    monkeypatch.setattr(launcher.sys, "executable", str(tmp_path / "python.exe"))
    ran = []

    def note(cmd, *a, **k):
        ran.append(cmd)
        return subprocess.CompletedProcess(cmd, 0)

    monkeypatch.setattr(launcher.subprocess, "run", note)
    launcher.ensure_pip()
    assert ran and str(tmp_path / "get-pip.py") in ran[0]


def test_a_bootstrap_that_fails_stops_with_something_readable(tmp_path, monkeypatch):
    (tmp_path / "get-pip.py").write_text("# net alsof", encoding="utf-8")
    monkeypatch.setattr(launcher.importlib.util, "find_spec", lambda _name: None)
    monkeypatch.setattr(launcher.sys, "executable", str(tmp_path / "python.exe"))
    monkeypatch.setattr(launcher.subprocess, "run",
                        lambda cmd, *a, **k: subprocess.CompletedProcess(cmd, 1))
    with pytest.raises(SystemExit) as caught:
        launcher.ensure_pip()
    assert "internetverbinding" in str(caught.value)


def test_no_pip_and_no_bootstrap_says_what_to_do(tmp_path, monkeypatch):
    monkeypatch.setattr(launcher.importlib.util, "find_spec", lambda _name: None)
    monkeypatch.setattr(launcher.sys, "executable", str(tmp_path / "python.exe"))
    with pytest.raises(SystemExit) as caught:
        launcher.ensure_pip()
    assert "python.org" in str(caught.value)


def test_installing_the_packages_asks_for_pip_first(tmp_path, monkeypatch):
    """Otherwise the very first thing a church's own Python does is fail on "no module pip"."""
    order = []
    monkeypatch.setattr(launcher, "ensure_pip", lambda: order.append("pip"))
    monkeypatch.setattr(launcher, "INSTALLED_STAMP", tmp_path / "nergens")
    monkeypatch.setattr(launcher, "quietly", lambda cmd, doing: order.append("install") or True)
    launcher.ensure_requirements()
    assert order[:2] == ["pip", "install"]


# --- and the path file it needs -------------------------------------------------------


def test_the_workflow_writes_the_path_file_rather_than_patching_it():
    """Both lines have to be added, so what the shipped file said does not matter."""
    said = WORKFLOW.read_text(encoding="utf-8")
    assert "._pth" in said
    assert "sed -i" not in said, "een ._pth bijwerken met sed raakt de helft niet"


@pytest.mark.parametrize("line, why", [
    ("..", "het app-pad, anders vindt hij backend niet"),
    ("import site", "anders heeft pip nergens om te installeren"),
])
def test_the_path_file_carries_what_the_app_needs(line, why):
    said = WORKFLOW.read_text(encoding="utf-8")
    assert line in said, why


def test_pip_is_put_in_while_the_download_is_built():
    """So the church's computer has it, for what the download leaves out (below)."""
    said = WORKFLOW.read_text(encoding="utf-8")
    assert "python/python.exe python/get-pip.py" in said


def test_the_path_file_is_named_after_the_version_it_ships():
    """python312._pth beside python 3.12; a mismatched name is ignored in silence."""
    said = WORKFLOW.read_text(encoding="utf-8")
    assert 'cut -d. -f1,2' in said and 'python/python${short}._pth' in said


# --- what a download leaves out on purpose ------------------------------------------------


def a_bundle(tmp_path, monkeypatch, fetch) -> None:
    note = tmp_path / "bundle.json"
    note.write_text(json.dumps({"kind": "windows-x64", "version": "9.9.9", "fetch": fetch}),
                    encoding="utf-8")
    monkeypatch.setattr(launcher, "BUNDLE", note)


def test_no_note_means_nothing_was_left_out(tmp_path, monkeypatch):
    """The plain zip and a git checkout install everything themselves."""
    monkeypatch.setattr(launcher, "BUNDLE", tmp_path / "nergens.json")
    assert launcher.left_out() == {}


def test_what_is_already_here_is_not_fetched_again(tmp_path, monkeypatch):
    a_bundle(tmp_path, monkeypatch, {"json": "1.0"})
    assert launcher.left_out() == {}


def test_what_was_left_out_is_fetched_at_the_version_the_rest_was_installed_with(tmp_path, monkeypatch):
    a_bundle(tmp_path, monkeypatch, {"geen_pakket_van_ons": "18.1.0"})
    monkeypatch.setattr(launcher, "ensure_pip", lambda: None)
    ran = []
    monkeypatch.setattr(launcher, "quietly", lambda cmd, doing: ran.append(cmd) or True)
    launcher.fetch_left_out()
    assert len(ran) == 1
    assert "geen_pakket_van_ons==18.1.0" in ran[0] and "--no-deps" in ran[0]


def test_a_download_with_everything_installed_still_fetches_what_it_left_out(tmp_path, monkeypatch):
    stamp = tmp_path / "requirements.installed"
    stamp.write_text(launcher.REQUIREMENTS.read_text(encoding="utf-8"), encoding="utf-8")
    monkeypatch.setattr(launcher, "INSTALLED_STAMP", stamp)
    a_bundle(tmp_path, monkeypatch, {"geen_pakket_van_ons": "1.0"})
    monkeypatch.setattr(launcher, "ensure_pip", lambda: None)
    ran = []
    monkeypatch.setattr(launcher, "quietly", lambda cmd, doing: ran.append(cmd) or True)
    launcher.ensure_requirements()
    assert len(ran) == 1, "alleen dat ene onderdeel, niet alles opnieuw"
    assert "-r" not in ran[0]


def test_fetching_it_without_internet_says_so(tmp_path, monkeypatch):
    a_bundle(tmp_path, monkeypatch, {"geen_pakket_van_ons": "1.0"})
    monkeypatch.setattr(launcher, "ensure_pip", lambda: None)
    monkeypatch.setattr(launcher, "quietly", lambda cmd, doing: False)
    with pytest.raises(SystemExit) as caught:
        launcher.fetch_left_out()
    assert "internetverbinding" in str(caught.value)
