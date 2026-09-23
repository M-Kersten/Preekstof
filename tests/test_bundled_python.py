"""The Python the Windows release brings with it, and the two things it cannot do alone.

An embeddable build ships without pip, and its ._pth file replaces sys.path outright, so
neither site-packages nor the app's own folder is on it. Both have to be dealt with or the
first double-click ends in an import error a volunteer cannot read.
"""

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
    monkeypatch.setattr(launcher.subprocess, "run",
                        lambda cmd, *a, **k: order.append("install") or
                        subprocess.CompletedProcess(cmd, 0))
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


def test_the_bootstrap_travels_with_it():
    assert "get-pip.py" in WORKFLOW.read_text(encoding="utf-8")


def test_the_path_file_is_named_after_the_version_it_ships():
    """python312._pth beside python 3.12; a mismatched name is ignored in silence."""
    said = WORKFLOW.read_text(encoding="utf-8")
    assert 'cut -d. -f1,2' in said and 'winpython/python${short}._pth' in said
