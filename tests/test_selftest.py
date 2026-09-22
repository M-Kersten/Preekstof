"""Ten seconds through the whole chain, and what it says when a link in it is broken."""

import json
import subprocess
import zipfile
from io import BytesIO
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend import diagnose, main, selftest
from backend.models import Segment, Transcript, VideoInfo


@pytest.fixture
def alone(tmp_path, monkeypatch):
    monkeypatch.setattr(selftest, "WORK", tmp_path / "zelftest")
    monkeypatch.setattr(selftest, "KEPT", tmp_path / "zelftest.json")
    return tmp_path


# --- the sentence that ships with the app -----------------------------------------


def test_the_sample_travels_with_the_app():
    assert selftest.SAMPLE.is_file()
    assert selftest.SAMPLE.stat().st_size < 200_000, "dit moet klein blijven"


def test_the_sample_is_the_length_the_code_thinks_it_is():
    said = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration",
                           "-of", "csv=p=0", str(selftest.SAMPLE)],
                          capture_output=True, text=True, check=True).stdout
    assert abs(float(said) - selftest.SECONDS) < 1.0


# --- what counts as read back ------------------------------------------------------


def heard_as(text: str) -> Transcript:
    return Transcript(language="nl", segments=[Segment(start=0, end=8, text=text)])


def test_the_real_answer_from_this_machine_counts_as_read_back():
    """What whisper actually returned here, mistakes and all. This must keep passing."""
    back, _ = selftest.said_back(heard_as(
        "Dit is een proefmanpreeksstof. Als je deze linteren geeft in de AAP, "
        "dan merkt het uitschrijven op deze computer."))
    assert back >= len(selftest.ANCHORS) * selftest.ENOUGH


def test_a_perfect_reading_counts_too():
    back, _ = selftest.said_back(heard_as(
        "Dit is een proef van Preekstof. Als je deze zin terugleest in de app, "
        "dan werkt het uitschrijven op deze computer."))
    assert back == len(selftest.ANCHORS)


@pytest.mark.parametrize("nonsense", ["", "   ", "you you you you", "Thank you for watching."])
def test_a_model_that_read_something_else_does_not_count(nonsense):
    """Silence and hallucination are the two ways a broken chain looks like a working one."""
    back, _ = selftest.said_back(heard_as(nonsense))
    assert back < len(selftest.ANCHORS) * selftest.ENOUGH


# --- a broken link, staged on purpose ----------------------------------------------


def test_no_ffmpeg_stops_at_the_first_step_and_says_which(alone, monkeypatch):
    monkeypatch.setattr(selftest.shutil, "which", lambda _n: None)
    monkeypatch.setattr(selftest, "ROOT", alone)  # no downloaded copy either
    result = selftest.run(alone / "zelftest")
    assert not result.ok
    assert not result.outcomes[0].ok
    assert "FFmpeg" in result.outcomes[0].detail


def test_the_steps_that_needed_it_say_they_were_skipped(alone, monkeypatch):
    """"Everything is broken" and "the render is broken" are answers of different worth."""
    monkeypatch.setattr(selftest.shutil, "which", lambda _n: None)
    monkeypatch.setattr(selftest, "ROOT", alone)
    result = selftest.run(alone / "zelftest")
    skipped = [o for o in result.outcomes if o.skipped]
    assert len(skipped) == 3
    assert all("Overgeslagen" in o.detail for o in skipped)
    assert [o.step for o in result.outcomes] == ["geluid", "uitschrijven", "volgen", "clip"]


def test_a_speech_model_that_will_not_load_names_itself(alone, monkeypatch):
    def refuse(*a, **k):
        raise RuntimeError("Het spraakmodel 'small' kon niet geladen worden.")

    monkeypatch.setattr(selftest.transcription, "transcribe", refuse)
    outcome, text = selftest.step_uitschrijven(alone)
    assert not outcome.ok
    assert "spraakmodel" in outcome.detail
    assert text == ""


def test_a_model_that_ran_but_read_something_else_is_a_failure_with_the_words_in_it(alone, monkeypatch):
    monkeypatch.setattr(selftest.transcription, "transcribe",
                        lambda *a, **k: heard_as("Thank you for watching."))
    outcome, _ = selftest.step_uitschrijven(alone)
    assert not outcome.ok
    assert "Thank you for watching." in outcome.detail
    assert "half gedownload" in outcome.detail


def test_a_render_that_comes_back_empty_blames_libass(alone, monkeypatch):
    """An FFmpeg without libass is a real build and the readiness panel cannot see it."""
    (alone / "proefclip.mp4").write_bytes(b"x" * 10)
    monkeypatch.setattr(selftest.renderer, "render_video", lambda *a, **k: None)
    monkeypatch.setattr(selftest.renderer, "probe", lambda _p: VideoInfo(
        width=1280, height=720, duration=9, fps=25, videoCodec="h264", hasAudio=True,
        audioCodec="aac", audioSampleRate=48000, audioChannels=2))
    monkeypatch.setattr(selftest.subtitles, "write_ass", lambda *a, **k: alone / "x.ass")
    outcome, made = selftest.step_clip(alone, alone / "proef.mp4", "iets")
    assert not outcome.ok
    assert "libass" in outcome.detail
    assert made is None


# --- what is kept, and who gets to read it -----------------------------------------


def test_the_outcome_is_kept_so_a_report_can_say_it(alone):
    result = selftest.Result(outcomes=[selftest.Outcome("geluid", "Geluid", True, "ging goed", 1.2)])
    selftest.remember(result)
    said = selftest.last()
    assert said["ok"] is True
    assert said["steps"][0]["detail"] == "ging goed"
    assert said["at"].startswith("20")


def test_never_having_run_it_is_not_a_crash(alone):
    assert selftest.last() is None
    assert selftest.clip_path() is None


def test_a_damaged_file_reads_as_never_run(alone):
    selftest.KEPT.write_text("{ dit is geen json", encoding="utf-8")
    assert selftest.last() is None


def test_a_folder_that_cannot_be_written_costs_the_memory_and_not_the_run(tmp_path, monkeypatch):
    monkeypatch.setattr(selftest, "KEPT", tmp_path / "nope" / "deeper" / "x.json")
    monkeypatch.setattr(Path, "mkdir", lambda *a, **k: (_ for _ in ()).throw(OSError()))
    selftest.remember(selftest.Result())  # no exception


def test_the_report_says_when_the_proof_was_never_run(alone):
    said = diagnose.first_page("iets", None)
    assert "nooit gedraaid" in said


def test_the_report_carries_the_proof_when_there_is_one(alone):
    selftest.remember(selftest.Result(outcomes=[
        selftest.Outcome("clip", "Clip maken", False, "FFmpeg zonder libass", 2.0)]))
    kept = diagnose.build("de clip mislukte")
    with zipfile.ZipFile(BytesIO(kept)) as z:
        assert "proef.json" in z.namelist()
        assert "FOUT Clip maken" in z.read("melding.txt").decode()
        assert json.loads(z.read("proef.json"))["ok"] is False


# --- through the endpoints ---------------------------------------------------------


@pytest.fixture
def client(alone):
    with TestClient(main.app) as running:
        yield running


def test_a_machine_that_never_proved_itself_says_so(client):
    said = client.get("/selftest").json()
    assert said == {"last": None, "hasClip": False, "job": None}


def test_there_is_no_clip_to_show_before_it_has_run(client):
    assert client.get("/selftest/clip").status_code == 404


def test_two_proofs_at_once_are_refused(client, monkeypatch):
    monkeypatch.setattr(main.jobs, "is_running", lambda key: key == main.SELFTEST)
    assert client.post("/selftest").status_code == 409
