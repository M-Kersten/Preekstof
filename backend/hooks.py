"""The hook: a few seconds from later in the clip, played before it starts.

A clip opens where the thought opens, because that is what makes it possible to follow.
Somebody scrolling past has not decided to follow anything yet. What stops them is the
preacher saying the point, so that sentence is played first, a short white flash marks
the jump, and then the clip starts from the top. Around three seconds: long enough for a
whole sentence, short enough that it is clearly a preview and not the clip.

Which sentence carries the point is a question about meaning, so Claude reads the clip's
subtitles and proposes a few, best first. Where it sits is not left to the model: the
quote has to be found word for word in what whisper heard, and its time comes from
whisper's own word timings. Then the same checks as everywhere else in this app decide
whether it may be used:

    the words are really there, in that order,
    it lasts between SHORTEST and LONGEST seconds,
    it comes from later in the clip than EARLIEST, so the clip does not repeat itself at once,
    and it does not open on a word that leans on what came before ("dat", "dus", "hij").

The first proposal that passes is taken. None passing means no hook, which is a clip as
it always was. The editor shows the choice, plays it, and lets somebody take another line
or move the edges by hand; a hook chosen by hand is never replaced by a new suggestion.
"""

import re

from pydantic import BaseModel

from . import settings
from .models import Hook, Segment, Spoken, Transcript
from .subtitles import word_times

ON = settings.text("HOOK_CLIPS", "1").strip().lower() not in ("0", "false", "nee", "off")
EFFORT = settings.choice("HOOK_EFFORT", ("low", "medium", "high", "xhigh", "max"), "low")

SHORTEST = 1.5  # seconds: less is a word, not a sentence
LONGEST = 5.0  # more is the clip starting twice
AIM = 3.0  # what the question asks for
EARLIEST = 6.0  # the hook comes from after this point in the clip
SHORTEST_CLIP = 15.0  # a clip shorter than this has no room for a preview of itself
BEFORE = 0.12  # room in front of the first word, so its first sound is not cut
AFTER = 0.30  # and behind the last, where the flash to white happens
GAP = 0.03  # never into the word next to it

SYSTEM = (
    "Je krijgt de ondertitels van een fragment uit een Nederlandse preek, met per regel de "
    "tijd in seconden. Het fragment gaat online als korte video (Instagram Reel, YouTube "
    "Short).\n\n"
    "Kies een hook: één zin of zinsdeel uit dit fragment waarin de predikant de kern van de "
    "boodschap zegt. Die wordt vooraan afgespeeld, ongeveer drie seconden, en daarna begint "
    "het fragment bij het begin. Iemand die voorbij scrolt moet aan die paar seconden genoeg "
    "hebben om te willen weten hoe het verder gaat.\n\n"
    "Een goede hook:\n"
    "- zegt de kern, de belofte of de vraag waar het fragment om draait\n"
    "- is te begrijpen zonder wat ervoor kwam: geen \"dat\", \"die\", \"hij\", \"dus\", "
    "\"daarom\" of \"want\" als eerste woord\n"
    "- duurt twee tot vier seconden; meestal zes tot twaalf woorden\n"
    "- komt niet uit de eerste zes seconden van het fragment, want die hoort de kijker meteen "
    "daarna toch\n\n"
    "Regels, en hier mag je niet van afwijken:\n"
    "- neem de woorden letterlijk over zoals ze in de ondertitels staan, aaneengesloten, "
    "zonder iets weg te laten, toe te voegen of te verbeteren\n"
    "- een hook mag over twee regels lopen als de zin dat doet\n"
    "- geef tot drie opties, de beste eerst, en bij elk in een zin waarom\n\n"
    "Staat er niets in dat zonder de rest werkt, geef dan een lege lijst terug."
)


class LlmHook(BaseModel):
    quote: str  # the words, exactly as they stand in the subtitles
    why: str


class LlmHooks(BaseModel):
    hooks: list[LlmHook]


# --- where the words are ---------------------------------------------------------


def said(transcript: Transcript) -> list[Spoken]:
    """Every word of the clip with when it was said, in order."""
    words: list[Spoken] = []
    for segment in sorted(transcript.segments, key=lambda s: s.start):
        words += word_times(segment)
    return words


TOKEN = re.compile(r"[^\w]+", re.UNICODE)


def token(word: str) -> str:
    """A word as it is compared: no capitals, no punctuation."""
    return TOKEN.sub("", word.lower())


def find(quote: str, words: list[Spoken]) -> list[tuple[int, int]]:
    """Every place where the quote stands in the clip, as (first, last) word indexes."""
    wanted = [t for t in (token(w) for w in quote.split()) if t]
    if not wanted:
        return []
    have = [token(w.word) for w in words]
    found = []
    for i in range(len(have) - len(wanted) + 1):
        if have[i:i + len(wanted)] == wanted:
            found.append((i, i + len(wanted) - 1))
    return found


def edges(words: list[Spoken], first: int, last: int, length: float) -> tuple[float, float]:
    """Where to cut around words first..last: a little room, never into a neighbour."""
    start = words[first].start - BEFORE
    if first > 0:
        start = max(start, words[first - 1].end + GAP)
    end = words[last].end + AFTER
    if last + 1 < len(words):
        end = min(end, words[last + 1].start - GAP)
    start = max(0.0, min(start, words[first].start))
    end = min(length, max(end, words[last].end))
    return round(start, 2), round(end, 2)


def refused(quote: str, start: float, end: float, length: float) -> str | None:
    """Why this hook may not be used, or None when it may."""
    from .discovery import cold_open

    if end - start < SHORTEST:
        return f"te kort ({end - start:.1f} s)"
    if end - start > LONGEST:
        return f"te lang ({end - start:.1f} s)"
    if start < EARLIEST:
        return "komt uit het begin van het fragment"
    if end > length:
        return "loopt over het einde heen"
    if cold_open(quote):
        return "begint met een verwijzing naar wat ervoor kwam"
    return None


def place(quote: str, words: list[Spoken], length: float) -> tuple[Hook | None, str]:
    """The quote as a hook, where it stands in the clip; or None and why not."""
    spots = find(quote, words)
    if not spots:
        return None, "staat niet letterlijk in de ondertitels"
    why = ""
    for first, last in spots:
        start, end = edges(words, first, last, length)
        text = " ".join(w.word for w in words[first:last + 1])
        why = refused(text, start, end, length) or ""
        if not why:
            return Hook(start=start, end=end, text=text, by="claude"), ""
    return None, why


# --- asking ----------------------------------------------------------------------


def question(transcript: Transcript, title: str = "") -> str:
    lines = "\n".join(f"{s.start:.1f}-{s.end:.1f}: {s.text.strip()}"
                      for s in sorted(transcript.segments, key=lambda s: s.start) if s.text.strip())
    about = f"Titel van het fragment: {title.strip()}\n\n" if title and title.strip() else ""
    return f"{about}De ondertitels:\n{lines}"


def choose(options: list[LlmHook], transcript: Transcript, length: float) -> Hook | None:
    """The first proposal that passes every check."""
    words = said(transcript)
    for option in options:
        hook, why = place(option.quote, words, length)
        if hook is not None:
            return hook
        print(f"[hook] “{option.quote[:60]}” valt af: {why}")
    return None


def suggest(transcript: Transcript, length: float, title: str = "") -> Hook | None:
    """A hook for this clip, or None. Never a reason for anything to fail."""
    from . import discovery

    if not ON or length < SHORTEST_CLIP or not any(s.text.strip() for s in transcript.segments):
        return None
    try:
        discovery.check_provider()
        answer = discovery.ask(question(transcript, title), SYSTEM, LlmHooks, EFFORT)
    except Exception as exc:  # noqa: BLE001  a clip without a hook is a clip as it always was
        print(f"[hook] overgeslagen: {exc}")
        return None
    return choose(getattr(answer, "hooks", []) or [], transcript, length)


# --- what it shows ---------------------------------------------------------------


def captions(transcript: Transcript, hook: Hook) -> Transcript:
    """The subtitles for the hook alone: the words said inside it, counted from its start.

    Only the words, and not the whole caption they belong to: a hook that is the second
    half of a long sentence should not show its first half on screen.
    """
    length = hook.end - hook.start
    out: list[Segment] = []
    for segment in sorted(transcript.segments, key=lambda s: s.start):
        inside = [w for w in word_times(segment) if hook.start <= (w.start + w.end) / 2 <= hook.end]
        if not inside:
            continue
        moved = [Spoken(start=round(max(0.0, w.start - hook.start), 3),
                        end=round(min(length, w.end - hook.start), 3), word=w.word) for w in inside]
        out.append(Segment(start=round(max(0.0, min(segment.start - hook.start, moved[0].start)), 3),
                           end=round(min(length, max(moved[-1].end, min(segment.end, hook.end) - hook.start)), 3),
                           text=" ".join(w.word for w in inside), words=moved))
    return Transcript(language=transcript.language, segments=[s for s in out if s.end > s.start])


def by_hand(hook: Hook, length: float) -> Hook:
    """A hook somebody set: kept inside the clip and within reason, and marked as theirs."""
    start = max(0.0, min(hook.start, length))
    end = max(start, min(hook.end, length))
    if end - start < 0.5:
        raise ValueError("Een hook moet minstens een halve seconde duren.")
    if end - start > LONGEST * 2:
        raise ValueError(f"Een hook mag hoogstens {LONGEST * 2:.0f} seconden duren.")
    return hook.model_copy(update={"start": round(start, 2), "end": round(end, 2), "by": "hand"})
