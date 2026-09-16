"""Where a caption breaks, and whether anybody could read it in time.

Most social viewing is muted, so the captions are the clip. A line break in the wrong place
is the difference between something that looks made and something that looks generated.
"""

import pytest

from backend import transcription
from backend.transcription import MAX_CHARS, MAX_DURATION, Word, chunk_words


def spoken(text: str, start: float = 0.0, pace: float = 0.35, pauses: dict | None = None):
    """Words with plausible timings; `pauses` adds silence before the word at that index."""
    words, at = [], start
    for i, word in enumerate(text.split()):
        at += (pauses or {}).get(i, 0.0)
        words.append(Word(round(at, 2), round(at + pace, 2), word))
        at += pace
    return words


def texts(words) -> list[str]:
    return [s.text for s in chunk_words(words)]


def ending(line: str) -> str:
    return line.split()[-1]


# --- the lines it makes -----------------------------------------------------------


def test_a_short_sentence_stays_in_one_piece():
    assert texts(spoken("God is op zoek naar jou.")) == ["God is op zoek naar jou."]


def test_nothing_said_makes_no_lines():
    assert chunk_words([]) == []


def test_no_line_is_wider_than_a_caption():
    words = spoken("Niet omdat je perfect bent maar omdat hij van je houdt en dat "
                   "verandert alles wat je dacht te weten over genade en vergeving")
    assert all(len(line) <= MAX_CHARS for line in texts(words))


def test_no_line_outstays_its_welcome():
    words = spoken("een twee drie vier vijf zes zeven acht negen tien elf twaalf", pace=0.9)
    for seg in chunk_words(words):
        assert seg.end - seg.start <= MAX_DURATION + 0.01


def test_every_word_is_used_once_and_in_order():
    words = spoken("Hij wil dat je dichter bij hem komt en dat is niet iets wat je zelf "
                   "hoeft te verdienen want het is hem om jou te doen")
    assert " ".join(texts(words)).split() == [w.word for w in words]


def test_the_times_follow_the_words():
    words = spoken("God is op zoek naar jou en hij vindt je ook als jij niet zoekt")
    made = chunk_words(words)
    assert made[0].start == words[0].start
    assert made[-1].end == words[-1].end
    for one, next_one in zip(made, made[1:]):
        assert next_one.start >= one.end


# --- where it breaks --------------------------------------------------------------


def test_a_full_stop_ends_a_line():
    words = spoken("Dat is genade en niets anders. Daar begint het mee en daar houdt het niet op")
    assert texts(words)[0] == "Dat is genade en niets anders."


def test_a_full_stop_too_early_does_not_end_a_line():
    """Three words on a line of their own reads as a stutter."""
    assert texts(spoken("Ja. Daar gaat het vanmorgen over in deze dienst"))[0] != "Ja."


def test_a_line_does_not_end_on_a_word_that_leans_on_the_next_one():
    words = spoken("Hij wil dat je dichter bij hem komt en dat hij dat zelf doet in jou")
    for line in texts(words)[:-1]:
        last = ending(line)
        if not last.endswith(transcription.ENDS_SENTENCE + transcription.ENDS_CLAUSE):
            assert transcription.plain(Word(0, 0, last)) not in transcription.LEANS_FORWARD


def test_a_comma_is_a_better_break_than_the_middle_of_a_phrase():
    words = spoken("Niet omdat je perfect bent, maar omdat hij van je houdt en blijft houden")
    assert texts(words)[0].endswith(",")


def test_a_silence_breaks_the_line_wherever_it_falls():
    words = spoken("God is op zoek naar jou", pauses={3: 1.2})
    assert texts(words)[0] == "God is op"


def test_a_breath_is_a_better_break_than_no_breath():
    """Half a second is under the hard limit and still where the sentence takes air."""
    words = spoken("God is op zoek naar jou en hij vindt je waar je ook bent", pauses={6: 0.5})
    assert texts(words)[0] == "God is op zoek naar jou"


def test_a_line_may_start_with_the_word_that_carries_the_sentence_on():
    words = spoken("Hij houdt van je zoals je bent, maar dat betekent niet dat alles "
                   "vanzelf goed gaat in je leven")
    assert any(line.startswith(("maar", "want", "omdat", "en ")) for line in texts(words)[1:])


def test_breaking_early_beats_breaking_badly():
    """A good break at half a line wins from a bad one at the character limit."""
    words = spoken("Hij zoekt jou en niemand anders. Niet de mens die je zou willen zijn "
                   "op je allerbeste dag")
    assert texts(words)[0] == "Hij zoekt jou en niemand anders."


# --- how it reads over a longer stretch -------------------------------------------

SERMON = (
    "God is op zoek naar jou. Niet omdat je perfect bent, maar omdat hij van je houdt. "
    "Hij wil dat je dichter bij hem komt, en dat is geen kwestie van harder je best doen. "
    "Wat is God vandaag aan het doen in jouw leven, denk je? Misschien wel meer dan je ziet. "
    "De herder is verdwenen voor even, zingt Stef Bos, en toch is hij er. "
    "Ook in de kerk kun je je verlaten voelen, verlaten door de ander en door God zelf. "
    "Wie zijn de arme schapen in deze stad, en wie zijn dat hier in ons midden? "
    "Wij zijn het zelf, met zijn allen zo alleen, en dat mag gezegd worden. "
    "In de tekst die we lazen zie je wel degelijk dat Jezus als de goede herder aanwezig is. "
    "De herders die het volk hadden moeten weiden, die geven niet thuis. "
    "Dat zie je niet meteen, en toch is het er, want hij ziet ons allemaal. "
    "Misschien vind je het moeilijk om mee te zingen met de liederen van vanmorgen. "
    "Omdat je de herder zo mist, of omdat het geloof van vroeger je is ontglipt."
)


def test_most_lines_end_where_the_sentence_takes_a_breath():
    lines = texts(spoken(SERMON))
    assert len(lines) >= 20, "a sample worth drawing a conclusion from"
    breathing = sum(1 for line in lines
                    if line.strip().endswith(transcription.ENDS_SENTENCE + transcription.ENDS_CLAUSE))
    assert breathing / len(lines) >= 0.75, f"only {breathing} of {len(lines)} lines end on punctuation"


def test_almost_no_line_is_left_hanging():
    lines = texts(spoken(SERMON))
    hanging = [ending(line) for line in lines[:-1]
               if not ending(line).endswith(transcription.ENDS_SENTENCE + transcription.ENDS_CLAUSE)
               and transcription.plain(Word(0, 0, ending(line))) in transcription.LEANS_FORWARD]
    assert len(hanging) <= 1, f"lines left hanging: {hanging}"


def test_lines_are_not_shredded_into_scraps():
    lines = texts(spoken(SERMON))
    average = sum(len(line) for line in lines) / len(lines)
    assert average >= 25, f"average line is {average:.0f} characters, which is a lot of flicker"


# --- the scoring itself -----------------------------------------------------------


LONG_ENOUGH = "dat is genade en niets minder"  # past MIN_CHARS, so punctuation counts


def test_a_sentence_end_scores_above_a_comma_above_nothing():
    at = len(LONG_ENOUGH.split())
    stop = spoken(f"{LONG_ENOUGH}. en")
    comma = spoken(f"{LONG_ENOUGH}, en")
    nothing = spoken(f"{LONG_ENOUGH} en")
    assert (transcription.break_score(stop, 0, at)
            > transcription.break_score(comma, 0, at)
            > transcription.break_score(nothing, 0, at))


def test_punctuation_on_a_line_too_short_to_keep_counts_for_nothing():
    """Otherwise "Ja." wins every time, and the captions stutter."""
    short = spoken("Ja. daar gaat het over")
    assert transcription.break_score(short, 0, 1) < 0


def test_a_longer_silence_scores_higher():
    at = len(LONG_ENOUGH.split())
    short = spoken(f"{LONG_ENOUGH} en", pauses={at: 0.2})
    long = spoken(f"{LONG_ENOUGH} en", pauses={at: 0.6})
    assert transcription.break_score(long, 0, at) > transcription.break_score(short, 0, at)


def test_a_silence_outweighs_a_word_that_leans_on_the_next_one():
    """The bug this was written for: a caption forced to end at a silence kept being cut
    short instead, because the word before the silence happened to be "op"."""
    at = len(LONG_ENOUGH.split())
    words = spoken(f"{LONG_ENOUGH} op tafel", pauses={at + 1: transcription.PAUSE_SPLIT + 0.5})
    assert transcription.break_score(words, 0, at + 1) > 0


def test_ending_on_a_leaning_word_is_punished():
    leaning = spoken("dat is genade en niets van")
    solid = spoken("dat is genade en niets minder")
    at = 6
    assert transcription.break_score(leaning, 0, at) < transcription.break_score(solid, 0, at)


def test_punctuation_does_not_hide_a_leaning_word():
    assert transcription.plain(Word(0, 0, "van,")) == "van"
    assert transcription.plain(Word(0, 0, '"Heer!"')) == "heer"


# --- the timings that make the highlight possible ---------------------------------


def test_the_words_are_kept_with_their_times():
    made = chunk_words(spoken("God is op zoek naar jou"))
    assert [w.word for w in made[0].words] == "God is op zoek naar jou".split()
    assert made[0].words[0].start == made[0].start
    assert made[0].words[-1].end == made[0].end


def test_a_clip_cut_from_a_service_keeps_the_times_it_needs():
    from backend.clips import slice_transcript
    from backend.models import Transcript

    whole = Transcript(language="nl", segments=chunk_words(spoken("God is op zoek naar jou "
                                                                  "en hij vindt je ook", start=100.0)))
    piece = slice_transcript(whole, 100.0, 108.0)
    assert piece.segments[0].words, "the timings went missing on the way into the clip"
    assert piece.segments[0].words[0].start == pytest.approx(piece.segments[0].start)


def test_the_times_survive_being_written_down_and_read_back(tmp_path, monkeypatch):
    from backend import models
    from backend.models import Output, Project, Transcript

    monkeypatch.setattr(models, "PROJECTS_DIR", tmp_path)
    (tmp_path / "clip").mkdir()
    project = Project(id="clip", createdAt="2026-01-01T10:00:00", output=Output())
    models.save_project(project)
    models.save_transcript(project, Transcript(language="nl",
                                               segments=chunk_words(spoken("God is op zoek"))))
    back = models.load_transcript(models.load_project("clip"))
    assert [w.word for w in back.segments[0].words] == ["God", "is", "op", "zoek"]
