"""What a pilot learned, out of the file the app filled in while it worked."""

import json

import pytest

from backend import journal
from tools import pilot


@pytest.fixture
def kept(tmp_path, monkeypatch):
    monkeypatch.setattr(journal, "KEPT", tmp_path / "runs.jsonl")
    return journal.KEPT


def a_service(kept, *, audio=5400.0, writing=1080.0, offered=8, made=3, top5=2, own=0):
    journal.note("uitschrijven", service="s", audio=audio, seconds=writing,
                 engine="faster-whisper", model="small")
    journal.note("zoeken", service="s", seconds=42.0, windows=1, failed=0,
                 found=offered, shortlisted=5, tokens=2700, cost=0.03, model="claude-opus-5")
    journal.note("clips", service="s", seconds=300.0, offered=offered, made=made,
                 fromTop5=top5, ownCuts=own)


# --- writing it down ---------------------------------------------------------------


def test_one_line_per_event(kept):
    a_service(kept)
    assert len(kept.read_text(encoding="utf-8").strip().splitlines()) == 3


def test_every_line_says_when_and_what(kept):
    journal.note("zoeken", service="s", cost=0.03)
    said = json.loads(kept.read_text(encoding="utf-8"))
    assert said["what"] == "zoeken" and said["at"].startswith("20")


def test_nothing_anybody_said_ends_up_in_it(kept):
    """It has to be mailable without being read first, or it never gets mailed."""
    a_service(kept)
    said = kept.read_text(encoding="utf-8")
    for private in ("titel", "preek", "voorganger", "kerk"):
        assert private not in said.lower()


def test_a_folder_that_cannot_be_written_is_not_a_reason_for_anything_to_fail(tmp_path, monkeypatch):
    monkeypatch.setattr(journal, "KEPT", tmp_path / "nope" / "deeper" / "runs.jsonl")
    monkeypatch.setattr(journal.Path, "mkdir", lambda *a, **k: (_ for _ in ()).throw(OSError()))
    journal.note("zoeken", cost=0.03)  # no exception


def test_it_stops_growing_before_it_becomes_a_problem(kept, monkeypatch):
    monkeypatch.setattr(journal, "MAX_BYTES", 200)
    for _ in range(50):
        journal.note("zoeken", service="s", cost=0.03)
    assert kept.stat().st_size < 600


def test_a_damaged_line_is_skipped_rather_than_fatal(kept):
    a_service(kept)
    with kept.open("a", encoding="utf-8") as out:
        out.write("{ dit is geen json\n")
    assert len(journal.read(kept)) == 3


# --- reading it back ----------------------------------------------------------------


def test_nothing_yet_says_so_rather_than_printing_zeros(kept):
    assert "nog niets" in pilot.said(pilot.summarise(journal.read(kept)))


def test_the_four_numbers_come_out(kept):
    a_service(kept, audio=5400, writing=1080, offered=8, made=3, top5=2)
    summary = pilot.summarise(journal.read(kept))
    assert summary["diensten"] == 1
    assert summary["uitschrijvenMinutenPer90"] == pytest.approx(18, abs=0.5)
    assert summary["zoekenEuro"] == 0.03
    assert summary["gemaakt"] == 3 and summary["voorgesteld"] == 8
    assert summary["uitDeTop5"] == 2
    assert summary["deelUitTop5"] == pytest.approx(0.67, abs=0.01)


def test_several_services_add_up(kept):
    a_service(kept, made=3, top5=2, offered=8)
    a_service(kept, made=4, top5=4, offered=9)
    summary = pilot.summarise(journal.read(kept))
    assert summary["diensten"] == 2
    assert summary["gemaakt"] == 7 and summary["uitDeTop5"] == 6
    assert summary["voorgesteld"] == 17


def test_the_middle_service_decides_how_long_writing_out_takes(kept):
    """One service that resumed after a closed laptop should not set the expectation."""
    for writing in (1000, 1100, 1200, 30000):
        a_service(kept, audio=5400, writing=writing)
    assert pilot.summarise(journal.read(kept))["uitschrijvenMinutenPer90"] == \
        pytest.approx(19, abs=2)


def test_clips_somebody_cut_by_hand_are_counted_apart(kept):
    """A church that ignores every suggestion and cuts its own is telling you something."""
    a_service(kept, made=3, top5=0, own=3)
    summary = pilot.summarise(journal.read(kept))
    assert summary["zelfGeknipt"] == 3
    assert summary["deelUitTop5"] == 0.0


def test_the_one_number_that_matters_is_named_in_words(kept):
    a_service(kept, made=4, top5=3, offered=9)
    said = pilot.said(pilot.summarise(journal.read(kept)))
    assert "uit de top 5" in said
    assert "3 van 4" in said


def test_a_pilot_with_searches_that_failed_says_so(kept):
    journal.note("zoeken", service="s", seconds=40.0, failed=2, cost=0.03)
    journal.note("clips", service="s", offered=4, made=1, fromTop5=1, ownCuts=0)
    assert "liepen vast" in pilot.said(pilot.summarise(journal.read(kept)))
