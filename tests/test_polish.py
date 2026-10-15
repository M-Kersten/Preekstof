"""Reading a clip back in its sentence, and everything the model is not allowed to do.

Subtitles sit under the face of a real person. The pass may swap a misheard word for what
was said, it may only bring in a name somebody wrote down or the service kept saying, and
it may do nothing else; every test below that says "geweigerd" is a way of getting that
wrong.
"""

import json

import pytest

from backend import polish
from backend.models import Segment, Transcript
from backend.polish import Swap

KNOWN = ["Efeziërs", "Ezechiël", "kerkenraad", "schriftlezing", "Heilige Geest",
         "ds. M. Kreuk", "Wittevrouwen", "barmhartigheid"]


@pytest.fixture
def known(monkeypatch):
    monkeypatch.setattr(polish, "known_words", lambda: list(KNOWN))
    return KNOWN


@pytest.fixture
def kept(tmp_path, monkeypatch):
    monkeypatch.setattr(polish, "TALLY", tmp_path / "verbeteringen.json")
    monkeypatch.setattr("backend.brands.learn_corrections", lambda pairs: None)
    return polish.TALLY


def lines(*texts) -> list[Segment]:
    return [Segment(start=i * 3.0, end=i * 3.0 + 2.8, text=t) for i, t in enumerate(texts)]


def swapped(segments, *swaps):
    return polish.apply(segments, list(swaps))


# --- what it is for -----------------------------------------------------------------


def test_a_misheard_name_is_put_right(known):
    said = lines("En dan lezen we uit de brief aan de eveneers.")
    out, pairs = swapped(said, Swap(line=0, wrong="eveneers", right="Efeziërs"))
    assert out[0].text == "En dan lezen we uit de brief aan de Efeziërs."
    assert pairs == {"eveneers": "Efeziërs"}


def test_everything_around_it_is_left_exactly_as_it_was(known):
    """No grammar, no punctuation, no tidying up a sentence that changed direction."""
    said = lines("De kerk en raad, eh, die vraagt uw... uw voorbede vanavond.")
    out, _ = swapped(said, Swap(line=0, wrong="kerk en raad", right="kerkenraad"))
    assert out[0].text == "De kerkenraad, eh, die vraagt uw... uw voorbede vanavond."


def test_only_the_line_it_names_is_touched(known):
    said = lines("Eerst dit.", "En dan de eveneers.", "En daarna dit.")
    out, _ = swapped(said, Swap(line=1, wrong="eveneers", right="Efeziërs"))
    assert [s.text for s in out] == ["Eerst dit.", "En dan de Efeziërs.", "En daarna dit."]


def test_the_timings_are_not_disturbed(known):
    said = lines("de brief aan de eveneers")
    out, _ = swapped(said, Swap(line=0, wrong="eveneers", right="Efeziërs"))
    assert (out[0].start, out[0].end) == (said[0].start, said[0].end)


def test_capitals_alone_are_a_fix_worth_making(known):
    said = lines("Wij bidden om de heilige geest.")
    out, pairs = swapped(said, Swap(line=0, wrong="heilige geest", right="Heilige Geest"))
    assert "Heilige Geest" in out[0].text
    assert pairs


def test_the_original_is_not_changed_underneath(known):
    said = lines("de eveneers")
    out, _ = swapped(said, Swap(line=0, wrong="eveneers", right="Efeziërs"))
    assert said[0].text == "de eveneers", "het origineel blijft staan"
    assert out[0].text != said[0].text


# --- and what it may not do -----------------------------------------------------------


def test_a_word_nobody_listed_is_refused(known):
    """It cannot introduce a name. Every name it reaches for is on a list."""
    said = lines("We lezen uit Wiebenga.")
    out, pairs = swapped(said, Swap(line=0, wrong="Wiebenga", right="Wiegersma"))
    assert out[0].text == said[0].text and pairs == {}


def test_a_rewrite_is_refused(known):
    """Two words for one is a sentence being edited, and the word timings are per word."""
    said = lines("De kerkenraad vraagt uw voorbede.")
    out, pairs = swapped(said, Swap(line=0, wrong="kerkenraad", right="ds. M. Kreuk"))
    assert out[0].text == said[0].text and pairs == {}


def test_a_different_word_is_refused_even_when_it_is_on_the_list(known):
    """It hears sounds. A fix that does not sound alike is not a fix, it is an opinion."""
    said = lines("Er is vanavond schriftlezing.")
    out, pairs = swapped(said, Swap(line=0, wrong="schriftlezing", right="barmhartigheid"))
    assert out[0].text == said[0].text and pairs == {}


def test_replacing_something_that_is_not_there_is_refused(known):
    said = lines("Een heel gewone zin.")
    out, pairs = swapped(said, Swap(line=0, wrong="eveneers", right="Efeziërs"))
    assert out[0].text == said[0].text and pairs == {}


def test_a_line_that_does_not_exist_is_refused(known):
    said = lines("Eén regel maar.")
    out, pairs = swapped(said, Swap(line=7, wrong="regel", right="Efeziërs"))
    assert out[0].text == said[0].text and pairs == {}


@pytest.mark.parametrize("wrong, right", [("", "Efeziërs"), ("eveneers", ""), ("  ", "  ")])
def test_an_empty_swap_is_refused(known, wrong, right):
    said = lines("de eveneers")
    out, pairs = swapped(said, Swap(line=0, wrong=wrong, right=right))
    assert out[0].text == said[0].text and pairs == {}


def test_a_swap_that_changes_nothing_is_not_counted(known):
    said = lines("de Efeziërs")
    _out, pairs = swapped(said, Swap(line=0, wrong="Efeziërs", right="Efeziërs"))
    assert pairs == {}


def test_only_whole_words_are_matched(known):
    """"raad" inside "kerkenraad" is not the word "raad"."""
    said = lines("De kerkenraadsvergadering is verzet.")
    out, _ = swapped(said, Swap(line=0, wrong="raad", right="kerkenraad"))
    assert out[0].text == said[0].text


def test_a_model_that_loses_the_plot_is_capped(known):
    said = lines(*[f"regel {i} met eveneers erin" for i in range(30)])
    out, pairs = swapped(said, *[Swap(line=i, wrong="eveneers", right="Efeziërs")
                                 for i in range(30)])
    assert len(pairs) <= 1  # one pair, and at most MOST_SWAPS lines touched
    assert sum(1 for s in out if "Efeziërs" in s.text) == polish.MOST_SWAPS


# --- what it should not have to think about twice ---------------------------------------


def test_the_first_time_is_only_counted(kept):
    assert polish.remember({"eveneers": "Efeziërs"}) == {}
    assert json.loads(kept.read_text(encoding="utf-8"))["eveneers"]["times"] == 1


def test_the_second_time_it_becomes_a_plain_correction(kept):
    polish.remember({"eveneers": "Efeziërs"})
    assert polish.remember({"eveneers": "Efeziërs"}) == {"eveneers": "Efeziërs"}
    assert "eveneers" not in json.loads(kept.read_text(encoding="utf-8")), "de telling is klaar"


def test_it_reaches_the_church_s_own_word_list(kept, monkeypatch):
    learned = {}
    monkeypatch.setattr("backend.brands.learn_corrections", lambda pairs: learned.update(pairs))
    polish.remember({"eveneers": "Efeziërs"})
    polish.remember({"eveneers": "Efeziërs"})
    assert learned == {"eveneers": "Efeziërs"}


def test_the_same_mishearing_fixed_two_ways_starts_counting_again(kept):
    """Two different answers are two different cases, and neither has been seen twice."""
    polish.remember({"eveneers": "Efeziërs"})
    assert polish.remember({"eveneers": "Ezechiël"}) == {}


def test_a_damaged_tally_is_not_a_crash(kept):
    kept.write_text("{ dit is geen json", encoding="utf-8")
    assert polish.tally() == {}
    assert polish.remember({"eveneers": "Efeziërs"}) == {}


def test_a_folder_that_cannot_be_written_costs_the_counting_and_not_the_swap(tmp_path, monkeypatch):
    """The swap already happened; counting it is a convenience."""
    unwritable = tmp_path / "dicht"
    unwritable.mkdir()
    unwritable.chmod(0o500)
    monkeypatch.setattr(polish, "TALLY", unwritable / "verbeteringen.json")
    try:
        polish.remember({"eveneers": "Efeziërs"})  # no exception
    finally:
        unwritable.chmod(0o700)


# --- and when the model is not there at all ----------------------------------------------


def test_switched_off_leaves_the_words_exactly_as_heard(monkeypatch):
    monkeypatch.setattr(polish, "ON", False)
    said = Transcript(language="nl", segments=lines("de eveneers"))
    out, pairs = polish.polish(said)
    assert out is said and pairs == {}


def test_no_key_is_not_a_reason_to_lose_the_clip(known, monkeypatch, capsys):
    monkeypatch.setattr("backend.discovery.check_provider",
                        lambda: (_ for _ in ()).throw(RuntimeError("geen sleutel")))
    said = Transcript(language="nl", segments=lines("de eveneers"))
    out, pairs = polish.polish(said)
    assert out is said and pairs == {}
    assert "overgeslagen" in capsys.readouterr().out


def test_an_empty_clip_asks_nothing(known, monkeypatch):
    monkeypatch.setattr("backend.discovery.check_provider",
                        lambda: pytest.fail("er hoort niets gevraagd te worden"))
    out, pairs = polish.polish(Transcript(language="nl", segments=[]))
    assert pairs == {}


def test_with_no_word_list_the_sentence_is_still_read(kept, monkeypatch):
    """A word that makes no sense where it stands needs no list to be put right."""
    monkeypatch.setattr(polish, "known_words", lambda: [])
    monkeypatch.setattr("backend.discovery.check_provider", lambda: None)
    monkeypatch.setattr("backend.discovery.ask", lambda *a, **k: polish.LlmSwaps(swaps=[
        Swap(line=0, wrong="zout de aarde", right="zout der aarde")]))
    said = Transcript(language="nl", segments=lines("Jullie zijn het zout de aarde."))
    out, pairs = polish.polish(said)
    assert out.segments[0].text == "Jullie zijn het zout der aarde."
    assert pairs == {"zout de aarde": "zout der aarde"}


def test_the_whole_thing_through_a_stubbed_model(known, kept, monkeypatch):
    monkeypatch.setattr("backend.discovery.check_provider", lambda: None)
    monkeypatch.setattr("backend.discovery.ask",
                        lambda *a, **k: polish.LlmSwaps(swaps=[
                            Swap(line=0, wrong="eveneers", right="Efeziërs"),
                            Swap(line=0, wrong="gewone", right="Wittevrouwen"),  # geweigerd
                        ]))
    said = Transcript(language="nl", segments=lines("de eveneers in een gewone zin"))
    out, pairs = polish.polish(said)
    assert out.segments[0].text == "de Efeziërs in een gewone zin"
    assert pairs == {"eveneers": "Efeziërs"}


def test_what_it_asks_carries_the_list_and_the_lines(known):
    asked = polish.question(lines("eerste regel", "tweede regel"), known)
    assert "Efeziërs" in asked
    assert "0: eerste regel" in asked and "1: tweede regel" in asked


# --- a word whisper split or joined ------------------------------------------------------


def test_a_word_it_split_in_two_is_put_back_together(known):
    """"kerk en raad" is "kerkenraad" with the spaces in the wrong place."""
    said = lines("De kerk en raad vergadert.")
    out, pairs = swapped(said, Swap(line=0, wrong="kerk en raad", right="kerkenraad"))
    assert out[0].text == "De kerkenraad vergadert."
    assert pairs == {"kerk en raad": "kerkenraad"}


def test_the_same_the_other_way_round(known):
    said = lines("Er is schriftle zing.")
    out, _ = swapped(said, Swap(line=0, wrong="schriftle zing", right="schriftlezing"))
    assert out[0].text == "Er is schriftlezing."


def test_a_different_number_of_words_is_still_refused_when_the_letters_differ(known):
    """Which is the rule the spacing case is an exception to, not a way around it."""
    said = lines("Wij danken voor zijn grote goedheid.")
    out, pairs = swapped(said, Swap(line=0, wrong="zijn grote goedheid", right="barmhartigheid"))
    assert out[0].text == said[0].text and pairs == {}


# --- against what whisper really produced -------------------------------------------------


@pytest.mark.parametrize("heard, meant", [
    ("Ezechiëel", "Ezechiël"),
    ("diakken", "diaken"),
    ("zontverming", "ontferming"),
    ("Jezaja", "Jesaja"),
    ("meidedeelingen", "mededelingen"),
    ("kerk en raad", "kerkenraad"),
    ("schriftle zing", "schriftlezing"),
    ("eveneers", "Efeziërs"),
])
def test_the_mistakes_this_model_really_makes_are_reachable(heard, meant):
    """Taken from what whisper wrote on two read-aloud test sentences, not invented."""
    assert polish.sounds_like(heard, meant)


@pytest.mark.parametrize("heard, meant", [
    ("schriftlezing", "barmhartigheid"),
    ("gemeente", "Openbaring"),
    ("vanavond", "Wittevrouwen"),
    ("lezen", "Efeziërs"),
    ("gebed", "Ezechiël"),
])
def test_swapping_in_an_unrelated_word_from_the_list_is_not(heard, meant):
    assert not polish.sounds_like(heard, meant)


def test_a_whole_clip_of_real_output(known, kept, monkeypatch):
    """The lines whisper produced yesterday, with the swaps a model would propose."""
    monkeypatch.setattr("backend.discovery.check_provider", lambda: None)
    monkeypatch.setattr("backend.discovery.ask", lambda *a, **k: polish.LlmSwaps(swaps=[
        Swap(line=0, wrong="Ezechiëel", right="Ezechiël"),
        Swap(line=1, wrong="kerk en raad", right="kerkenraad"),
        Swap(line=1, wrong="vanavond", right="Wittevrouwen"),  # geweigerd: ander woord
    ]))
    said = Transcript(language="nl", segments=lines(
        "De schriftlezing komt uit Ezechiëel.",
        "De kerk en raad vraagt uw voorbede vanavond."))
    out, pairs = polish.polish(said)
    assert out.segments[0].text == "De schriftlezing komt uit Ezechiël."
    assert out.segments[1].text == "De kerkenraad vraagt uw voorbede vanavond."
    assert pairs == {"ezechiëel": "Ezechiël", "kerk en raad": "kerkenraad"}


# --- read in the service around it --------------------------------------------------------

AROUND = polish.Context(before="We lazen uit het boek Ruth, over Naomi en haar schoondochter.",
                        after="Naomi ging terug naar Bethlehem.",
                        names=["Ruth", "Naomi", "Bethlehem", "Hendriks"],
                        about=["preek: De weg terug", "voorganger: ds. Pieter Visser"])


def test_an_ordinary_word_is_put_right_from_the_sentence(known):
    said = lines("Wij zijn geroepen om het zout de aarde te zijn.")
    out, pairs = swapped(said, Swap(line=0, wrong="zout de aarde", right="zout der aarde"))
    assert out[0].text == "Wij zijn geroepen om het zout der aarde te zijn."


def test_an_odd_name_where_ordinary_words_were_said_is_put_right(known):
    said = lines("Daarom Kees ik vandaag voor het leven.")
    out, _ = swapped(said, Swap(line=0, wrong="Kees", right="kies"))
    assert out[0].text == "Daarom kies ik vandaag voor het leven."


def test_a_name_the_service_keeps_saying_may_be_brought_in(known):
    said = lines("We bidden voor zuster Hendrix in het ziekenhuis.")
    out, _ = polish.apply(said, [Swap(line=0, wrong="Hendrix", right="Hendriks")], AROUND)
    assert out[0].text == "We bidden voor zuster Hendriks in het ziekenhuis."


def test_the_preacher_from_the_service_page_may_be_brought_in(known):
    said = lines("Dominee Fisser gaat voor.")
    out, _ = polish.apply(said, [Swap(line=0, wrong="Fisser", right="Visser")], AROUND)
    assert out[0].text == "Dominee Visser gaat voor."


def test_a_made_up_name_is_refused(known):
    """Sounds alike, and nobody ever said it: exactly what it must not invent."""
    said = lines("En toen zei Ruth tegen Nomi dat ze bleef.")
    out, pairs = polish.apply(said, [Swap(line=0, wrong="Nomi", right="Noemi")], AROUND)
    assert out[0].text == said[0].text and pairs == {}


def test_without_the_service_its_names_are_not_allowed_either(known):
    said = lines("We bidden voor zuster Hendrix in het ziekenhuis.")
    out, pairs = swapped(said, Swap(line=0, wrong="Hendrix", right="Hendriks"))
    assert out[0].text == said[0].text and pairs == {}


def test_a_capital_where_a_sentence_starts_is_only_grammar(known):
    said = lines("Hij bleef. Kees voor het leven, zei hij.")
    out, _ = swapped(said, Swap(line=0, wrong="Kees", right="Kies"))
    assert out[0].text == "Hij bleef. Kies voor het leven, zei hij."


def test_a_name_in_the_middle_of_a_fix_still_needs_a_list(known):
    said = lines("Daarom kies ik voor het Lefen.")
    out, pairs = swapped(said, Swap(line=0, wrong="het Lefen", right="het Leven"))
    assert out[0].text == said[0].text and pairs == {}


def test_a_fix_read_from_the_sentence_is_not_learned(known, kept, monkeypatch):
    """"de" was "der" in that line; in the next one it is "de" again."""
    monkeypatch.setattr("backend.discovery.check_provider", lambda: None)
    monkeypatch.setattr("backend.discovery.ask", lambda *a, **k: polish.LlmSwaps(swaps=[
        Swap(line=0, wrong="zout de aarde", right="zout der aarde"),
        Swap(line=0, wrong="eveneers", right="Efeziërs")]))
    said = Transcript(language="nl", segments=lines("Het zout de aarde, zegt de eveneers."))
    polish.polish(said)
    counted = json.loads(kept.read_text(encoding="utf-8"))
    assert list(counted) == ["eveneers"]


def test_what_it_asks_carries_the_service_around_it(known):
    asked = polish.question(lines("de regel zelf"), known, AROUND)
    assert "boek Ruth" in asked and "terug naar Bethlehem" in asked
    assert "Naomi" in asked and "ds. Pieter Visser" in asked
    assert asked.index("boek Ruth") < asked.index("0: de regel zelf") < asked.index("terug naar Bethlehem")


def test_the_names_are_those_the_service_keeps_saying():
    said = lines("Ruth bleef bij Naomi.", "En Naomi zei tegen Ruth: ga.", "Toen kwam Boaz.",
                 "Want Naomi wist het.", "De velden van Boaz.")
    names = polish.service_names(said)
    assert names[0] == "Naomi"
    assert "Boaz" in names and "Ruth" not in names  # Ruth once mid-sentence, once at the start
    assert "Want" not in names and "De" not in names and "Toen" not in names


def test_the_service_around_a_clip_is_a_few_minutes_and_not_the_hour(monkeypatch):
    from backend.models import ClipOrigin, Service

    hour = Transcript(language="nl", segments=[
        Segment(start=t, end=t + 9.0, text=f"zin op {t:.0f}") for t in range(0, 3600, 10)])
    monkeypatch.setattr(polish, "load_service", lambda _id: Service(
        id="s", createdAt="nu", title="Zondag", preacher="ds. Visser", transcript="t.json"))
    monkeypatch.setattr(polish, "load_service_transcript", lambda _s: hour)
    project = polish.Project.model_construct(origin=ClipOrigin(serviceId="s", start=1800.0, end=1860.0))
    found = polish.context_for(project)
    assert "zin op 1690" in found.before and "zin op 1790" in found.before
    assert "zin op 1660" not in found.before and "zin op 1810" not in found.before
    assert "zin op 1860" in found.after and "zin op 1970" in found.after
    assert "zin op 1990" not in found.after and "zin op 1840" not in found.after
    assert "voorganger: ds. Visser" in found.about


def test_a_clip_on_its_own_has_no_service_around_it():
    project = polish.Project.model_construct(origin=None)
    assert polish.context_for(project) is None


def test_a_service_that_is_gone_is_not_a_crash(monkeypatch):
    from backend.models import ClipOrigin

    monkeypatch.setattr(polish, "load_service", lambda _id: None)
    project = polish.Project.model_construct(origin=ClipOrigin(serviceId="weg", start=0, end=30))
    assert polish.context_for(project) is None


def test_a_very_fast_talker_does_not_double_the_question():
    many = [Segment(start=t, end=t + 1, text="woord " * 40) for t in range(0, 300)]
    said = polish.text_between(many, 0, 300, keep_end=True)
    assert len(said) <= polish.AROUND_CHARS + 2


def test_what_was_there_before_is_kept_out_of_sight(tmp_path):
    before = Transcript(language="nl", segments=lines("de eveneers"))
    polish.note(tmp_path / "work", before, {"eveneers": "Efeziërs"})
    kept = json.loads((tmp_path / "work" / "nagelezen.json").read_text(encoding="utf-8"))
    assert kept == {"swaps": {"eveneers": "Efeziërs"}, "before": ["de eveneers"]}


def test_nothing_changed_leaves_no_note(tmp_path):
    polish.note(tmp_path / "work", Transcript(language="nl", segments=lines("x")), {})
    assert not (tmp_path / "work").exists()


def test_a_name_from_the_bible_needs_no_list():
    """Whisper wrote this on a real sermon, next to Gideon and Jacob."""
    said = lines("dat lezen we over Jeremia, over Gideon, over Simpson, over Jacob")
    out, _ = polish.apply(said, [Swap(line=0, wrong="Simpson", right="Simson")])
    assert "over Simson, over Jacob" in out[0].text


def test_the_bible_names_are_not_sent_along(known):
    assert "Methusalem" not in polish.question(lines("een regel"), known, AROUND)
