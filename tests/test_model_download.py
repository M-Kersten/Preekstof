"""The 460 MB that used to arrive in silence, counted."""

import io

import pytest

from backend import transcription


def counting(expected_mb=0):
    said = []
    counter = transcription.Arriving(expected_mb * 1e6, lambda f, m: said.append((f, m)))
    return counter, said


# --- which repository ----------------------------------------------------------------


@pytest.mark.parametrize("size, repo", [
    ("small", "Systran/faster-whisper-small"),
    ("large-v3", "Systran/faster-whisper-large-v3"),
    ("mlx-community/whisper-small-mlx", "mlx-community/whisper-small-mlx"),
])
def test_a_size_becomes_a_repository(size, repo):
    assert transcription.model_repo(size) == repo


def test_a_size_nobody_knows_is_not_guessed_at():
    assert transcription.model_repo("") is None


# --- counting what arrives -------------------------------------------------------------


def test_the_bytes_are_added_up_here_and_not_by_tqdm():
    """A bar that is switched off takes updates and quietly stops counting, and this app
    switches them off itself. What is reported has to survive that."""
    counter, said = counting()
    assert said == []
    Bar = counter.bar()
    bar = Bar(total=100e6, unit="B")
    bar.disable = True  # exactly what quiet_hub_notices causes
    for _ in range(4):
        bar.update(25e6)
    assert "100 van 100 MB" in said[-1][1]
    assert said[-1][0] == pytest.approx(0.99)


def test_two_bars_over_the_same_download_do_not_count_it_twice():
    """One bar for the wire and one for putting it back together; the same megabytes."""
    counter, said = counting()
    Bar = counter.bar()
    wire, built = Bar(total=100e6, unit="B"), Bar(total=100e6, unit="B")
    wire.update(60e6)
    built.update(40e6)
    assert "60 van 100 MB" in said[-1][1]


def test_a_third_bar_would_change_nothing():
    counter, said = counting()
    Bar = counter.bar()
    bars = [Bar(total=100e6, unit="B") for _ in range(3)]
    for bar in bars:
        bar.update(30e6)
    assert "30 van 100 MB" in said[-1][1]


def test_the_guess_stands_until_the_real_total_passes_it():
    """The estimate is a floor, so a bar that starts at nought does not read as nought of
    nought. The moment the download says how big it really is, that wins."""
    counter, said = counting(expected_mb=145)
    Bar = counter.bar()
    bar = Bar(total=100e6, unit="B")
    bar.update(1e6)
    assert "van 145 MB" in said[-1][1], "de schatting is de bodem"
    bigger = Bar(total=148e6, unit="B")
    bigger.update(20e6)  # past the once-a-megabyte throttle
    assert "van 148 MB" in said[-1][1], "en de echte totaal wint zodra hij groter is"


def test_it_says_this_happens_once():
    """Which is the whole reason somebody is willing to wait for it."""
    counter, said = counting()
    counter.bar()(total=100e6)
    assert "één keer" in said[-1][1]


def test_it_does_not_say_it_thousands_of_times():
    """A callback per chunk is a job message rewritten faster than anyone can read it."""
    counter, said = counting()
    bar = counter.bar()(total=100e6, unit="B")
    for _ in range(2000):
        bar.update(50_000)  # 50 kB at a time, 100 MB in total
    assert len(said) < 150


def test_it_never_claims_to_be_finished():
    """The model still has to load after the last byte; a bar at 100 that then waits is
    worse than one that stops at 99."""
    counter, said = counting()
    bar = counter.bar()(total=100e6, unit="B")
    bar.update(100e6)
    assert said[-1][0] <= 0.99


# --- and when it cannot be counted ------------------------------------------------------


def test_without_somebody_watching_nothing_is_fetched_here(monkeypatch):
    """The ordinary path, where WhisperModel does its own downloading as it always did."""
    monkeypatch.setattr(transcription, "model_repo", lambda _s: "Systran/faster-whisper-small")
    assert transcription.fetch_model("small", None) == "small"


def test_a_download_that_falls_over_hands_back_the_size(monkeypatch):
    import huggingface_hub

    monkeypatch.setattr(huggingface_hub, "snapshot_download",
                        lambda *a, **k: (_ for _ in ()).throw(OSError("geen verbinding")))
    assert transcription.fetch_model("small", lambda f, m: None) == "small"


def test_a_hub_without_the_bar_we_expect_is_not_fatal(monkeypatch):
    """Their tqdm moved once already. If it moves again the download still has to work."""
    counter, _said = counting()
    monkeypatch.delattr("huggingface_hub.utils.tqdm", raising=False)
    assert counter.bar() is not None
