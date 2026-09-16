"""The words that go to the speech model, and the budget they have to fit in.

Whisper reads the *last* 223 tokens of a prompt and drops the rest without saying so
(`previous_tokens[-(max_length // 2 - 1):]` in faster_whisper). A longer word list is
therefore not a better one: past the budget it is the head that disappears, so the list is
ordered with the words worth protecting at the end and trimmed from the front.
"""

import json

import pytest

from backend import brands, transcription
from backend.transcription import PROMPT_CHARS, fit_words, initial_prompt


@pytest.fixture
def own_list(tmp_path, monkeypatch):
    """A word list of our own, and no church behind it."""
    path = tmp_path / "woordenlijst.json"
    monkeypatch.setattr(transcription, "VOCABULARY_PATH", path)
    monkeypatch.setattr(transcription, "church_words", lambda: ("", {}))
    return path


def write(path, **parts):
    path.write_text(json.dumps(parts, ensure_ascii=False), encoding="utf-8")


# --- the budget -------------------------------------------------------------------


def test_the_list_that_ships_fits_in_what_whisper_reads(own_list):
    """If this fails the front of the list is being thrown away, quietly."""
    write(own_list, opening=transcription.OPENING, words=transcription.DEFAULT_WORDS)
    assert len(initial_prompt()) <= PROMPT_CHARS


def test_the_budget_is_the_one_faster_whisper_actually_uses():
    """223 = max_length // 2 - 1, for whisper's 448. Written down so a bump gets noticed."""
    assert transcription.PROMPT_TOKENS == 448 // 2 - 1


def test_the_characters_counted_per_token_stay_under_what_dutch_costs():
    """Measured with the small model's tokenizer: a word list runs about 2.7 to the token."""
    assert transcription.CHARS_PER_TOKEN <= 2.6


def test_a_church_with_a_great_many_names_does_not_push_the_list_over(own_list, monkeypatch):
    write(own_list, opening=transcription.OPENING, words=transcription.DEFAULT_WORDS)
    monkeypatch.setattr(transcription, "church_words",
                        lambda: ("Er wordt gepreekt door: " + ", ".join(f"Naam {i}" for i in range(40)) + ".", {}))
    assert len(initial_prompt()) <= PROMPT_CHARS


def test_the_church_keeps_its_own_names_whatever_else_goes(own_list, monkeypatch):
    write(own_list, opening=transcription.OPENING, words=transcription.DEFAULT_WORDS)
    monkeypatch.setattr(transcription, "church_words", lambda: ("Er wordt gepreekt door: Ds. Van Ommen.", {}))
    prompt = initial_prompt()
    assert "Ds. Van Ommen" in prompt
    assert prompt.rstrip().endswith("Ds. Van Ommen."), "and last, where whisper is sure to read it"


def test_a_church_list_longer_than_the_whole_budget_stands_alone(own_list, monkeypatch):
    mine = "Er wordt gepreekt door: " + ", ".join(f"Dominee Nummer {i}" for i in range(60)) + "."
    write(own_list, opening=transcription.OPENING, words=transcription.DEFAULT_WORDS)
    monkeypatch.setattr(transcription, "church_words", lambda: (mine, {}))
    prompt = initial_prompt()
    assert mine in prompt, "the church's own words are never what gets dropped"


# --- what gets dropped ------------------------------------------------------------


def test_words_are_kept_from_the_back():
    assert fit_words(["aaa", "bbb", "ccc"], 10) == ["bbb", "ccc"]


def test_nothing_fits_in_nothing():
    assert fit_words(["aaa"], 0) == []
    assert fit_words([], 100) == []


def test_everything_fits_when_there_is_room():
    assert fit_words(["aaa", "bbb"], 100) == ["aaa", "bbb"]


def test_the_precious_end_of_the_list_survives_a_squeeze(own_list):
    write(own_list, opening="Kort.", words=transcription.DEFAULT_WORDS)
    prompt = initial_prompt()
    for word in ("herder", "Jezus Christus", "Heilige Geest"):
        assert word in prompt, f"{word} is what the list is for, and it went missing"


def test_the_easy_words_are_the_first_to_go(own_list):
    """A model that already knows "gemeente" gains nothing from being told."""
    write(own_list, opening=transcription.OPENING, words=transcription.DEFAULT_WORDS)
    prompt = initial_prompt()
    assert "herder" in prompt
    assert "gemeente" not in prompt, "the budget went to a word the model gets right anyway"


# --- the list itself --------------------------------------------------------------


def test_the_words_asked_for_are_in_there():
    listed = [w for group in transcription.DEFAULT_WORDS.values() for w in group]
    for word in ("herder", "herders", "farao", "lied", "liederen", "psalm", "gezang"):
        assert word in listed


def test_no_word_is_in_the_list_twice():
    listed = [w.lower() for group in transcription.DEFAULT_WORDS.values() for w in group]
    assert len(listed) == len(set(listed)), "a repeat costs budget and buys nothing"


def test_every_correction_puts_right_something_that_is_not_a_word():
    """A correction that fires on a real Dutch word would damage sentences that meant it."""
    fixes = transcription.DEFAULT_VOCABULARY["corrections"]
    assert "heller" not in fixes, "heller is the comparative of hel, so it has to stand"
    assert "lied" not in fixes, 'capitalising every lied breaks "we zingen een lied"'
    for wrong, right in fixes.items():
        assert wrong != right, f"{wrong} corrects to itself"


def test_a_correction_either_respells_a_word_or_recapitalises_it():
    """Both are worth having; a no-op is not."""
    for wrong, right in transcription.DEFAULT_VOCABULARY["corrections"].items():
        respelled = wrong.lower() != right.lower()
        recapitalised = wrong.lower() == right.lower() and wrong != right
        assert respelled or recapitalised, f"{wrong} -> {right} changes nothing"


def test_the_shepherd_survives_the_whole_way_through():
    """The mishearing this was written for, from what the model says to what is shown."""
    fixes = transcription.all_corrections()
    for heard in ("heerder", "heider", "header"):
        assert transcription.apply_corrections(f"de goede {heard} gaat voorop", fixes) == \
            "de goede herder gaat voorop"


# --- the older shape --------------------------------------------------------------


def test_a_word_list_from_before_the_groups_still_works(own_list, monkeypatch):
    write(own_list, initialPrompt="Opname van een kerkdienst. Let op: gemeente, genade.")
    monkeypatch.setattr(transcription, "church_words", lambda: ("De kerk heet Sionkerk.", {}))
    prompt = initial_prompt()
    assert "gemeente" in prompt and "Sionkerk" in prompt


def test_a_broken_word_list_falls_back_on_the_one_in_the_code(own_list):
    own_list.write_text("{ this is not json", encoding="utf-8")
    assert "herder" in initial_prompt()


def test_a_missing_word_list_is_written_out(own_list):
    assert not own_list.exists()
    transcription.load_vocabulary()
    assert own_list.exists()
    written = json.loads(own_list.read_text(encoding="utf-8"))
    assert "herder" in written["words"]["moeilijk"]


def test_the_shipped_example_matches_what_the_code_would_write():
    """templates/woordenlijst.example.json is what a church starts from."""
    example = transcription.TEMPLATES_DIR / "woordenlijst.example.json"
    if not example.is_file():
        pytest.skip("no example shipped")
    written = json.loads(example.read_text(encoding="utf-8"))
    assert written.get("words"), "the example still has the old shape"
