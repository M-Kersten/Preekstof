"""The page a church council reads, and the promise it makes about what leaves the building."""

import re
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend import version
from backend.main import app

PAGE = Path(__file__).resolve().parent.parent / "PRIVACY.md"
SAID = PAGE.read_text(encoding="utf-8")


def test_it_exists_next_to_the_app():
    assert PAGE.is_file()


def test_it_says_which_version_it_belongs_to():
    """A promise about a program is worth nothing without saying which program."""
    assert version.VERSION in SAID


@pytest.mark.parametrize("subject, must_say", [
    ("waar de opname blijft", "eigen computer"),
    ("wat er naar Anthropic gaat", "api.anthropic.com"),
    ("niet gebruikt om te trainen", "trainen"),
    ("het gevoelige deel", "AVG"),
    ("de uitweg voor wie dit niet wil", "LLM_PROVIDER=ollama"),
    ("hoe lang het blijft staan", "KEEP_WEEKS"),
    ("hoe je alles weggooit", "Ruimte vrijmaken"),
    ("dat er niets naar de maker gaat", "telemetrie"),
    ("waar de sleutel staat", "config.env"),
    ("kerkdienstgemist", "Kerkdienstgemist"),
    ("hugging face", "Hugging Face"),
])
def test_it_answers_what_a_council_will_ask(subject, must_say):
    assert must_say in SAID, f"niets over {subject}"


def test_it_names_what_a_transcript_can_contain():
    """The weakness is only a weakness while it is undocumented."""
    assert "zieke" in SAID or "ziek is" in SAID
    assert "gebeden" in SAID or "gebed" in SAID


def test_it_does_not_hedge():
    """A council reading "mogelijk" and "wellicht" learns nothing it can decide on."""
    for weasel in ("wellicht", "mogelijk gaat", "zou kunnen gaan"):
        assert weasel not in SAID.lower(), f"hedging: {weasel}"


def test_the_app_serves_the_copy_that_ships_with_it():
    with TestClient(app) as client:
        answer = client.get("/privacy")
    assert answer.status_code == 200
    assert answer.headers["content-type"].startswith("text/plain")
    assert answer.text == SAID


def test_every_setting_it_names_is_a_setting_the_app_really_reads():
    """A page that tells a church to set something the app ignores is worse than no page."""
    from backend import discovery, storage

    assert discovery.LLM_PROVIDER is not None
    assert isinstance(storage.KEEP_WEEKS, (int, float))


def test_it_claims_no_telemetry_and_the_app_has_none():
    """The one claim here that code could quietly contradict."""
    backend = Path(__file__).resolve().parent.parent / "backend"
    reaching_out = re.compile(r"urlopen|requests\.(get|post)|httpx\.")
    allowed = {"fetch.py", "kerkdienstgemist.py", "updates.py", "vision.py", "discovery.py",
               "transcription.py", "fonts.py"}
    for module in backend.glob("*.py"):
        if module.name in allowed:
            continue
        assert not reaching_out.search(module.read_text(encoding="utf-8")), \
            f"{module.name} praat met de buitenwereld en staat niet in PRIVACY.md"
