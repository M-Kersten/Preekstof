"""Reading a service to find the moments, and writing out the clips people actually read.

The whole service used to be transcribed once, carefully, and the clips were slices of that.
Almost all of that careful listening went to minutes nobody ever posts. Now the service is
scanned greedily and each chosen clip is heard again properly, over half a minute instead of
an hour and a half.
"""

import pytest
from fastapi.testclient import TestClient

from backend import clips, main, models, transcription
from backend.models import (ClipCandidate, ClipOrigin, Output, Project, Segment, Service,
                            Transcript, VideoInfo)


@pytest.fixture
def client(tmp_path, monkeypatch):
    for name in ("PROJECTS_DIR", "SERVICES_DIR"):
        folder = tmp_path / name.lower()
        folder.mkdir()
        monkeypatch.setattr(models, name, folder)
    monkeypatch.setattr(main, "SERVICES_DIR", tmp_path / "services_dir")
    with TestClient(main.app) as running:
        yield running


def a_recording() -> VideoInfo:
    return VideoInfo(width=1920, height=1080, duration=5400.0, fps=25.0, videoCodec="h264",
                     hasAudio=True, audioCodec="aac", audioSampleRate=48000, audioChannels=2)


def a_service(sid: str = "dienst", accurate: bool = False) -> Service:
    models.service_dir(sid).mkdir(parents=True, exist_ok=True)
    (models.service_dir(sid) / "source.mp4").write_bytes(b"not really a video")
    service = Service(id=sid, createdAt="2026-01-01T10:00:00", title="Kerkdienst",
                      status="ready", sourceVideo="source.mp4", sourceInfo=a_recording(),
                      accurate=accurate)
    service.candidates = [
        ClipCandidate(id="c1", start=1200.0, end=1240.0, title="Het midden", score=0.9,
                      reason="x", selected=True, shortlisted=True),
    ]
    models.save_service(service)
    models.save_service_transcript(service, Transcript(language="nl", segments=[
        Segment(start=1200.0, end=1210.0, text="ruwe tekst uit de scan"),
        Segment(start=1210.0, end=1240.0, text="nog wat ruwe tekst"),
    ]))
    return models.load_service(sid)


def a_clip(pid: str = "clip", sound: bool = True) -> Project:
    models.project_dir(pid).mkdir(parents=True, exist_ok=True)
    project = Project(
        id=pid, createdAt="2026-01-01T10:00:00", title="Fragment", output=Output(),
        origin=ClipOrigin(serviceId="dienst", candidateId="c1", start=1200.0, end=1240.0),
        sourceInfo=a_recording().model_copy(update={"duration": 40.0, "hasAudio": sound}))
    models.save_project(project)
    models.save_transcript(project, Transcript(language="nl", segments=[
        Segment(start=0.0, end=10.0, text="ruwe tekst uit de scan")]))
    return project


# --- which pass is which ----------------------------------------------------------


def test_the_service_is_scanned_rather_than_written_out(client, monkeypatch):
    service = a_service()
    asked: list[transcription.Listening] = []

    def listen(source, work_dir, **kwargs):
        asked.append(kwargs.get("how"))
        return Transcript(language="nl", segments=[Segment(start=0.0, end=5.0, text="tekst")])

    monkeypatch.setattr(transcription, "transcribe", listen)
    client.post(f"/services/{service.id}/transcribe")
    for _ in range(200):
        if asked:
            break
        __import__("time").sleep(0.02)
    assert asked and asked[0] == transcription.scanning()


def test_a_clip_that_arrived_on_its_own_is_written_out_properly():
    """Nothing to scan there: somebody handed us the clip itself."""
    assert transcription.writing().beam == transcription.CLIP_BEAM


# --- hearing the clip again -------------------------------------------------------


def test_the_clip_is_heard_again_over_its_own_seconds(tmp_path, monkeypatch):
    a_service()
    project = a_clip()
    seen: list[dict] = []

    def listen(source, work_dir, **kwargs):
        seen.append(kwargs)
        return Transcript(language="nl", segments=[Segment(start=0.0, end=8.0, text="wat er echt staat")])

    monkeypatch.setattr(transcription, "transcribe", listen)
    main.write_out(project, accurate=False)
    assert len(seen) == 1
    assert seen[0]["start"] == 1200.0, "it seeks to where the clip sits in the recording"
    assert seen[0]["duration"] == 40.0, "and stops at the end of it"
    assert seen[0]["how"] == transcription.writing(False)


def test_what_it_hears_replaces_the_scan(tmp_path, monkeypatch):
    a_service()
    project = a_clip()
    monkeypatch.setattr(transcription, "transcribe", lambda *a, **k: Transcript(
        language="nl", segments=[Segment(start=0.0, end=8.0, text="wat er echt staat")]))
    main.write_out(project)
    kept = models.load_transcript(models.load_project("clip"))
    assert [s.text for s in kept.segments] == ["wat er echt staat"]


def test_asking_for_the_careful_model_reaches_the_clip_and_not_the_service(tmp_path, monkeypatch):
    a_service(accurate=True)
    project = a_clip()
    seen: list[dict] = []
    monkeypatch.setattr(transcription, "transcribe",
                        lambda *a, **k: seen.append(k) or Transcript(language="nl", segments=[
                            Segment(start=0.0, end=8.0, text="netjes")]))
    main.write_out(project, accurate=True)
    assert seen[0]["how"].model == transcription.ACCURATE_MODEL_SIZE


def test_a_pass_that_fails_leaves_the_rough_words_standing(tmp_path, monkeypatch):
    """Worse subtitles beat an empty editor, and the user can always redo them."""
    a_service()
    project = a_clip()

    def cross(*_a, **_k):
        raise RuntimeError("het model is weg")

    monkeypatch.setattr(transcription, "transcribe", cross)
    main.write_out(project)  # must not raise
    kept = models.load_transcript(models.load_project("clip"))
    assert [s.text for s in kept.segments] == ["ruwe tekst uit de scan"]


def test_a_pass_that_hears_nothing_leaves_the_rough_words_too(tmp_path, monkeypatch):
    a_service()
    project = a_clip()
    monkeypatch.setattr(transcription, "transcribe",
                        lambda *a, **k: Transcript(language="nl", segments=[]))
    main.write_out(project)
    kept = models.load_transcript(models.load_project("clip"))
    assert [s.text for s in kept.segments] == ["ruwe tekst uit de scan"]


def test_a_clip_without_sound_is_not_listened_to(tmp_path, monkeypatch):
    a_service()
    project = a_clip(sound=False)

    def cross(*_a, **_k):
        raise AssertionError("there is nothing to hear")

    monkeypatch.setattr(transcription, "transcribe", cross)
    main.write_out(project)


def test_stopping_still_stops(tmp_path, monkeypatch):
    """Cancelling must travel, or pressing Stoppen would look like it did nothing."""
    a_service()
    project = a_clip()

    def cross(*_a, **_k):
        raise main.Cancelled

    monkeypatch.setattr(transcription, "transcribe", cross)
    with pytest.raises(main.Cancelled):
        main.write_out(project)


# --- both passes, in the step where you are waiting -------------------------------


def test_cutting_a_service_hears_every_clip_and_frames_it(client, monkeypatch):
    service = a_service()
    heard: list[str] = []
    framed: list[str] = []
    monkeypatch.setattr(main, "write_out",
                        lambda p, *a, **k: heard.append(p.id) or p)
    monkeypatch.setattr(main, "follow_speaker",
                        lambda p, *a, **k: framed.append(p.id) or p)
    answer = client.post(f"/services/{service.id}/process-selected")
    assert answer.status_code == 200
    for _ in range(300):
        if heard and framed:
            break
        __import__("time").sleep(0.02)
    assert len(heard) == 1 and heard == framed, "the same clip, written out and then framed"


def test_the_bar_covers_both_steps_of_every_clip(client, monkeypatch):
    """Half the clip's share each, so the number never goes backwards."""
    service = a_service()
    service.candidates.append(ClipCandidate(id="c2", start=2000.0, end=2040.0, title="Twee",
                                            score=0.8, reason="x", selected=True))
    models.save_service(service)
    seen: list[float] = []

    def note(project, told):
        if told:
            for f in (0.0, 0.5, 1.0):
                told(f, "bezig")
        return project

    monkeypatch.setattr(main, "write_out", lambda p, acc=False, told=None, stop=None, quiet=True: note(p, told))
    monkeypatch.setattr(main, "follow_speaker", lambda p, told=None, stop=None, quiet=True: note(p, told))
    real = main.Job.advance

    def watch(self, fraction):
        seen.append(fraction)
        real(self, fraction)

    monkeypatch.setattr(main.Job, "advance", watch)
    client.post(f"/services/{service.id}/process-selected")
    for _ in range(300):
        if len(seen) >= 14:
            break
        __import__("time").sleep(0.02)
    # Two clips, two steps each, three readings per step, plus one before each clip starts.
    assert len(seen) >= 14, f"the work did not run: {seen}"
    assert seen == sorted(seen), f"the bar went backwards: {seen}"
    assert max(seen) <= 1.0
    assert max(seen) >= 0.9, "the last clip has to finish the bar"
