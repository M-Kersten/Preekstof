"""Reading the words back in their sentence, which is what hotwords cannot do.

Whisper hears sounds. Told to expect "Efeziërs" it will lean that way, and on a bad
microphone it still writes "eveneers", because nothing in a speech model knows that only
one word can follow "de brief aan de". A language model reading the finished line knows
that in an instant. It knows "het zout de aarde" is "het zout der aarde" too, and that a
preacher who just read from Ruth did not mean somebody called "Kees Fluit" two lines on.

So this runs after a clip has been heard properly, with a little of the service around it
to read the clip in: a couple of minutes before and after, the names that keep coming back
in the whole service, and what the church said the service was about. Not the whole
service. Those few minutes are what a person would need to see that a word is wrong, and
the full hour would cost twenty times as much for the same answer.

It is deliberately not allowed to write. It proposes swaps, and a swap only happens when
all of this holds:

    what it replaces really is in that line,
    the two are the same number of words (or the same letters with the spaces moved),
    they sound enough alike to be a mishearing rather than a different word,
    and any name it brings in is one somebody wrote down, the service itself keeps saying,
    or the Bible has (bijbelnamen).

Everything else is dropped without argument. The model cannot invent a name, cannot
rewrite a sentence, and cannot tidy up the grammar of a preacher who changed direction
halfway. Subtitles sit under the face of a real person, and what they say has to be what
was said.

What it changes is not marked in the editor. These are small fixes to words nobody meant,
and the text simply reads as it should. What the clip said before is kept beside it in the
work folder, for whoever wants to know.

One word for one word is also what keeps the karaoke caption honest:
`subtitles.word_times` uses whisper's own per-word timings while the count still matches
the text, and falls back to guessing from word lengths when it does not.

A swap to a word on the list that keeps coming back is promoted to an ordinary correction
and handled for free after that. A fix read from the sentence is not: "hem" was "hen" in
that line, and in the next one it will be "hem" again.
"""

import json
import re
from collections import Counter
from dataclasses import dataclass, field
from difflib import SequenceMatcher
from pathlib import Path

from pydantic import BaseModel

from . import settings
from .models import OWN_TEMPLATES, Project, Segment, Transcript, load_service, load_service_transcript, write_atomic

ON = settings.text("POLISH_CLIPS", "1").strip().lower() not in ("0", "false", "nee", "off")
EFFORT = settings.choice("POLISH_EFFORT", ("low", "medium", "high", "xhigh", "max"), "low")

TALLY = OWN_TEMPLATES / "verbeteringen.json"
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

# Around the clip, to read it in. Two minutes either side is a person's worth of "what was
# this about"; the cap in characters keeps a fast talker from doubling the bill.
AROUND = 120.0
AROUND_CHARS = 2400
MOST_NAMES = 60
NAME_AT_LEAST = 2  # a name said once in an hour is as likely a mishearing as a name

SYSTEM = (
    "Je krijgt de ondertitels van een fragment uit een Nederlandse kerkdienst, uitgeschreven "
    "door een spraakmodel. Om ze te kunnen lezen krijg je ook wat er vlak voor en vlak na "
    "gezegd werd, de namen die in deze dienst vaker vallen, wat de kerk over de dienst "
    "schreef en een lijst met woorden die in deze kerk voorkomen.\n\n"
    "Zoek plekken waar het spraakmodel iets verkeerd verstaan heeft en waar uit de zin of "
    "uit de dienst duidelijk is wat er gezegd werd. Denk aan namen en bijbelboeken die "
    "verhaspeld zijn, aan een gewoon woord dat in de zin geen betekenis heeft terwijl een "
    "woord dat er bijna hetzelfde klinkt dat wel heeft, en aan een vreemde naam die er "
    "staat waar de spreker gewone woorden zei.\n\n"
    "Regels, en hier mag je niet van afwijken:\n"
    "- Wat je vervangt moet precies zo in die regel staan. Alleen de genummerde regels; "
    "de tekst ervoor en erna is om te lezen.\n"
    "- Evenveel woorden terug als je weghaalt. Eén woord voor één woord, twee voor twee. "
    "Alleen een woord dat in stukken is geknipt of aan elkaar is geplakt mag je heel maken.\n"
    "- Alleen als het erop lijkt qua klank. Een ander woord is geen verbetering.\n"
    "- Verzin geen namen. Een naam die je erin zet, staat in de lijst, bij de namen uit "
    "deze dienst of in wat de kerk over de dienst schreef, of komt uit de Bijbel.\n"
    "- Raak niets anders aan. Geen grammatica, geen interpunctie, geen zinnen mooier maken. "
    "Een spreker die halverwege van richting verandert, heeft dat zo gezegd.\n"
    "- Twijfel je, doe het dan niet. Een gemiste fout is niet erg; een verzonnen verbetering "
    "staat straks onder iemands gezicht.\n\n"
    "Vind je niets, geef dan een lege lijst terug."
)


class Swap(BaseModel):
    line: int  # which caption, counted from 0
    wrong: str  # exactly as it stands there now
    right: str  # what was said


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


@dataclass
class Context:
    """What the clip is read in: a little of the service around it, and its names."""

    before: str = ""
    after: str = ""
    names: list[str] = field(default_factory=list)
    about: list[str] = field(default_factory=list)


WORD = re.compile(r"[^\W\d_][\w'’.-]*", re.UNICODE)


def bare(token: str) -> str:
    return token.strip(".,;:!?\"'’“”()[]…-").lower()


def service_names(segments: list[Segment]) -> list[str]:
    """Capitalised words the service keeps saying where no sentence starts.

    Read from the quick scan of the whole service, locally, so the question about one clip
    can carry "this service mentions Ruth and Naomi" without carrying the hour it came from.
    """
    counted: Counter[str] = Counter()
    spelled: dict[str, str] = {}
    lower: Counter[str] = Counter()
    for segment in segments:
        starts = True
        for token in segment.text.split():
            word = token.strip(".,;:!?\"'’“”()[]…")
            if word and word[0].isupper() and not starts and WORD.fullmatch(word):
                counted[word.lower()] += 1
                spelled.setdefault(word.lower(), word)
            elif word:
                lower[word.lower()] += 1
            starts = token.endswith((".", "!", "?", ":"))
    names = [w for w, n in counted.most_common() if n >= NAME_AT_LEAST and counted[w] > lower[w]]
    return [spelled[w] for w in names[:MOST_NAMES]]


def text_between(segments: list[Segment], start: float, end: float, keep_end: bool) -> str:
    """The words said between two moments, cut to AROUND_CHARS from the side away from the clip."""
    said = " ".join(s.text.strip() for s in segments
                    if s.end > start and s.start < end and s.text.strip())
    if len(said) <= AROUND_CHARS:
        return said
    return ("… " + said[-AROUND_CHARS:].split(" ", 1)[-1]) if keep_end else (said[:AROUND_CHARS].rsplit(" ", 1)[0] + " …")


def context_for(project: Project) -> Context | None:
    """The service around a clip that was cut from one. A clip uploaded on its own has none."""
    origin = project.origin
    if origin is None:
        return None
    try:
        service = load_service(origin.serviceId)
        heard = load_service_transcript(service) if service else None
    except (OSError, ValueError):
        return None
    if service is None:
        return None
    about = [f"{label}: {value.strip()}" for label, value in
             (("titel", service.title), ("preek", service.sermonTitle), ("serie", service.series),
              ("voorganger", service.preacher)) if value and value.strip()]
    if heard is None or not heard.segments:
        return Context(about=about)
    return Context(
        before=text_between(heard.segments, origin.start - AROUND, origin.start + 0.5, keep_end=True),
        after=text_between(heard.segments, origin.end - 0.5, origin.end + AROUND, keep_end=False),
        names=service_names(heard.segments),
        about=about,
    )


def question(segments: list[Segment], known: list[str], context: Context | None = None) -> str:
    lines = "\n".join(f"{i}: {s.text.strip()}" for i, s in enumerate(segments))
    parts: list[str] = []
    if context and context.about:
        parts.append("Over deze dienst:\n" + "\n".join(context.about))
    if context and context.names:
        parts.append("Namen die in deze dienst vaker vallen:\n" + ", ".join(context.names))
    if known:
        parts.append(f"Woorden die in deze kerk voorkomen:\n{', '.join(known)}")
    if context and context.before:
        parts.append(f"Vlak ervoor gezegd (alleen om te lezen):\n{context.before}")
    parts.append(f"De ondertitels:\n{lines}")
    if context and context.after:
        parts.append(f"Vlak erna gezegd (alleen om te lezen):\n{context.after}")
    return "\n\n".join(parts)


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


def names_allowed(known: list[str] | set[str], context: Context | None = None) -> set[str]:
    """Every name a swap may bring in, as bare lowercase words."""
    from .bijbelnamen import NAMES

    pool = list(known) + list(NAMES)
    if context:
        pool += context.names + [value.split(":", 1)[-1] for value in context.about]
    return {bare(token) for entry in pool for token in entry.split() if bare(token)}


def starts_sentence(line: str, at: int) -> bool:
    before = line[:at].rstrip()
    return not before or before[-1] in ".!?:\"'“”"


def usable(swap: Swap, segments: list[Segment], allowed: set[str]) -> bool:
    """Whether this swap is one the model was allowed to make.

    `allowed` holds the names it may bring in (names_allowed). An ordinary word read from
    the sentence needs no list; a name does, because a name is the thing it would make up.
    """
    if not (0 <= swap.line < len(segments)):
        return False
    wrong, right = swap.wrong.strip(), swap.right.strip()
    if not wrong or not right:
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
    found = found_in(segments[swap.line].text, wrong)
    if found is None:
        return False
    first = starts_sentence(segments[swap.line].text, found.start())
    for i, token in enumerate(right.split()):
        if token[:1].isupper() and bare(token) not in allowed and not (i == 0 and first):
            # A capital where a sentence starts is grammar, not a name. Anywhere else it is
            # a name, and a name nobody wrote down and the service never said is made up.
            return False
    return sounds_like(wrong, right)


def swap_into(line: str, wrong: str, right: str) -> str:
    """Put `right` where `wrong` stands, and leave every other character alone."""
    found = found_in(line, wrong)
    return line if found is None else line[:found.start()] + right + line[found.end():]


def apply(segments: list[Segment], swaps: list[Swap],
          context: Context | None = None) -> tuple[list[Segment], dict[str, str]]:
    """The captions with the good swaps made, and the pairs that were made."""
    allowed = names_allowed(known_words(), context)
    out = [s.model_copy(deep=True) for s in segments]
    pairs: dict[str, str] = {}
    for swap in swaps[:MOST_SWAPS]:
        if not usable(swap, out, allowed):
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


def listed(pairs: dict[str, str]) -> dict[str, str]:
    """The swaps to a word on the list: the only ones worth learning for next time."""
    known = {w.lower() for w in known_words()}
    return {wrong: right for wrong, right in pairs.items() if right.lower() in known}


def polish(transcript: Transcript, context: Context | None = None) -> tuple[Transcript, dict[str, str]]:
    """Read the captions back in their sentence. Never a reason for anything to fail."""
    from . import discovery

    if not ON or not transcript.segments:
        return transcript, {}
    known = known_words()
    try:
        discovery.check_provider()
        answer = discovery.ask(question(transcript.segments, known, context), SYSTEM, LlmSwaps, EFFORT)
    except Exception as exc:  # noqa: BLE001  the clip is written out and usable as it is
        print(f"[woorden] nalezen overgeslagen: {exc}")
        return transcript, {}
    segments, pairs = apply(transcript.segments, getattr(answer, "swaps", []) or [], context)
    if not pairs:
        return transcript, {}
    learned = remember(listed(pairs))
    if learned:
        print(f"[woorden] geleerd: {', '.join(f'{k} → {v}' for k, v in learned.items())}")
    return Transcript(language=transcript.language, segments=segments), pairs


def note(work_dir: Path, before: Transcript, pairs: dict[str, str]) -> None:
    """Keep what the clip said before it was read back, beside it and out of sight."""
    if not pairs:
        return
    try:
        work_dir.mkdir(parents=True, exist_ok=True)
        write_atomic(work_dir / "nagelezen.json", json.dumps(
            {"swaps": pairs, "before": [s.text for s in before.segments]}, indent=2, ensure_ascii=False))
    except OSError:
        pass  # a note for the curious; the clip does not depend on it
