"""Reading the words back in their sentence, which is what hotwords cannot do.

Whisper hears sounds. Told to expect "Efeziërs" it will lean that way, and on a bad
microphone it still writes "eveneers", because nothing in a speech model knows that only
one word can follow "de brief aan de". A language model reading the finished line knows
that in an instant, and it has no size limit: the whole word list, every preacher's name,
all of it fits in one question about sixty seconds of text.

So this runs after a clip has been heard properly, and it is deliberately not allowed to
write. It proposes swaps, and a swap only happens when all of this holds:

    the replacement is a word already on a list somebody wrote down,
    what it replaces really is in that line,
    the two are the same number of words,
    and they sound enough alike to be a mishearing rather than a different word.

Everything else is dropped without argument. The model cannot introduce a word nobody
listed, cannot rewrite a sentence, and cannot tidy up the grammar of a preacher who
changed direction halfway. Subtitles sit under the face of a real person, and what they
say has to be what was said.

One word for one word is also what keeps the karaoke caption honest:
`subtitles.word_times` uses whisper's own per-word timings while the count still matches
the text, and falls back to guessing from word lengths when it does not.

What it fixes twice it should not have to think about a third time, so a swap that keeps
coming back is promoted to an ordinary correction and handled for free after that.
"""

import json
import re

from pydantic import BaseModel

from difflib import SequenceMatcher

from . import settings
from .models import Segment, TEMPLATES_DIR, Transcript, write_atomic

ON = settings.text("POLISH_CLIPS", "1").strip().lower() not in ("0", "false", "nee", "off")
EFFORT = settings.choice("POLISH_EFFORT", ("low", "medium", "high", "xhigh", "max"), "low")

TALLY = TEMPLATES_DIR / "verbeteringen.json"
LEARN_AFTER = 2  # seen this many times, it becomes a plain correction and costs nothing
MOST_SWAPS = 12  # a clip of a minute with more than this is a model that has lost the plot
MOST_WORDS = 4  # a swap longer than a few words is a rewrite

# How alike two spellings have to be before this counts as a mishearing rather than a
# different word. Whisper writes down what it heard, so a misheard name keeps the shape of
# the sound and loses the letters: "eveneers" for "Efeziërs" shares half its characters.
#
# wordlearn has its own, stricter number for the same shape of question. The jobs differ:
# there a person typed the replacement and it goes into the word list for good, so caution
# is cheap. Here the replacement is already on a list somebody wrote, and the change lasts
# one clip.
#
# Measured on a hand-made set of twenty pairs: real mishearings ran from 0.50 up, and swaps
# to an unrelated word on the list stopped at 0.46. Twenty pairs is not a lot of evidence
# for a safety line, which is why it is not the only guard: a word has to be on the list,
# stand in that line, and come back with the same number of words before this is asked.
SOUNDS_ALIKE = 0.48

SYSTEM = (
    "Je krijgt de ondertitels van een fragment uit een Nederlandse kerkdienst, uitgeschreven "
    "door een spraakmodel, en een lijst met woorden die in deze kerk voorkomen.\n\n"
    "Zoek plekken waar het spraakmodel een woord verkeerd verstaan heeft en waar een woord "
    "uit de lijst er duidelijk hoort te staan. Denk aan namen, bijbelboeken en kerkwoorden: "
    "die klinken bekend maar staan er verhaspeld.\n\n"
    "Regels, en hier mag je niet van afwijken:\n"
    "- Vervang alleen door een woord dat letterlijk in de lijst staat.\n"
    "- Wat je vervangt moet precies zo in die regel staan.\n"
    "- Evenveel woorden terug als je weghaalt. Eén woord voor één woord, twee voor twee.\n"
    "- Alleen als het erop lijkt qua klank. Een ander woord is geen verbetering.\n"
    "- Raak niets anders aan. Geen grammatica, geen interpunctie, geen zinnen mooier maken. "
    "Een spreker die halverwege van richting verandert, heeft dat zo gezegd.\n"
    "- Twijfel je, doe het dan niet. Een gemiste fout is niet erg; een verzonnen verbetering "
    "staat straks onder iemands gezicht.\n\n"
    "Vind je niets, geef dan een lege lijst terug."
)


class Swap(BaseModel):
    line: int  # which caption, counted from 0
    wrong: str  # exactly as it stands there now
    right: str  # exactly as it stands in the list


class LlmSwaps(BaseModel):
    swaps: list[Swap]


def known_words() -> list[str]:
    """Everything a swap is allowed to reach for: the shared list and this church's own."""
    from . import transcription

    vocabulary = transcription.load_vocabulary()
    words = [w.strip() for group in (vocabulary.get("words") or {}).values()
             for w in group if w.strip()]
    words += [w.strip() for w in vocabulary.get("hotwords") or [] if w.strip()]
    words += transcription.own_terms()
    # What the church already fixed by hand is by definition what it says.
    words += [v.strip() for v in vocabulary.get("corrections", {}).values() if v.strip()]
    try:
        from . import brands

        words += [v.strip() for v in brands.active().vocabulary.corrections.values() if v.strip()]
    except Exception:  # noqa: BLE001  a broken brand costs the names, not the pass
        pass
    seen: list[str] = []
    for word in words:
        if word and word.lower() not in {w.lower() for w in seen}:
            seen.append(word)
    return seen


def question(segments: list[Segment], known: list[str]) -> str:
    lines = "\n".join(f"{i}: {s.text.strip()}" for i, s in enumerate(segments))
    return (f"Woorden die in deze kerk voorkomen:\n{', '.join(known)}\n\n"
            f"De ondertitels:\n{lines}")


def only_spacing(heard: str, meant: str) -> bool:
    """The same letters with the spaces somewhere else: a word split or joined."""
    return heard.lower().replace(" ", "") == meant.lower().replace(" ", "")


def sounds_like(heard: str, meant: str) -> bool:
    """Whether `meant` is a plausible reading of `heard` rather than a different word."""
    if not heard or not meant or heard == meant:
        return False
    if heard.lower() == meant.lower():
        return True  # only the capitals, which is how a name is usually put right
    if only_spacing(heard, meant):
        return True  # "schriftle zing" is "schriftlezing"
    return SequenceMatcher(a=heard.lower(), b=meant.lower()).ratio() >= SOUNDS_ALIKE


def found_in(line: str, wrong: str) -> re.Match | None:
    """Where `wrong` sits in the line, as whole words and whatever the capitals are."""
    if not wrong.strip():
        return None
    return re.search(rf"\b{re.escape(wrong.strip())}\b", line, re.IGNORECASE)


def usable(swap: Swap, segments: list[Segment], known: set[str]) -> bool:
    """Whether this swap is one the model was allowed to make."""
    if not (0 <= swap.line < len(segments)):
        return False
    wrong, right = swap.wrong.strip(), swap.right.strip()
    if not wrong or not right or right.lower() not in known:
        return False
    if len(wrong.split()) > MOST_WORDS or len(right.split()) > MOST_WORDS:
        return False
    if len(wrong.split()) != len(right.split()) and not only_spacing(wrong, right):
        # One word for one keeps whisper's own per-word timings, which is what the caption
        # lights up on. The exception is a word it split or joined: "kerk en raad" is
        # "kerkenraad" with two spaces in the wrong place, and refusing that to protect the
        # timings would be protecting the timings of a word that is not there. That one
        # caption falls back to spreading the words by length, the same as a line somebody
        # corrected by hand.
        return False
    if found_in(segments[swap.line].text, wrong) is None:
        return False
    return sounds_like(wrong, right)


def swap_into(line: str, wrong: str, right: str) -> str:
    """Put `right` where `wrong` stands, and leave every other character alone."""
    found = found_in(line, wrong)
    return line if found is None else line[:found.start()] + right + line[found.end():]


def apply(segments: list[Segment], swaps: list[Swap]) -> tuple[list[Segment], dict[str, str]]:
    """The captions with the good swaps made, and the pairs that were made."""
    known = {w.lower() for w in known_words()}
    out = [s.model_copy(deep=True) for s in segments]
    pairs: dict[str, str] = {}
    for swap in swaps[:MOST_SWAPS]:
        if not usable(swap, out, known):
            continue
        line = out[swap.line]
        after = swap_into(line.text, swap.wrong.strip(), swap.right.strip())
        if after == line.text:
            continue
        line.text = after
        pairs[swap.wrong.strip().lower()] = swap.right.strip()
    return out, pairs


# --- what it should not have to think about twice ---------------------------------


def tally() -> dict:
    try:
        said = json.loads(TALLY.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return said if isinstance(said, dict) else {}


def remember(pairs: dict[str, str]) -> dict[str, str]:
    """Count what was fixed, and hand back what has now been seen often enough to keep.

    A swap the model makes once could be a one-off. The same swap on a second clip is this
    church's own vocabulary, and belongs in the list where it costs nothing to apply.
    """
    if not pairs:
        return {}
    seen = tally()
    learned: dict[str, str] = {}
    for wrong, right in pairs.items():
        row = seen.get(wrong)
        times = (row.get("times", 0) if isinstance(row, dict) and row.get("right") == right else 0) + 1
        if times >= LEARN_AFTER:
            learned[wrong] = right
            seen.pop(wrong, None)
        else:
            seen[wrong] = {"right": right, "times": times}
    try:
        TALLY.parent.mkdir(parents=True, exist_ok=True)
        write_atomic(TALLY, json.dumps(seen, indent=2, ensure_ascii=False))
    except OSError:
        pass  # counting is a convenience; the swap itself already happened
    if learned:
        try:
            from . import brands

            brands.learn_corrections(learned)
        except Exception as exc:  # noqa: BLE001
            print(f"[woorden] geleerde verbetering kon niet bewaard worden: {exc}")
    return learned


def polish(transcript: Transcript) -> tuple[Transcript, dict[str, str]]:
    """Read the captions back against the word list. Never a reason for anything to fail."""
    from . import discovery

    if not ON or not transcript.segments:
        return transcript, {}
    known = known_words()
    if not known:
        return transcript, {}
    try:
        discovery.check_provider()
        answer = discovery.ask(question(transcript.segments, known), SYSTEM, LlmSwaps, EFFORT)
    except Exception as exc:  # noqa: BLE001  the clip is written out and usable as it is
        print(f"[woorden] nalezen overgeslagen: {exc}")
        return transcript, {}
    segments, pairs = apply(transcript.segments, getattr(answer, "swaps", []) or [])
    if not pairs:
        return transcript, {}
    learned = remember(pairs)
    if learned:
        print(f"[woorden] geleerd: {', '.join(f'{k} → {v}' for k, v in learned.items())}")
    return Transcript(language=transcript.language, segments=segments), pairs
