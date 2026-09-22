"""The black window, written down, with the one secret in this app struck out."""

import sys
from pathlib import Path

import pytest

from backend import logbook


@pytest.fixture
def logs(tmp_path, monkeypatch):
    """A logs folder of its own, and the real stdout put back afterwards."""
    folder = tmp_path / "logs"
    monkeypatch.setattr(logbook, "LOGS", folder)
    monkeypatch.setattr(logbook, "CURRENT", folder / "preekstof.log")
    was = sys.stdout, sys.stderr
    yield folder
    sys.stdout, sys.stderr = was


# --- what may never be written down ---------------------------------------------


@pytest.mark.parametrize("said", [
    "ANTHROPIC_API_KEY=sk-ant-api03-AAAAAAAAAAAAAAAAAAAAAA",
    "ANTHROPIC_AUTH_TOKEN: sk-ant-oat01-BBBBBBBBBBBBBBBBBBBBBB",
    "x-api-key: sk-ant-api03-CCCCCCCCCCCCCCCCCCCCCC",
    "Authorization: Bearer sk-ant-api03-DDDDDDDDDDDDDDDDDDDDDD",
    "de aanvraag met sk-ant-api03-EEEEEEEEEEEEEEEEEEEEEE liep vast",
    "api_key=sk-ant-api03-FFFFFFFFFFFFFFFFFFFFFF",
])
def test_anything_that_looks_like_a_key_is_struck_out(said):
    left = logbook.without_secrets(said)
    assert "sk-ant-" not in left
    assert "weggelaten" in left


def test_the_rest_of_the_line_survives():
    """Striking out a key must not take the message it was in."""
    left = logbook.without_secrets("De Claude API gaf een fout (401) bij sk-ant-api03-AAAAAAAAAAAAAAAAAAAA")
    assert left.startswith("De Claude API gaf een fout (401) bij ")


def test_ordinary_text_is_left_alone():
    said = "Uitschrijven: 42% · nog ongeveer 8 minuten"
    assert logbook.without_secrets(said) == said


# --- keeping the window ----------------------------------------------------------


def test_what_the_window_says_lands_in_the_file(logs):
    logbook.begin()
    print("Opname wordt opgehaald")
    print("Uitschrijven begint")
    assert "Opname wordt opgehaald" in logbook.CURRENT.read_text(encoding="utf-8")
    assert "Uitschrijven begint" in logbook.CURRENT.read_text(encoding="utf-8")


def test_the_console_still_gets_everything(logs, capsys):
    logbook.begin()
    print("op het scherm")
    assert "op het scherm" in capsys.readouterr().out


def test_a_key_printed_by_accident_does_not_reach_the_file(logs):
    logbook.begin()
    print("bezig met sk-ant-api03-AAAAAAAAAAAAAAAAAAAAAA")
    written = logbook.CURRENT.read_text(encoding="utf-8")
    assert "sk-ant-" not in written
    assert "bezig met" in written


def test_every_line_carries_the_time_it_was_said(logs):
    logbook.begin()
    print("iets")
    assert logbook.CURRENT.read_text(encoding="utf-8").split()[0].count(":") == 2


def test_blank_lines_are_not_worth_a_timestamp(logs):
    logbook.begin()
    print("")
    print("   ")
    assert logbook.CURRENT.read_text(encoding="utf-8") == ""


# --- one file per run, and not many ----------------------------------------------


def test_the_previous_run_is_put_aside_under_its_date(logs):
    logbook.begin()
    print("de eerste keer")
    logbook.begin()
    print("de tweede keer")
    assert "de tweede keer" in logbook.CURRENT.read_text(encoding="utf-8")
    assert "de eerste keer" not in logbook.CURRENT.read_text(encoding="utf-8")
    older = logbook.older_runs()
    assert len(older) == 1
    assert "de eerste keer" in older[0].read_text(encoding="utf-8")


def test_only_the_last_few_runs_are_kept(logs):
    logs.mkdir(parents=True, exist_ok=True)
    for i in range(12):
        (logs / f"preekstof-2026010{i // 2}-00000{i}.log").write_text(f"run {i}", encoding="utf-8")
    logbook.rotate()
    assert len(logbook.older_runs()) == logbook.KEEP_RUNS - 1


def test_an_empty_run_is_not_kept_at_all(logs):
    """Starting the app twice in a row without it saying anything leaves no rubbish."""
    logbook.begin()
    logbook.begin()
    assert logbook.older_runs() == []


def test_a_run_that_will_not_stop_talking_cannot_fill_the_disk(logs, monkeypatch):
    monkeypatch.setattr(logbook, "MAX_BYTES", 2000)
    logbook.begin()
    for _ in range(400):
        print("x" * 100)
    written = logbook.CURRENT.read_text(encoding="utf-8")
    assert len(written) < 4000
    assert "logboek is vol" in written


# --- nothing here may stop the app ------------------------------------------------


def test_a_folder_that_cannot_be_written_is_not_a_reason_to_refuse_to_start(logs, monkeypatch):
    monkeypatch.setattr(Path, "mkdir", lambda *a, **k: (_ for _ in ()).throw(OSError("read-only")))
    assert logbook.begin() is None
    print("dit hoort gewoon te werken")  # no exception


def test_a_file_that_turns_unwritable_halfway_leaves_the_window_working(logs, capsys):
    logbook.begin()
    print("de eerste regel")
    logbook.CURRENT.unlink()
    logs.chmod(0o500)
    try:
        print("de tweede regel")
    finally:
        logs.chmod(0o700)
    assert "de tweede regel" in capsys.readouterr().out


# --- what the report reads --------------------------------------------------------


def test_the_tail_reaches_back_into_the_previous_run(logs):
    logbook.begin()
    print("de vorige keer ging het hier mis")
    logbook.begin()
    print("nu")
    said = logbook.tail(100)
    assert "de vorige keer ging het hier mis" in said
    assert said.strip().endswith("nu")


def test_the_tail_stops_at_the_number_asked_for(logs):
    logbook.begin()
    for i in range(50):
        print(f"regel {i}")
    assert len(logbook.tail(10).splitlines()) == 10


def test_a_tail_with_nothing_behind_it_is_empty(logs):
    assert logbook.tail(10) == ""


# --- whole lines, not whatever arrived in one call --------------------------------


def test_a_print_with_several_arguments_stays_one_line(logs):
    """print() reaches a stream in pieces; one timestamp per piece is not a log."""
    logbook.begin()
    print("Uitschrijven:", "42%", "· nog 8 minuten")
    written = logbook.CURRENT.read_text(encoding="utf-8")
    assert written.count("\n") == 1
    assert "Uitschrijven: 42% · nog 8 minuten" in written


def test_a_progress_counter_leaves_only_its_last_state(logs):
    """A download writes "  41%\\r  42%\\r" for minutes without ever ending a line."""
    logbook.begin()
    for percent in range(0, 101, 10):
        sys.stdout.write(f"\r  {percent:3d}%")
    sys.stdout.write("\n")
    written = logbook.CURRENT.read_text(encoding="utf-8")
    assert written.count("\n") == 1
    assert "100%" in written
    assert "10%" not in written


def test_a_line_that_never_ends_is_still_written_down(logs):
    """Otherwise a crash halfway through a long line takes the line with it."""
    logbook.begin()
    sys.stdout.write("x" * (logbook.MAX_PENDING + 10))
    assert "x" in logbook.CURRENT.read_text(encoding="utf-8")


def test_what_is_still_pending_is_written_on_a_flush(logs):
    logbook.begin()
    sys.stdout.write("een halve regel")
    assert logbook.CURRENT.read_text(encoding="utf-8") == ""
    sys.stdout.flush()
    assert "een halve regel" in logbook.CURRENT.read_text(encoding="utf-8")
