"""The zip a church downloads: everything it needs to run, and nothing it does not."""

import zipfile
from pathlib import Path

import pytest

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
        mode = zip_file.getinfo("preekstof-9.9.9/start.command").external_attr >> 16
    assert mode & 0o111, "nobody can run it"


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
    assert '"python\\python.exe" launcher.py' in said


def test_start_bat_no_longer_asks_for_a_second_double_click_first():
    """That second action is where a willing church stops, and nobody hears about it."""
    said = (Path(release.ROOT) / "start.bat").read_text(encoding="utf-8")
    assert "LOCALAPPDATA" in said, "er wordt gekeken waar winget het net neerzette"
    assert said.index("goto :restart") > said.index("LOCALAPPDATA"), \
        "opnieuw beginnen is de uitwijk, niet de eerste stap"
