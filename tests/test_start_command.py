"""start.command on a real bash: an update put in place, and a restart that comes back."""

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent

pytestmark = pytest.mark.skipif(sys.platform == "win32" or shutil.which("bash") is None,
                                reason="start.command is for a Mac; bash runs it the same here")

FAKE_PYTHON = """#!/bin/bash
# Stands in for the Python that came with the download. Asks for a restart once.
echo "run $(cat "$(dirname "$0")/../../version.txt")" >> "$(dirname "$0")/../../runs.txt"
if [ ! -f "$(dirname "$0")/../../restarted" ]; then
  touch "$(dirname "$0")/../../restarted"
  exit 75
fi
exit 0
"""


def an_app(folder: Path, version: str) -> None:
    folder.mkdir(parents=True)
    shutil.copy(ROOT / "start.command", folder / "start.command")
    (folder / "launcher.py").write_text("# stand-in\n")
    (folder / "version.txt").write_text(version)
    python = folder / "python" / "bin" / "python3"
    python.parent.mkdir(parents=True)
    python.write_text(FAKE_PYTHON)
    python.chmod(0o755)


def run(app: Path) -> subprocess.CompletedProcess:
    return subprocess.run(["bash", str(app / "start.command")], cwd=app, input="\n",
                          capture_output=True, text=True, timeout=60, env={**os.environ, "HOME": str(app)})


def test_a_restart_asked_for_by_the_app_starts_it_again(tmp_path):
    app = tmp_path / "Preekstof"
    an_app(app, "1")
    done = run(app)
    assert done.returncode == 0, done.stdout + done.stderr
    assert (app / "runs.txt").read_text().splitlines() == ["run 1", "run 1"]


def test_a_downloaded_update_is_put_in_place_before_the_app_starts(tmp_path):
    app = tmp_path / "Preekstof"
    an_app(app, "1")
    staged = tmp_path / "staged"
    an_app(staged, "2")
    (app / ".update").mkdir()
    shutil.copytree(staged, app / ".update" / "new")
    (app / ".update" / "ready").write_text("2")
    done = run(app)
    assert done.returncode == 0, done.stdout + done.stderr
    assert "nieuwe versie" in done.stdout
    assert (app / "version.txt").read_text() == "2"
    assert not (app / ".update").exists()
    assert (app / "runs.txt").read_text().splitlines()[0] == "run 2"


def test_the_python_that_came_with_it_is_swapped_whole_not_merged(tmp_path):
    """Two versions' packages in one folder is a Python nobody can predict."""
    app = tmp_path / "Preekstof"
    an_app(app, "1")
    (app / "python" / "oud.txt").write_text("van de vorige versie")
    staged = tmp_path / "staged"
    an_app(staged, "2")
    (staged / "python" / "nieuw.txt").write_text("van deze versie")
    (app / ".update").mkdir()
    shutil.copytree(staged, app / ".update" / "new")
    (app / ".update" / "ready").write_text("2")
    done = run(app)
    assert done.returncode == 0, done.stdout + done.stderr
    assert (app / "python" / "nieuw.txt").is_file()
    assert not (app / "python" / "oud.txt").exists()
    assert not (app / "python.old").exists()


def test_a_failed_update_gives_the_old_python_back(tmp_path):
    app = tmp_path / "Preekstof"
    an_app(app, "1")
    (app / "python" / "oud.txt").write_text("van de vorige versie")
    staged = tmp_path / "staged"
    an_app(staged, "2")
    (app / ".update").mkdir()
    shutil.copytree(staged, app / ".update" / "new")
    (app / ".update" / "ready").write_text("2")
    # A file in the way of a folder of the same name: cp cannot put the new version in.
    (app / ".update" / "new" / "version.txt").unlink()
    (app / ".update" / "new" / "version.txt").mkdir()
    (app / ".update" / "new" / "version.txt" / "x").write_text("x")
    done = run(app)
    assert "niet gelukt" in done.stdout
    assert (app / "python" / "oud.txt").is_file(), "de oude Python is terug"
    assert (app / "python" / "bin" / "python3").is_file()
    assert not (app / ".update" / "ready").exists(), "en hij probeert het niet bij elke start opnieuw"


def a_mac(tmp_path: Path, version: str) -> dict:
    """A PATH with a sw_vers on it that says which macOS this is."""
    bin_dir = tmp_path / "fakebin"
    bin_dir.mkdir()
    sw_vers = bin_dir / "sw_vers"
    sw_vers.write_text(f"#!/bin/bash\necho {version}\n")
    sw_vers.chmod(0o755)
    return {**os.environ, "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}"}


@pytest.mark.parametrize("have, runs", [("13.6.1", False), ("14.0", True), ("15.2", True)])
def test_a_mac_older_than_the_download_was_built_for_is_told_so(tmp_path, have, runs):
    """Instead of a Python that falls over on a library it cannot load."""
    app = tmp_path / "Preekstof"
    an_app(app, "1")
    (app / "bundle.json").write_text('{"kind": "mac-arm64", "version": "1", "macos": "14.0"}')
    done = subprocess.run(["bash", str(app / "start.command")], cwd=app, input="\n",
                          capture_output=True, text=True, timeout=60,
                          env={**a_mac(tmp_path, have), "HOME": str(app)})
    assert (app / "runs.txt").exists() == runs, done.stdout
    if not runs:
        assert "vraagt macOS 14.0 of nieuwer" in done.stdout and have in done.stdout
        assert "gewone zip" in done.stdout
