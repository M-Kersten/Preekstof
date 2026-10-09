"""The zip a church downloads: everything it needs to run, and nothing it does not."""

import json
import stat
import subprocess
import zipfile
from pathlib import Path

import pytest

from backend import updates
from tools import release

# What a volunteer who has never seen a terminal has to be able to double-click, and what
# has to be next to it for that to work.
MUST_BE_IN = (
    "start.bat", "start.command", "launcher.py",
    "backend/main.py", "backend/requirements.txt",
    "frontend/dist/index.html",
    "vision/face.onnx",
    "config.example.env", "LICENSE", "NOTICE", "README.md", "CHANGELOG.md",
)


@pytest.fixture(scope="module")
def built(tmp_path_factory) -> Path:
    return release.build(tmp_path_factory.mktemp("dist"), "9.9.9")


def inside(built: Path) -> list[str]:
    with zipfile.ZipFile(built) as zip_file:
        return [name.partition("/")[2] for name in zip_file.namelist()]


def test_the_file_is_named_after_the_version(built):
    assert built.name == "preekstof-9.9.9.zip"


def test_everything_unpacks_into_one_folder(built):
    """Not forty loose files into whatever folder the download landed in."""
    with zipfile.ZipFile(built) as zip_file:
        tops = {name.partition("/")[0] for name in zip_file.namelist()}
    assert tops == {"preekstof-9.9.9"}


@pytest.mark.parametrize("name", MUST_BE_IN)
def test_what_a_church_needs_is_in_it(built, name):
    assert name in inside(built)


def test_the_interface_is_built_and_in_it(built):
    """A church has no Node, so the built interface travels with the code."""
    assert any(name.startswith("frontend/dist/assets/") for name in inside(built))


def test_the_fonts_travel_along(built):
    assert sum(1 for name in inside(built) if name.startswith("templates/fonts/")) > 10


@pytest.mark.parametrize("name", ["tests/", "docs/", "evaluation/", ".github/"])
def test_what_a_church_has_no_use_for_is_left_out(built, name):
    assert not any(said.startswith(name) for said in inside(built))


def test_the_person_model_is_not_in_it(built):
    """AGPL. It is fetched on the machine that uses it and passed on to nobody."""
    assert "vision/person.onnx" not in inside(built)


def test_no_church_ever_receives_another_church(built):
    """templates/church.json holds a real name and is not tracked; prove it stayed out."""
    assert "templates/church.json" not in inside(built)
    assert not any(name.startswith("templates/brands/") for name in inside(built))


def test_the_start_scripts_come_out_runnable(built):
    """A start.command without the executable bit is a file macOS opens in a text editor."""
    with zipfile.ZipFile(built) as zip_file:
        info = zip_file.getinfo("preekstof-9.9.9/start.command")
    mode = info.external_attr >> 16
    assert mode & 0o111, "nobody can run it"
    # ditto, behind a double-click on a Mac, ignores rights that come without a file type.
    assert stat.S_ISREG(mode) and info.create_system == 3


def test_the_built_interface_is_younger_than_its_source(built):
    """Otherwise the launcher tries to rebuild it, on a machine with no Node."""
    with zipfile.ZipFile(built) as zip_file:
        code = zip_file.getinfo("preekstof-9.9.9/frontend/src/main.tsx").date_time
        page = zip_file.getinfo("preekstof-9.9.9/frontend/dist/index.html").date_time
    assert page > code


def test_the_same_code_gives_the_same_zip(tmp_path):
    """A release that differs run to run cannot be checked against anything."""
    first = release.build(tmp_path / "a", "9.9.9").read_bytes()
    second = release.build(tmp_path / "b", "9.9.9").read_bytes()
    assert first == second


def test_what_git_does_not_track_cannot_end_up_in_a_release():
    kept = release.wanted(["backend/main.py", "tests/test_release.py", "docs/ROADMAP.md",
                           ".github/workflows/tests.yml", "tools/release.py", "tools/ffmpeg/ffmpeg"])
    assert kept == ["backend/main.py", "tools/ffmpeg/ffmpeg"]


def test_the_privacy_page_travels_with_the_app(built):
    """A church council reads the copy that belongs to the version they are running."""
    assert "PRIVACY.md" in inside(built)


def test_the_sentence_the_proof_uses_travels_with_the_app(built):
    """Without it the proof cannot run, and the proof is what a new church presses first."""
    assert "selftest/proef.opus" in inside(built)


# --- the Windows zip, which carries its own Python -------------------------------------


@pytest.fixture(scope="module")
def with_python(tmp_path_factory) -> Path:
    """A stand-in for a prepared embeddable Python, which CI downloads for real."""
    fake = tmp_path_factory.mktemp("winpython")
    (fake / "python.exe").write_bytes(b"MZ")
    (fake / "python312._pth").write_text("python312.zip\n.\nimport site\n", encoding="utf-8")
    (fake / "Lib").mkdir()
    (fake / "Lib" / "site-packages").mkdir()
    (fake / "Lib" / "site-packages" / "marker.txt").write_text("x", encoding="utf-8")
    return release.build(tmp_path_factory.mktemp("dist-win"), "9.9.9", fake)


def test_it_is_named_so_nobody_downloads_the_wrong_one(with_python):
    assert with_python.name == "preekstof-9.9.9-windows.zip"


def test_the_python_travels_inside_the_same_folder(with_python):
    names = inside(with_python)
    assert "python/python.exe" in names
    assert "python/Lib/site-packages/marker.txt" in names, "ook wat dieper zit"


def test_it_is_otherwise_the_same_zip(with_python):
    for name in ("start.bat", "launcher.py", "selftest/proef.opus"):
        assert name in inside(with_python)


def test_the_python_comes_out_runnable(with_python):
    with zipfile.ZipFile(with_python) as zip_file:
        mode = zip_file.getinfo("preekstof-9.9.9/python/python.exe").external_attr >> 16
    assert mode & 0o111


def test_without_one_the_ordinary_zip_has_no_python_folder(built):
    assert not any(name.startswith("python/") for name in inside(built))


def test_start_bat_uses_a_python_that_came_with_the_download():
    """And runs the launcher with it straight away: an embeddable build has no venv."""
    said = (Path(release.ROOT) / "start.bat").read_text(encoding="utf-8")
    assert 'if exist "python\\python.exe"' in said
    assert 'set "RUN=python\\python.exe"' in said
    assert '"%RUN%" launcher.py' in said


def test_start_bat_no_longer_asks_for_a_second_double_click_first():
    """That second action is where a willing church stops, and nobody hears about it."""
    said = (Path(release.ROOT) / "start.bat").read_text(encoding="utf-8")
    assert "LOCALAPPDATA" in said, "er wordt gekeken waar winget het net neerzette"
    assert said.index("goto :restart") > said.index("LOCALAPPDATA"), \
        "opnieuw beginnen is de uitwijk, niet de eerste stap"


def test_batch_files_keep_windows_line_endings():
    """cmd can miss a goto label in a batch file with Unix line endings."""
    for name in ("start.bat", "tools/apply-update.bat"):
        raw = (Path(release.ROOT) / name).read_bytes()
        assert raw.count(b"\r\n") == raw.count(b"\n"), name


def test_start_bat_puts_a_downloaded_update_in_place_from_outside_itself():
    said = (Path(release.ROOT) / "start.bat").read_text(encoding="utf-8")
    assert 'if exist ".update\\ready"' in said
    assert '"%TEMP%\\preekstof-bijwerken.bat"' in said, "cmd cannot overwrite the file it is reading"
    assert 'if "%STATUS%"=="75" goto :again' in said
    update = (Path(release.ROOT) / "tools" / "apply-update.bat").read_text(encoding="utf-8")
    assert "robocopy" in update and "/MOVE" in update
    assert 'move "%APP%\\python" "%APP%\\python.old"' in update, "de Python gaat er in zijn geheel uit"
    assert 'move "%APP%\\python.old" "%APP%\\python"' in update, "en komt terug als het mislukt"
    assert 'start.bat"' in update.splitlines()[-1], "and it starts the new version when it is done"


def test_start_bat_says_so_when_it_runs_from_inside_the_zip():
    said = (Path(release.ROOT) / "start.bat").read_text(encoding="utf-8")
    assert 'if not exist "%~dp0launcher.py"' in said and "Alles uitpakken" in said


def test_start_command_is_read_whole_before_it_runs():
    """An update replaces start.command while bash is reading it."""
    said = (Path(release.ROOT) / "start.command").read_text(encoding="utf-8")
    assert said.rstrip().endswith('main "$@"; exit $?')
    assert "xattr -dr com.apple.quarantine" in said
    assert '[ -x "python/bin/python3" ]' in said


# --- the downloads per computer, with a Python and the packages in it ---------------------


@pytest.fixture(scope="module")
def bundled(tmp_path_factory) -> Path:
    """A stand-in for a prepared Mac Python; CI installs into a real one."""
    fake = tmp_path_factory.mktemp("macpython")
    (fake / "bin").mkdir()
    (fake / "bin" / "python3").write_text("#!/bin/sh\n", encoding="utf-8")
    packages = fake / "lib" / "python3.12" / "site-packages"
    packages.mkdir(parents=True)
    (packages / "marker.txt").write_text("x", encoding="utf-8")
    return release.build(tmp_path_factory.mktemp("dist-mac"), "9.9.9", fake, "mac-arm64",
                         {"av": "18.1.0"})


def test_a_download_per_computer_keeps_its_name_from_version_to_version(bundled):
    """The download page links to releases/latest/download/<name>, and so does the update."""
    assert bundled.name == "Preekstof-Mac.zip"


def test_every_kind_of_computer_has_a_download_name():
    assert set(updates.BUNDLES.values()) == {"Preekstof-Windows.zip", "Preekstof-Mac.zip",
                                             "Preekstof-Mac-Intel.zip"}


def test_it_unpacks_into_a_folder_called_preekstof(bundled):
    with zipfile.ZipFile(bundled) as zip_file:
        assert {name.partition("/")[0] for name in zip_file.namelist()} == {"Preekstof"}


def test_it_says_what_it_is_and_what_it_left_out(bundled):
    with zipfile.ZipFile(bundled) as zip_file:
        said = json.loads(zip_file.read("Preekstof/bundle.json"))
    assert said == {"kind": "mac-arm64", "version": "9.9.9", "fetch": {"av": "18.1.0"}}


def test_the_update_button_recognises_it_once_unpacked(bundled, tmp_path):
    updates.unpack(bundled, tmp_path / "app")
    assert updates.kind(tmp_path / "app") == "mac-arm64"
    assert (tmp_path / "app" / "python" / "bin" / "python3").stat().st_mode & 0o111
    assert (tmp_path / "app" / "python" / "lib" / "python3.12" / "site-packages" / "marker.txt").is_file()


def test_the_checks_and_the_install_page_stay_out_of_every_download(built, bundled):
    for made in (built, bundled):
        names = inside(made)
        assert "tools/check_bundle.py" not in names
        assert not any(name.startswith("site/") for name in names)


def test_preparing_takes_out_what_a_church_fetches_itself(tmp_path, monkeypatch):
    """PyAV carries an FFmpeg built with x264 and x265: fetched there, never handed on."""
    (tmp_path / "bin").mkdir()
    (tmp_path / "bin" / "python3").write_text("", encoding="utf-8")
    (tmp_path / "get-pip.py").write_text("", encoding="utf-8")
    (tmp_path / "Scripts").mkdir()
    (tmp_path / "Scripts" / "uvicorn.exe").write_bytes(b"MZ")
    ran = []

    def fake_run(command, *args, **kwargs):
        ran.append([str(c) for c in command])
        return subprocess.CompletedProcess(command, 0, stdout="18.1.0\n" if "-c" in command else "")

    monkeypatch.setattr(release.subprocess, "run", fake_run)
    assert release.prepare(tmp_path) == {"av": "18.1.0"}
    assert any("--prepare" in c for c in ran), "de launcher installeert, zoals bij een kerk"
    assert any("uninstall" in c and c[-1] == "av" for c in ran)
    assert any("unchecked-hash" in c for c in ran), "anders wordt bij de eerste start alles opnieuw vertaald"
    assert not (tmp_path / "get-pip.py").exists()
    assert not (tmp_path / "Scripts").exists()


def test_a_bundle_needs_a_python_to_go_in_it(tmp_path):
    with pytest.raises(SystemExit):
        release.interpreter(tmp_path)


def test_the_changelog_has_notes_for_the_version_being_released():
    """The release takes its text from this version's heading, and the app shows its first line."""
    said = (Path(release.ROOT) / "CHANGELOG.md").read_text(encoding="utf-8")
    heading = next((line for line in said.splitlines()
                    if line.startswith(f"## {release.version.VERSION}")
                    and not line[len(f"## {release.version.VERSION}"):][:1].isdigit()), None)
    assert heading, f"CHANGELOG.md heeft geen kopje voor {release.version.VERSION}"
    notes = said.split(heading, 1)[1].split("\n## ", 1)[0]
    headline = updates.Release(version=release.version.VERSION, url="", notes=notes).headline()
    assert headline and not headline.startswith("Per versie"), headline


def test_a_mac_download_says_which_macos_it_needs(tmp_path):
    made = release.build(tmp_path, "9.9.9", None, "mac-arm64", {}, "14.0")
    with zipfile.ZipFile(made) as zip_file:
        assert json.loads(zip_file.read("Preekstof/bundle.json"))["macos"] == "14.0"


@pytest.mark.parametrize("said, wanted", [
    ("Load command 1\n      cmd LC_BUILD_VERSION\n platform 1\n    minos 14.0\n      sdk 14.2\n", (14, 0)),
    ("Load command 1\n      cmd LC_VERSION_MIN_MACOSX\n  version 10.9\n      sdk 10.15\n", (10, 9)),
    ("Load command 1\n          cmd LC_ID_DYLIB\n current version 1.2.3\n", None),
])
def test_the_macos_a_binary_needs_is_read_from_its_load_commands(said, wanted):
    """Not from a dylib's own version number, which otool prints just the same."""
    assert release.lowest_macos(said) == wanted


def test_an_intel_download_is_made_with_what_runs_on_an_older_mac(tmp_path, monkeypatch):
    """pip picks for the runner's own macOS unless it is told which one to pick for."""
    (tmp_path / "bin").mkdir()
    (tmp_path / "bin" / "python3").write_text("", encoding="utf-8")
    envs = []

    def fake_run(command, *args, env=None, **kwargs):
        envs.append(env or {})
        said = "/x/lib/python3.12/site-packages\n" if "sysconfig" in " ".join(map(str, command)) else ""
        return subprocess.CompletedProcess(command, 1 if "importlib.metadata" in " ".join(map(str, command)) else 0,
                                           stdout=said)

    monkeypatch.setattr(release.subprocess, "run", fake_run)
    release.prepare(tmp_path, "mac-x64", "12.0")
    installing = next(e for e in envs if e.get("PREEKSTOF_DATA"))
    assert installing["PIP_PLATFORM"] == "macosx_12_0_x86_64"
    assert installing["PIP_ONLY_BINARY"] == ":all:"
    assert installing["PIP_TARGET"] == "/x/lib/python3.12/site-packages"


def test_without_an_older_mac_asked_for_pip_picks_as_usual(tmp_path, monkeypatch):
    (tmp_path / "python.exe").write_bytes(b"MZ")
    envs = []
    monkeypatch.setattr(release.subprocess, "run",
                        lambda command, *a, env=None, **k: envs.append(env or {})
                        or subprocess.CompletedProcess(command, 1, stdout=""))
    release.prepare(tmp_path, "windows-x64", None)
    assert not any("PIP_PLATFORM" in e for e in envs)
