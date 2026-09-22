"""Fetching a service from a link, through the endpoint a volunteer actually presses."""

import time
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend import fetch, main, models
from backend.jobs import Cancelled


@pytest.fixture
def client(tmp_path, monkeypatch):
    """A services tree of its own, so a test never touches real recordings."""
    folder = tmp_path / "services"
    folder.mkdir()
    monkeypatch.setattr(models, "SERVICES_DIR", folder)
    monkeypatch.setattr(main, "SERVICES_DIR", folder, raising=False)
    with TestClient(main.app) as running:
        yield running


def settle(client: TestClient, sid: str, tries: int = 100) -> dict:
    """Wait for the fetch job to be over, whichever way it ends."""
    for _ in range(tries):
        state = client.get(f"/services/{sid}/status").json()
        if state["status"] != "fetching":
            return client.get(f"/services/{sid}").json()
        time.sleep(0.05)
    raise AssertionError("the fetch never finished")


def a_recording(folder: Path) -> Path:
    written = folder / "source.mp4"
    written.write_bytes(b"not really a video")
    return written


def came_in(folder: Path, title: str, preacher: str = "", poster: bytes | None = None):
    """What fetch.fetch hands back: the file, plus what the source knew about it."""
    kept = None
    if poster is not None:
        kept = folder / "poster.jpg"
        kept.write_bytes(poster)
    return fetch.Grabbed(file=a_recording(folder), title=title, preacher=preacher, poster=kept)


def test_a_link_becomes_the_recording_of_this_service(client, monkeypatch):
    monkeypatch.setattr(fetch, "fetch", lambda url, folder, *a, **k: came_in(
        folder, "Kerkdienst 30 augustus", "ds. M. Kreuk", b"\xff\xd8pretend jpeg"))
    monkeypatch.setattr(main.renderer, "probe", lambda path: models.VideoInfo(
        width=1920, height=1080, duration=3600, fps=25, videoCodec="h264",
        hasAudio=True, audioCodec="aac", audioSampleRate=48000, audioChannels=2))

    sid = client.post("/services").json()["id"]
    started = client.post(f"/services/{sid}/link", json={"url": "https://youtu.be/abc"})
    assert started.status_code == 200
    assert started.json()["status"] == "fetching"

    done = settle(client, sid)
    assert done["status"] == "uploaded"
    assert done["title"] == "Kerkdienst 30 augustus", "the recording brings its own name"
    assert done["sourceVideo"] == "source.mp4"
    assert done["sourceInfo"]["duration"] == 3600
    assert done["preacher"] == "ds. M. Kreuk", "the church already typed this once"
    assert done["posterUrl"] == f"/services/{sid}/poster"

    picture = client.get(f"/services/{sid}/poster")
    assert picture.status_code == 200
    assert picture.content == b"\xff\xd8pretend jpeg"


def test_a_service_the_platform_knew_nothing_extra_about_still_works(client, monkeypatch):
    """Most links are not Kerkdienstgemist, and a plain mp4 carries neither of these."""
    monkeypatch.setattr(fetch, "fetch", lambda url, folder, *a, **k: came_in(folder, "Dienst"))
    monkeypatch.setattr(main.renderer, "probe", lambda path: models.VideoInfo(
        width=1920, height=1080, duration=3600, fps=25, videoCodec="h264",
        hasAudio=True, audioCodec="aac", audioSampleRate=48000, audioChannels=2))

    sid = client.post("/services").json()["id"]
    client.post(f"/services/{sid}/link", json={"url": "https://youtu.be/abc"})
    done = settle(client, sid)
    assert done["status"] == "uploaded"
    assert done["preacher"] == ""
    assert done["posterUrl"] is None
    assert client.get(f"/services/{sid}/poster").status_code == 404


def test_a_second_recording_does_not_keep_the_first_one_s_preacher(client, monkeypatch):
    """Otherwise a dragged-in file inherits whoever preached the last time."""
    monkeypatch.setattr(main.renderer, "probe", lambda path: models.VideoInfo(
        width=1920, height=1080, duration=3600, fps=25, videoCodec="h264",
        hasAudio=True, audioCodec="aac", audioSampleRate=48000, audioChannels=2))

    monkeypatch.setattr(fetch, "fetch", lambda url, folder, *a, **k: came_in(
        folder, "Eerste", "ds. M. Kreuk", b"\xff\xd8first"))
    sid = client.post("/services").json()["id"]
    client.post(f"/services/{sid}/link", json={"url": "https://youtu.be/abc"})
    assert settle(client, sid)["preacher"] == "ds. M. Kreuk"

    monkeypatch.setattr(fetch, "fetch", lambda url, folder, *a, **k: came_in(folder, "Tweede"))
    client.post(f"/services/{sid}/link", json={"url": "https://youtu.be/def"})
    done = settle(client, sid)
    assert done["preacher"] == ""
    assert done["posterUrl"] is None
    assert not list((models.service_dir(sid)).glob("poster.*")), "the old picture went too"


def test_something_that_is_not_an_address_is_refused_before_any_work_starts(client, monkeypatch):
    called = []
    monkeypatch.setattr(fetch, "fetch", lambda *a, **k: called.append(1))
    sid = client.post("/services").json()["id"]
    answer = client.post(f"/services/{sid}/link", json={"url": "de dienst van vorige week"})
    assert answer.status_code == 400
    assert "webadres" in answer.json()["detail"]
    assert called == [], "nothing is downloaded for a link that cannot be one"


def test_a_link_that_does_not_work_leaves_a_message_you_can_act_on(client, monkeypatch):
    def refuse(url, folder, *a, **k):
        raise fetch.LinkNotUsable("Op dit adres staat niets (meer). Controleer de link.")

    monkeypatch.setattr(fetch, "fetch", refuse)
    sid = client.post("/services").json()["id"]
    client.post(f"/services/{sid}/link", json={"url": "https://kerk.nl/weg"})
    done = settle(client, sid)
    assert done["status"] == "error"
    assert "Controleer de link" in done["error"]
    assert done["sourceVideo"] is None


def test_a_download_without_sound_is_not_kept(client, monkeypatch):
    """There is nothing to write out, and a silent file would only take up room."""
    monkeypatch.setattr(fetch, "fetch", lambda url, folder, *a, **k: came_in(folder, "Stil"))
    monkeypatch.setattr(main.renderer, "probe", lambda path: models.VideoInfo(
        width=1920, height=1080, duration=60, fps=25, videoCodec="h264",
        hasAudio=False, audioCodec="", audioSampleRate=0, audioChannels=0))

    sid = client.post("/services").json()["id"]
    client.post(f"/services/{sid}/link", json={"url": "https://youtu.be/abc"})
    done = settle(client, sid)
    assert done["status"] == "error"
    assert "geluid" in done["error"]
    assert not (models.service_dir(sid) / "source.mp4").exists()


def test_stopping_a_fetch_puts_the_service_back_where_it_was(client, monkeypatch):
    def give_up(url, folder, *a, **k):
        raise Cancelled()

    monkeypatch.setattr(fetch, "fetch", give_up)
    sid = client.post("/services").json()["id"]
    client.post(f"/services/{sid}/link", json={"url": "https://youtu.be/abc"})
    done = settle(client, sid)
    assert done["status"] == "created", "not an error: the user asked for it"
    assert done["error"] is None
