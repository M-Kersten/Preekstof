"""The second slot beside the prompt, and why the two lists run opposite ways.

Whisper reads the last 223 tokens of `initial_prompt` and drops the head without a word.
`hotwords` is a budget of the same size beside it, and that one keeps the head and drops the
tail. Two budgets, two orderings, and thirty words that used to reach nothing at all.
"""

import pytest

from backend import transcription as tr


@pytest.fixture
def only_shared(monkeypatch):
    """No church of its own, so the shared list is all there is."""
    monkeypatch.setattr(tr, "own_terms", lambda: [])
    monkeypatch.setattr(tr, "church_words", lambda: ("", {}))


# --- the two ends -------------------------------------------------------------------


def test_the_prompt_keeps_the_end_of_the_list():
    """Ordered droppable-first, so what survives is what was worth protecting."""
    assert tr.fit_words(["weg", "ook weg", "kostbaar"], room=12) == ["kostbaar"]


def test_hotwords_keep_the_start_of_the_list():
    """The other budget is cut off at the back, so it runs the other way round."""
    assert tr.head_fit(["kostbaar", "minder", "weg"], room=12) == ["kostbaar"]


def test_neither_returns_more_than_fits():
    assert tr.head_fit(["aaa", "bbb", "ccc"], room=0) == []
    assert tr.fit_words(["aaa", "bbb", "ccc"], room=0) == []


# --- what actually reaches the model ---------------------------------------------------


def test_everything_the_prompt_dropped_lands_in_hotwords(only_shared):
    """Thirty of the seventy words used to reach the model nowhere at all."""
    listed = [w.strip() for g in (tr.load_vocabulary().get("words") or {}).values()
              for w in g if w.strip()]
    prompt, hot = tr.initial_prompt(), tr.hot_words()
    spilled = [w for w in listed if w not in prompt]
    assert spilled, "de prompt zit vol, anders zegt deze test niets"
    assert all(w in hot for w in spilled), "wat de prompt niet kon houden gaat hierheen"


def test_the_bible_books_reach_the_model_at_all(only_shared):
    """They sit in the part of the prompt that falls off, and they are the whole point."""
    everything = f"{tr.initial_prompt()} {tr.hot_words()}"
    for book in ("Genesis", "Exodus", "Openbaring", "Handelingen", "Jesaja"):
        assert book in everything


def test_nothing_is_sent_twice(only_shared):
    """A word in two lists costs the budget twice and buys nothing."""
    words = [w.strip() for w in tr.hot_words().split(",")]
    assert len(words) == len({w.lower() for w in words})


def test_hotwords_stay_inside_their_own_budget(only_shared):
    assert len(tr.hot_words()) <= tr.PROMPT_CHARS


def test_the_budgets_are_not_shared(only_shared):
    """Together they carry more than either could alone, which is the whole gain."""
    assert len(tr.initial_prompt()) + len(tr.hot_words()) > tr.PROMPT_CHARS


# --- the church's own names ------------------------------------------------------------


def test_the_church_s_own_names_lead(monkeypatch):
    """They are the thing the model cannot guess, and the head is what hotwords keeps."""
    monkeypatch.setattr(tr, "own_terms", lambda: ["ds. M. Kreuk", "Wittevrouwen"])
    assert tr.hot_words().startswith("ds. M. Kreuk, Wittevrouwen")


def test_they_are_in_the_prompt_as_well(monkeypatch):
    """Both slots, because a wrong preacher name is the error nobody forgives."""
    monkeypatch.setattr(tr, "church_words", lambda: ("Er wordt gepreekt door: ds. M. Kreuk.", {}))
    monkeypatch.setattr(tr, "own_terms", lambda: ["ds. M. Kreuk"])
    assert "ds. M. Kreuk" in tr.initial_prompt()
    assert "ds. M. Kreuk" in tr.hot_words()


def test_a_broken_brand_costs_the_names_and_not_the_transcription(monkeypatch):
    monkeypatch.setattr("backend.brands.active",
                        lambda: (_ for _ in ()).throw(RuntimeError("stuk")))
    assert tr.own_terms() == []
    assert tr.hot_words(), "de gedeelde lijst gaat gewoon door"


# --- words a church adds itself ----------------------------------------------------------


def test_words_a_church_adds_go_in_front_of_the_leftovers(monkeypatch, only_shared):
    """Somebody chose those by hand; the leftovers are what a default list had over."""
    vocabulary = dict(tr.load_vocabulary())
    vocabulary["hotwords"] = ["Habakuk", "Zefanja"]
    monkeypatch.setattr(tr, "load_vocabulary", lambda: vocabulary)
    said = tr.hot_words()
    assert said.startswith("Habakuk, Zefanja")


def test_an_empty_list_is_the_ordinary_case(only_shared):
    assert isinstance(tr.load_vocabulary().get("hotwords"), list)


def test_a_word_list_from_before_this_still_works(monkeypatch, only_shared):
    """No hotwords key at all, which is every file written before today."""
    vocabulary = {k: v for k, v in tr.load_vocabulary().items() if k != "hotwords"}
    monkeypatch.setattr(tr, "load_vocabulary", lambda: vocabulary)
    assert tr.hot_words()
