"""How long a service takes here, said before somebody finds out on a Sunday afternoon."""

import json

import pytest

from backend import speed


@pytest.fixture
def kept(tmp_path, monkeypatch):
    monkeypatch.setattr(speed, "KEPT", tmp_path / "speed.json")
    return speed.KEPT


def a_run(audio=5400.0, wall=1100.0, engine="faster-whisper", model="small"):
    return {"audio": audio, "wall": wall, "engine": engine, "model": model}


# --- what this machine has really done --------------------------------------------


def test_one_real_service_is_enough_to_stop_guessing(kept):
    speed.remember(5400, 1080, "faster-whisper", "small")
    rate = speed.known("faster-whisper", "small")
    assert rate.measured_here
    assert rate.minutes_for() == pytest.approx(18, abs=0.5)


def test_the_middle_run_decides_rather_than_the_average(kept):
    """One service that shared the machine with a video call should not move the number."""
    for wall in (1080, 1100, 1120, 9000):
        speed.remember(5400, wall, "faster-whisper", "small")
    assert speed.known("faster-whisper", "small").minutes_for() == pytest.approx(18.5, abs=1)


def test_only_the_last_few_runs_count(kept):
    for i in range(20):
        speed.remember(5400, 1000 + i, "faster-whisper", "small")
    assert len(json.loads(kept.read_text(encoding="utf-8"))["runs"]) == speed.REMEMBER


def test_a_short_clip_says_nothing_about_a_service(kept):
    """Writing out twenty seconds is mostly the model loading."""
    speed.remember(20, 40, "faster-whisper", "small")
    assert not kept.exists() or speed.from_runs("small", "faster-whisper") is None


@pytest.mark.parametrize("audio, wall", [(5400, 0), (5400, -1), (0, 100)])
def test_a_run_that_makes_no_sense_is_not_written_down(kept, audio, wall):
    speed.remember(audio, wall, "faster-whisper", "small")
    assert speed.from_runs("small", "faster-whisper") is None


def test_a_different_model_is_a_different_machine_as_far_as_this_goes(kept):
    speed.remember(5400, 1080, "faster-whisper", "small")
    assert speed.from_runs("medium", "faster-whisper") is None
    assert speed.from_runs("small", "mlx") is None


def test_a_folder_that_cannot_be_written_costs_an_estimate_and_not_a_transcription(tmp_path, monkeypatch):
    monkeypatch.setattr(speed, "KEPT", tmp_path / "nope" / "deeper" / "speed.json")
    speed.remember(5400, 1080, "faster-whisper", "small")  # no exception


def test_a_damaged_file_is_not_a_crash(kept):
    kept.write_text("{ dit is geen json", encoding="utf-8")
    assert speed.load() == {}
    speed.remember(5400, 1080, "faster-whisper", "small")
    assert speed.from_runs("small", "faster-whisper") is not None


# --- the table of machines somebody measured ---------------------------------------


def test_the_table_only_holds_machines_that_were_really_timed():
    """A guessed row is the number a church plans its Sunday around."""
    for pattern, per, said in speed.MEASURED:
        assert 0.01 < per < 2.0, f"{said}: {per} is geen gemeten getal"
        assert said.strip()


def test_a_machine_nobody_measured_says_so_rather_than_inventing_one(kept, monkeypatch):
    monkeypatch.setattr(speed, "processor", lambda: "Mystery Chip 9000")
    said = speed.sentence("faster-whisper", "small")
    assert "weet de app pas na de eerste dienst" in said


def test_a_machine_from_the_table_is_said_as_a_range(kept, monkeypatch):
    monkeypatch.setattr(speed, "processor", lambda: "x86_64")
    said = speed.sentence("faster-whisper", "small")
    assert "tot" in said and "naar verwachting" in said
    assert "Na de eerste dienst" in said


def test_what_this_machine_did_beats_what_the_table_says(kept, monkeypatch):
    monkeypatch.setattr(speed, "processor", lambda: "x86_64")
    speed.remember(5400, 2700, "faster-whisper", "small")
    said = speed.sentence("faster-whisper", "small")
    assert "gemeten op deze computer" in said
    assert "45 minuten" in said


def test_several_services_are_said_as_several(kept, monkeypatch):
    for _ in range(3):
        speed.remember(5400, 1080, "faster-whisper", "small")
    assert "over 3 diensten" in speed.sentence("faster-whisper", "small")


# --- how it is said ------------------------------------------------------------------


@pytest.mark.parametrize("minutes, want", [
    (0.4, "nog geen minuut"), (18.3, "18 minuten"), (45, "45 minuten"),
    (89, "89 minuten"), (96, "ongeveer 1,6 uur"), (150, "ongeveer 2,5 uur"),
])
def test_a_number_is_said_the_way_somebody_would_say_it(minutes, want):
    assert speed.as_minutes(minutes) == want


# --- and what the readiness panel does with it ----------------------------------------


def test_a_machine_that_needs_two_hours_is_not_green(kept, monkeypatch):
    from backend import health

    speed.remember(5400, 9000, "faster-whisper", "small")  # 2.5 hours for 90 minutes
    monkeypatch.setattr(health.transcription, "engine", lambda: "faster-whisper")
    monkeypatch.setattr(health, "MODEL_SIZE", "small")
    check = health._speed()
    assert not check.ok
    assert "te lang om vol te houden" in check.detail


def test_a_machine_that_manages_it_is_green(kept, monkeypatch):
    from backend import health

    speed.remember(5400, 1080, "faster-whisper", "small")
    monkeypatch.setattr(health.transcription, "engine", lambda: "faster-whisper")
    monkeypatch.setattr(health, "MODEL_SIZE", "small")
    assert health._speed().ok


def test_not_knowing_yet_is_not_a_failure(kept, monkeypatch):
    from backend import health

    monkeypatch.setattr(speed, "processor", lambda: "Mystery Chip 9000")
    monkeypatch.setattr(health.transcription, "engine", lambda: "faster-whisper")
    assert health._speed().ok


def test_the_panel_names_it_so_it_can_be_found(kept):
    from backend import health

    assert any(c["name"] == "Snelheid" for c in health.report()["checks"])
