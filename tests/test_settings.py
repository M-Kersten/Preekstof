"""config.env is edited in Notepad by a volunteer. A typo there is not a broken app."""

import importlib

import pytest

from backend import settings


@pytest.fixture(autouse=True)
def _put_discovery_back():
    """The reloads above must leave the module as the rest of the suite expects it."""
    yield
    import backend.discovery

    importlib.reload(backend.discovery)

# --- the note someone wrote behind the value ------------------------------------

@pytest.mark.parametrize("written,meant", [
    ("medium   # of high als de momenten tegenvallen", "medium"),
    ("8 # sneller", "8"),
    ("medium\t# met een tab ervoor", "medium"),
    ('"medium"', "medium"),
    ("'medium'", "medium"),
    ("  medium  ", "medium"),
    ("medium", "medium"),
])
def test_a_note_behind_the_value_is_not_part_of_the_value(written, meant):
    assert settings.clean(written) == meant


def test_a_hash_inside_a_value_is_left_alone():
    """An API key or a password may contain one, and losing its tail would be silent."""
    assert settings.clean("sk-ant-a#b#c") == "sk-ant-a#b#c"
    assert settings.clean("geheim#wachtwoord") == "geheim#wachtwoord"


# --- words -----------------------------------------------------------------------

def test_a_setting_that_is_not_there_falls_back(monkeypatch):
    monkeypatch.delenv("WHATEVER", raising=False)
    assert settings.text("WHATEVER", "medium") == "medium"


def test_an_empty_setting_falls_back(monkeypatch):
    monkeypatch.setenv("WHATEVER", "   ")
    assert settings.text("WHATEVER", "medium") == "medium"


def test_one_of_a_handful_of_words_is_checked(monkeypatch):
    monkeypatch.setenv("LEVEL", "HIGH")
    assert settings.choice("LEVEL", ("low", "high"), "low") == "high"


def test_a_word_that_is_not_allowed_falls_back_and_says_so(monkeypatch, capsys):
    monkeypatch.setenv("LEVEL", "gemiddeld")
    assert settings.choice("LEVEL", ("low", "medium", "high"), "medium") == "medium"
    said = capsys.readouterr().out
    assert "LEVEL" in said and "low, medium, high" in said and "config.env" in said


# --- numbers ----------------------------------------------------------------------

def test_a_number_with_a_note_behind_it_still_reads(monkeypatch):
    monkeypatch.setenv("HOW_MANY", "8 # sneller")
    assert settings.whole("HOW_MANY", 3) == 8


def test_a_number_that_is_not_a_number_falls_back_and_says_so(monkeypatch, capsys):
    monkeypatch.setenv("HOW_MANY", "veertig")
    assert settings.whole("HOW_MANY", 3) == 3
    assert "geen getal" in capsys.readouterr().out


def test_a_comma_reads_as_a_decimal_point(monkeypatch):
    """A Dutch keyboard writes 0,86 and means 0.86."""
    monkeypatch.setenv("RATE", "0,86")
    assert settings.number("RATE", 1.0) == pytest.approx(0.86)


def test_a_number_below_what_makes_sense_falls_back(monkeypatch, capsys):
    monkeypatch.setenv("HOW_MANY", "0")
    assert settings.whole("HOW_MANY", 3, least=1) == 3
    assert "minstens" in capsys.readouterr().out


def test_zero_is_fine_where_zero_means_something(monkeypatch):
    monkeypatch.setenv("KEEP", "0")
    assert settings.whole("KEEP", 4, least=0) == 0


# --- the setting that caused this --------------------------------------------------

def test_the_effort_the_api_refused_never_leaves_the_house(monkeypatch, capsys):
    """400: output_config.effort: Input should be 'low', 'medium', 'high', 'xhigh' or 'max'."""
    monkeypatch.setenv("LLM_EFFORT", "medium   # of high als de momenten tegenvallen")
    from backend import discovery

    importlib.reload(discovery)
    assert discovery.LLM_EFFORT == "medium"


def test_an_effort_nobody_recognises_becomes_one_that_works(monkeypatch, capsys):
    monkeypatch.setenv("LLM_EFFORT", "heel hoog")
    from backend import discovery

    importlib.reload(discovery)
    assert discovery.LLM_EFFORT in discovery.EFFORT_LEVELS
    assert "LLM_EFFORT" in capsys.readouterr().out


def test_the_levels_are_the_ones_the_api_accepts():
    from backend import discovery

    assert discovery.EFFORT_LEVELS == ("low", "medium", "high", "xhigh", "max")


def test_a_number_written_with_a_note_no_longer_stops_the_app(monkeypatch):
    """int() used to raise while the module was being imported, so nothing started."""
    monkeypatch.setenv("LLM_CONCURRENCY", "8 # sneller")
    monkeypatch.setenv("LLM_MAX_TOKENS", "16000  # ruim genoeg")
    from backend import discovery

    importlib.reload(discovery)
    assert discovery.LLM_CONCURRENCY == 8
    assert discovery.LLM_MAX_TOKENS == 16000


