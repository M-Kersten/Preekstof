"""Refusing the job that cannot finish, before it writes anything."""

import pytest
from fastapi.testclient import TestClient

from backend import main, models, room
from backend.models import ClipCandidate, Service, VideoInfo


def with_free(monkeypatch, free_gb: float):
    class Disk:
        total, used, free = int(500e9), int(500e9 - free_gb * 1e9), int(free_gb * 1e9)

    monkeypatch.setattr(room.shutil, "disk_usage", lambda *_: Disk)


# --- what a job costs ---------------------------------------------------------------


def test_writing_out_a_service_costs_about_what_the_wav_weighs():
    """Measured: 32 kB a second, and this rounds up."""
    assert 200e6 < room.for_transcribing(5400) < 250e6


def test_more_clips_cost_more_room():
    assert room.for_clips(60, 4) > room.for_clips(60, 1)


def test_a_longer_clip_costs_more_room():
    assert room.for_clips(120, 1) > room.for_clips(60, 1)


@pytest.mark.parametrize("seconds", [0, -5])
def test_a_length_that_makes_no_sense_costs_nothing_rather_than_crashing(seconds):
    assert room.for_transcribing(seconds) == 0


# --- the floor ------------------------------------------------------------------------


def test_a_job_that_fits_with_room_to_spare_goes_ahead(monkeypatch):
    with_free(monkeypatch, 20)
    assert room.check(int(1e9), "Uitschrijven").enough


def test_a_job_that_fits_but_leaves_nothing_behind_is_refused(monkeypatch):
    """Windows misbehaves well before zero, and a full disk cannot write the log saying so."""
    with_free(monkeypatch, 1.2)
    with pytest.raises(room.NotEnoughRoom):
        room.check(int(1e9), "Uitschrijven")


def test_the_message_names_both_numbers_and_the_shortfall(monkeypatch):
    with_free(monkeypatch, 2)
    monkeypatch.setattr(room, "recoverable", lambda: 0)
    with pytest.raises(room.NotEnoughRoom) as caught:
        room.check(int(4e9), "Uitschrijven")
    said = str(caught.value)
    assert "Uitschrijven" in said
    assert "4,0 GB nodig" in said
    assert "2,0 GB vrij" in said
    assert "3,0 GB te weinig" in said


def test_it_points_at_what_is_standing_by_to_be_thrown_away(monkeypatch):
    with_free(monkeypatch, 2)
    monkeypatch.setattr(room, "recoverable", lambda: int(8e9))
    with pytest.raises(room.NotEnoughRoom) as caught:
        room.check(int(4e9), "Uitschrijven")
    assert "Ruimte vrijmaken" in str(caught.value)
    assert "8,0 GB" in str(caught.value)


def test_with_nothing_to_clean_up_it_says_something_useful_anyway(monkeypatch):
    with_free(monkeypatch, 0.5)
    monkeypatch.setattr(room, "recoverable", lambda: int(10e6))
    with pytest.raises(room.NotEnoughRoom) as caught:
        room.check(int(4e9), "Uitschrijven")
    assert "Maak ruimte vrij" in str(caught.value)


def test_a_survey_that_falls_over_does_not_take_the_message_with_it(monkeypatch):
    with_free(monkeypatch, 0.5)
    monkeypatch.setattr("backend.storage.survey", lambda: (_ for _ in ()).throw(OSError()))
    with pytest.raises(room.NotEnoughRoom):
        room.check(int(4e9), "Uitschrijven")


@pytest.mark.parametrize("size, said", [
    (int(4.2e9), "4,2 GB"), (int(300e6), "300 MB"), (1000, "1 MB"), (0, "1 MB"),
])
def test_sizes_are_said_the_way_somebody_would_say_them(size, said):
    assert room.gb(size) == said


# --- through the endpoints a volunteer presses ------------------------------------------


@pytest.fixture
def client(tmp_path, monkeypatch):
    folder = tmp_path / "services"
    folder.mkdir()
    monkeypatch.setattr(models, "SERVICES_DIR", folder)
    monkeypatch.setattr(main, "SERVICES_DIR", folder, raising=False)
    with TestClient(main.app) as running:
        yield running


def a_service(sid="service-1", *, duration=5400.0, chosen=0) -> Service:
    (models.SERVICES_DIR / sid / "work").mkdir(parents=True, exist_ok=True)
    service = Service(id=sid, createdAt="2026-09-06T10:00:00+00:00", title="Kerkdienst",
                      sourceVideo="source.mp4", status="uploaded",
                      sourceInfo=VideoInfo(width=1920, height=1080, duration=duration, fps=25,
                                           videoCodec="h264", hasAudio=True, audioCodec="aac",
                                           audioSampleRate=48000, audioChannels=2))
    service.candidates = [ClipCandidate(id=f"c{i}", start=i * 100, end=i * 100 + 60,
                                        title=f"m{i}", selected=i < chosen)
                          for i in range(6)]
    (models.SERVICES_DIR / sid / "source.mp4").write_bytes(b"x")
    models.save_service(service)
    return service


def test_writing_out_is_refused_on_a_full_disk_before_anything_runs(client, monkeypatch):
    a_service()
    with_free(monkeypatch, 0.3)
    answer = client.post("/services/service-1/transcribe")
    assert answer.status_code == 507
    assert "Uitschrijven" in answer.json()["detail"]
    assert models.load_service("service-1").status == "uploaded", "niets begonnen"


def test_writing_out_goes_ahead_when_there_is_room(client, monkeypatch):
    a_service()
    with_free(monkeypatch, 50)
    monkeypatch.setattr(main.transcription, "transcribe",
                        lambda *a, **k: models.Transcript(language="nl", segments=[]))
    assert client.post("/services/service-1/transcribe").status_code == 200


def test_making_clips_is_refused_on_a_full_disk(client, monkeypatch):
    a_service(chosen=3)
    with_free(monkeypatch, 0.4)
    answer = client.post("/services/service-1/process-selected")
    assert answer.status_code == 507
    assert "3 fragmenten" in answer.json()["detail"]


def test_one_chosen_fragment_is_said_in_the_singular(client, monkeypatch):
    a_service(chosen=1)
    with_free(monkeypatch, 0.4)
    assert "1 fragment " in client.post("/services/service-1/process-selected").json()["detail"]


def test_fetching_a_recording_is_refused_when_a_service_could_never_fit(client, monkeypatch):
    a_service()
    with_free(monkeypatch, 0.5)
    answer = client.post("/services/service-1/link", json={"url": "https://youtu.be/abc"})
    assert answer.status_code == 507
    assert "dienst ophalen" in answer.json()["detail"].lower()


# --- one machine, one piece of hard work ------------------------------------------------


def test_a_second_service_waits_for_the_first(client, monkeypatch):
    """Two tabs on a computer that manages one makes both crawl and neither says why."""
    a_service("service-1")
    a_service("service-2")
    with_free(monkeypatch, 50)
    monkeypatch.setattr(main.jobs, "busy_with", lambda unless="": "service-1")
    answer = client.post("/services/service-2/transcribe")
    assert answer.status_code == 409
    assert "al een dienst bezig" in answer.json()["detail"]


def test_the_proof_waits_for_a_service_too(client, monkeypatch):
    """It uses the same speech model and the same encoder."""
    monkeypatch.setattr(main.jobs, "busy_with", lambda unless="": "service-1")
    answer = client.post("/selftest")
    assert answer.status_code == 409
    assert "dienst bezig" in answer.json()["detail"]


def test_only_heavy_work_counts(client):
    """Saving a subtitle or fetching a list never has to wait for anything."""
    from backend.jobs import JobManager

    manager = JobManager()
    manager.start("iets-lichts", lambda job: None)
    assert manager.busy_with() is None, "wat niet zwaar is telt niet mee"


def test_a_job_does_not_block_itself(client):
    from backend.jobs import JobManager
    import threading

    manager = JobManager()
    manager.mark_heavy("service-1")
    hold = threading.Event()
    manager.start("service-1", lambda job: hold.wait(2))
    try:
        assert manager.busy_with(unless="service-1") is None
        assert manager.busy_with() == "service-1"
    finally:
        hold.set()
