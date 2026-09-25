"""Music that ships with the app, next to music a church adds itself.

The library is part of every release and may never be lost in an update or deleted by a
church. A church's own tracks are never overwritten by one. A clip remembers music by file
name only, so a name has to lead to exactly one file.
"""

import json

import pytest
from fastapi.testclient import TestClient

from backend import main, music, renderer
from backend.models import MusicSettings


@pytest.fixture
def folders(tmp_path, monkeypatch):
    own, library = tmp_path / "music", tmp_path / "library" / "music"
    own.mkdir()
    library.mkdir(parents=True)
    monkeypatch.setattr(music, "OWN_DIR", own)
    monkeypatch.setattr(music, "LIBRARY_DIR", library)
    return own, library


def test_the_library_comes_first_in_the_order_it_is_listed(folders):
    own, library = folders
    for name in ("b-lied.mp3", "a-lied.mp3", "zonder-titel.mp3"):
        (library / name).write_bytes(b"x")
    (own / "eigen.mp3").write_bytes(b"x")
    (library / "tracks.json").write_text(json.dumps({"tracks": [
        {"file": "b-lied.mp3", "title": "Stil water", "credit": "Maker (CC BY 4.0)"},
        {"file": "a-lied.mp3", "title": "Morgenlicht"},
        {"file": "weg.mp3", "title": "Staat er niet"},
    ]}), encoding="utf-8")
    tracks = music.everything()
    assert [(t.title, t.library) for t in tracks] == [
        ("Stil water", True), ("Morgenlicht", True), ("zonder titel", True), ("eigen", False)]
    assert tracks[0].credit == "Maker (CC BY 4.0)"
    assert tracks[0].url == "/templates/library/music/b-lied.mp3"
    assert tracks[-1].url == "/templates/music/eigen.mp3"


def test_a_library_without_a_catalogue_still_shows_its_files(folders):
    _own, library = folders
    (library / "rustige_piano-01.mp3").write_bytes(b"x")
    (library / "notities.txt").write_text("geen muziek")
    assert [t.title for t in music.library()] == ["rustige piano 01"]


def test_a_name_leads_to_the_file_wherever_it_lives(folders):
    own, library = folders
    (library / "psalm.mp3").write_bytes(b"x")
    (own / "eigen.mp3").write_bytes(b"x")
    assert music.path_for("psalm.mp3") == library / "psalm.mp3"
    assert music.path_for("eigen.mp3") == own / "eigen.mp3"
    assert music.path_for("../psalm.mp3") == library / "psalm.mp3", "only the name counts"
    assert music.path_for("weg.mp3") is None and music.path_for("") is None


def test_the_render_finds_library_music(folders):
    _own, library = folders
    (library / "psalm.mp3").write_bytes(b"x")
    assert renderer.music_file(MusicSettings(file="psalm.mp3")) == library / "psalm.mp3"


@pytest.fixture
def client(folders):
    with TestClient(main.app) as running:
        yield running


def test_the_list_says_which_is_which(client, folders):
    own, library = folders
    (library / "psalm.mp3").write_bytes(b"x")
    (own / "eigen.mp3").write_bytes(b"x")
    rows = client.get("/music").json()
    assert [(r["file"], r["library"]) for r in rows] == [("psalm.mp3", True), ("eigen.mp3", False)]


def test_an_upload_cannot_take_a_library_name(client, folders):
    _own, library = folders
    (library / "psalm.mp3").write_bytes(b"x")
    answer = client.post("/music", files={"file": ("psalm.mp3", b"mine", "audio/mpeg")})
    assert answer.status_code == 400 and "standaardbibliotheek" in answer.json()["detail"]
    assert (library / "psalm.mp3").read_bytes() == b"x"


def test_an_upload_lands_with_the_churchs_own(client, folders):
    own, _library = folders
    answer = client.post("/music", files={"file": ("eigen.mp3", b"mine", "audio/mpeg")})
    assert answer.status_code == 200
    assert (own / "eigen.mp3").read_bytes() == b"mine"


def test_the_library_cannot_be_thrown_away(client, folders):
    own, library = folders
    (library / "psalm.mp3").write_bytes(b"x")
    (own / "eigen.mp3").write_bytes(b"x")
    assert client.delete("/music/psalm.mp3").status_code == 400
    assert (library / "psalm.mp3").is_file()
    assert client.delete("/music/eigen.mp3").status_code == 200
    assert not (own / "eigen.mp3").exists()


def test_the_library_ships_with_the_app():
    """Tracked, not ignored: a release is built from what git has."""
    import subprocess

    ignored = subprocess.run(["git", "check-ignore", "-q", "templates/library/music/tracks.json"],
                             cwd=main.ROOT).returncode == 0
    assert not ignored
    catalogue = json.loads((main.ROOT / "templates" / "library" / "music" / "tracks.json").read_text("utf-8"))
    assert isinstance(catalogue["tracks"], list)


@pytest.mark.parametrize("path, tracked", [
    ("templates/library/music/lied.mp3", True),
    ("templates/library/music/lied.wav", True),
    ("templates/music/lied.mp3", False),
])
def test_library_audio_is_tracked_even_when_a_global_gitignore_says_otherwise(tmp_path, path, tracked):
    """Many machines ignore *.mp3 everywhere. The library must still reach the repository."""
    import subprocess

    everywhere = tmp_path / "global-ignore"
    everywhere.write_text("*.mp3\n*.wav\n")
    said = subprocess.run(["git", "-c", f"core.excludesFile={everywhere}", "check-ignore", "--no-index",
                           "--non-matching", "-v", path], cwd=main.ROOT, capture_output=True, text=True)
    rule = said.stdout.split("\t")[0]
    ignored = bool(rule.strip(": ")) and not rule.split(":")[-1].startswith("!")
    assert ignored is not tracked, said.stdout
