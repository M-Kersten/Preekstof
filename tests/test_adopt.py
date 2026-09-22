"""Turning a service the app has done into a case the evaluation set can measure."""

import json

import pytest

from backend import models
from backend.models import ClipCandidate, ProcessedClip, Service, VideoInfo
from tools import adopt


@pytest.fixture
def services(tmp_path, monkeypatch):
    folder = tmp_path / "services"
    folder.mkdir()
    monkeypatch.setattr(models, "SERVICES_DIR", folder)
    monkeypatch.setattr(adopt, "SERVICES_DIR", folder)
    return folder


def a_service(services, sid="service-1", *, clips=2, transcript=True, **fields) -> Service:
    folder = services / sid
    folder.mkdir(parents=True, exist_ok=True)
    service = Service(id=sid, createdAt="2026-09-06T10:00:00+00:00",
                      title="Morgendienst · 6 september 2026",
                      sourceVideo="source.mp4",
                      sourceInfo=VideoInfo(width=1920, height=1080, duration=5400, fps=25,
                                           videoCodec="h264", hasAudio=True, audioCodec="aac",
                                           audioSampleRate=48000, audioChannels=2),
                      **fields)
    service.candidates = [ClipCandidate(id=f"c{i}", start=i * 600, end=i * 600 + 60, title=f"m{i}")
                          for i in range(6)]
    service.clips = [ProcessedClip(candidateId=f"c{i}", projectId=f"p{i}", title=f"moment {i}",
                                   start=i * 600, end=i * 600 + 60,
                                   createdAt="2026-09-06T12:00:00+00:00")
                     for i in range(clips)]
    models.save_service(service)
    if transcript:
        (folder / "transcript.json").write_text(
            json.dumps({"language": "nl", "segments": [{"start": 0, "end": 2, "text": "Goedemorgen"}]}),
            encoding="utf-8")
    return service


def test_the_clips_that_were_made_are_the_answer_key(services, tmp_path):
    """A suggestion nobody turned into a clip is not something the church posted."""
    a_service(services, clips=3)
    target = adopt.adopt("service-1", tmp_path / "set")
    said = json.loads((target / "service.json").read_text(encoding="utf-8"))
    assert len(said["posted"]) == 3
    assert said["posted"][0] == {"start": 0.0, "end": 60.0, "note": "moment 0"}


def test_the_moments_come_out_in_the_order_they_happened(services, tmp_path):
    service = a_service(services, clips=0)
    service.clips = [ProcessedClip(candidateId="c2", projectId="p2", title="laat", start=2000,
                                   end=2060, createdAt="2026-09-06T12:00:00+00:00"),
                     ProcessedClip(candidateId="c1", projectId="p1", title="vroeg", start=100,
                                   end=160, createdAt="2026-09-06T12:00:00+00:00")]
    models.save_service(service)
    said = json.loads((adopt.adopt("service-1", tmp_path / "set") / "service.json")
                      .read_text(encoding="utf-8"))
    assert [m["note"] for m in said["posted"]] == ["vroeg", "laat"]


def test_the_transcript_travels_with_it(services, tmp_path):
    a_service(services)
    target = adopt.adopt("service-1", tmp_path / "set")
    assert json.loads((target / "transcript.json").read_text(encoding="utf-8"))["language"] == "nl"


def test_what_the_church_knew_beforehand_comes_along(services, tmp_path):
    a_service(services, sermonTitle="Rust in een druk leven", series="Onderweg",
              preacher="ds. M. Kreuk")
    said = json.loads((adopt.adopt("service-1", tmp_path / "set") / "service.json")
                      .read_text(encoding="utf-8"))
    assert said["sermonTitle"] == "Rust in een druk leven"
    assert said["series"] == "Onderweg"
    assert said["preacher"] == "ds. M. Kreuk"
    assert said["duration"] == 5400


def test_permission_is_left_blank_on_purpose(services, tmp_path):
    """A transcript in this folder without a name against it should stand out."""
    a_service(services)
    said = json.loads((adopt.adopt("service-1", tmp_path / "set") / "service.json")
                      .read_text(encoding="utf-8"))
    assert said["church"] == "VUL IN"
    assert said["permission"].startswith("VUL IN")


def test_a_service_with_no_clips_is_refused(services, tmp_path):
    """Adopting it would put a transcript in the set with an empty answer key."""
    a_service(services, clips=0)
    with pytest.raises(SystemExit) as caught:
        adopt.adopt("service-1", tmp_path / "set")
    assert "geen gemaakte clips" in str(caught.value)


def test_a_service_that_was_never_written_out_is_refused(services, tmp_path):
    a_service(services, transcript=False)
    with pytest.raises(SystemExit) as caught:
        adopt.adopt("service-1", tmp_path / "set")
    assert "uitgeschreven" in str(caught.value)


def test_a_service_that_does_not_exist_says_so(services, tmp_path):
    with pytest.raises(SystemExit) as caught:
        adopt.adopt("service-weg", tmp_path / "set")
    assert "bestaat niet" in str(caught.value)


def test_you_can_give_the_case_a_name_you_will_recognise(services, tmp_path):
    a_service(services)
    target = adopt.adopt("service-1", tmp_path / "set", "2026-03-08-kruispunt")
    assert target.name == "2026-03-08-kruispunt"


def test_what_comes_out_is_what_the_harness_reads(services, tmp_path):
    """The two tools have to agree, or a case looks adopted and measures nothing."""
    from tools import evaluate

    a_service(services, clips=2, sermonTitle="Rust")
    adopt.adopt("service-1", tmp_path / "set", "een-dienst")
    cases = evaluate.load_cases(tmp_path / "set")
    assert len(cases) == 1
    assert len(cases[0].posted) == 2
    assert "Rust" in cases[0].about


def test_a_clip_with_impossible_timings_is_left_out(services, tmp_path):
    service = a_service(services, clips=0)
    service.clips = [ProcessedClip(candidateId="c1", projectId="p1", title="goed", start=10,
                                   end=70, createdAt="2026-09-06T12:00:00+00:00"),
                     ProcessedClip(candidateId="c2", projectId="p2", title="stuk", start=90,
                                   end=90, createdAt="2026-09-06T12:00:00+00:00")]
    models.save_service(service)
    said = json.loads((adopt.adopt("service-1", tmp_path / "set") / "service.json")
                      .read_text(encoding="utf-8"))
    assert [m["note"] for m in said["posted"]] == ["goed"]
