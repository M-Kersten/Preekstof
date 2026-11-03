"""The hook: a few seconds from later in the clip, played before it starts.

A clip opens where the thought opens, because that is what makes it possible to follow.
Somebody scrolling past has not decided to follow anything yet. What stops them is the
preacher saying the point, so that is played first, a short white flash marks the jump,
and then the clip starts from the top. One sentence when one says it, two or three when the
point only stands together; ten seconds at most, so it is clearly a preview and not the
clip starting twice.

Which sentence carries the point is a question about meaning, so Claude reads the clip's
subtitles and proposes a few, best first. Where it sits is not left to the model: the
quote has to be found word for word in what whisper heard, and its time comes from
whisper's own word timings. Then the same checks as everywhere else in this app decide
whether it may be used:

    the words are really there, in that order,
    it lasts between SHORTEST and LONGEST seconds,
    it comes from later in the clip than EARLIEST, so the clip does not repeat itself at once,
    and it does not open on a word that leans on what came before ("dat", "dus", "hij").

The first proposal that passes becomes the hook, and every one that passes is kept beside
it (Project.hookOptions), so somebody who does not like the first can play the others and
switch with one click instead of asking again. Asking again sends what was already offered
along, so the next answer is a different sentence and not the same one in other words.
None passing means no hook, which is a clip as it always was. In the editor the words of
the clip can also be clicked, first and last, to make a hook of any sentence; a hook chosen
by hand is never replaced by a new suggestion.
"""

import re

from pydantic import BaseModel

from . import settings
from .models import Hook, Segment, Spoken, Transcript
from .subtitles import word_times

ON = settings.text("HOOK_CLIPS", "1").strip().lower() not in ("0", "false", "nee", "off")
EFFORT = settings.choice("HOOK_EFFORT", ("low", "medium", "high", "xhigh", "max"), "low")

SHORTEST = 1.5  # seconds: less is a word, not a sentence
LONGEST = 10.0  # three sentences at most; more is the clip starting twice
LONGEST_BY_HAND = 15.0  # somebody choosing for themselves gets some more room
EARLIEST = 6.0  # the hook comes from after this point in the clip
SHORTEST_CLIP = 15.0  # a clip shorter than this has no room for a preview of itself
BEFORE = 0.12  # room in front of the first word, so its first sound is not cut
AFTER = 0.30  # and behind the last, where the flash to white happens
GAP = 0.03  # never into the word next to it

SYSTEM = (
    "Je krijgt de ondertitels van een fragment uit een Nederlandse preek, met per regel de "
    "tijd in seconden. Het fragment gaat online als korte video (Instagram Reel, YouTube "
    "Short).\n\n"
    "Kies een hook: het stuk uit dit fragment waarin de predikant de kern van de boodschap "
    "zegt. Dat wordt vooraan afgespeeld, en daarna begint het fragment bij het begin. Iemand "
    "die voorbij scrolt moet aan die paar seconden genoeg hebben om te willen weten hoe het "
    "verder gaat.\n\n"
    "Een goede hook:\n"
    "- zegt de kern, de belofte of de vraag waar het fragment om draait\n"
    "- is te begrijpen zonder wat ervoor kwam: geen \"dat\", \"die\", \"hij\", \"dus\", "
    "\"daarom\" of \"want\" als eerste woord\n"
    "- is één zin als één zin de kern zegt, en twee of drie zinnen achter elkaar als de kern "
    "pas samen staat; korter is beter zolang het af is\n"
    "- duurt samen twee tot tien seconden\n"
    "- komt niet uit de eerste zes seconden van het fragment, want die hoort de kijker meteen "
    "daarna toch\n\n"
    "Regels, en hier mag je niet van afwijken:\n"
    "- neem de woorden letterlijk over zoals ze in de ondertitels staan, aaneengesloten, "
    "zonder iets weg te laten, toe te voegen of te verbeteren\n"
    "- een hook mag over meer regels lopen als de zinnen dat doen\n"
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


def question(transcript: Transcript, title: str = "", offered: list[str] | None = None) -> str:
    lines = "\n".join(f"{s.start:.1f}-{s.end:.1f}: {s.text.strip()}"
                      for s in sorted(transcript.segments, key=lambda s: s.start) if s.text.strip())
    about = f"Titel van het fragment: {title.strip()}\n\n" if title and title.strip() else ""
    asked = f"{about}De ondertitels:\n{lines}"
    if offered:
        # Without this the next answer is the same sentence, which is the one that was not liked.
        before = "\n".join(f"- {text}" for text in offered)
        asked += (f"\n\nDeze zijn al voorgesteld en vielen niet in de smaak. Kies andere zinnen, "
                  f"uit een ander deel van het fragment:\n{before}")
    return asked


def overlaps(a: Hook, b: Hook) -> bool:
    """Two hooks that are mostly the same seconds are the same hook."""
    shared = min(a.end, b.end) - max(a.start, b.start)
    return shared > 0.5 * min(a.end - a.start, b.end - b.start)


def choose(options: list[LlmHook], transcript: Transcript, length: float,
           besides: list[Hook] | None = None) -> list[Hook]:
    """Every proposal that passes every check, best first, and none twice."""
    words = said(transcript)
    taken: list[Hook] = []
    for option in options:
        hook, why = place(option.quote, words, length)
        if hook is None:
            print(f"[hook] “{option.quote[:60]}” valt af: {why}")
        elif not any(overlaps(hook, other) for other in taken + (besides or [])):
            taken.append(hook)
    return taken


def suggest(transcript: Transcript, length: float, title: str = "",
            besides: list[Hook] | None = None) -> list[Hook]:
    """Hooks for this clip, best first; empty when there is none. Never a reason to fail.

    `besides` are hooks offered before: named in the question as not wanted again, and left
    out of what comes back.
    """
    from . import discovery

    if not ON or length < SHORTEST_CLIP or not any(s.text.strip() for s in transcript.segments):
        return []
    try:
        discovery.check_provider()
        asked = question(transcript, title, [h.text for h in besides or [] if h.text])
        answer = discovery.ask(asked, SYSTEM, LlmHooks, EFFORT)
    except Exception as exc:  # noqa: BLE001  a clip without a hook is a clip as it always was
        print(f"[hook] overgeslagen: {exc}")
        return []
    return choose(getattr(answer, "hooks", []) or [], transcript, length, besides)


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
    if end - start > LONGEST_BY_HAND:
        raise ValueError(f"Een hook mag hoogstens {LONGEST_BY_HAND:.0f} seconden duren.")
    return hook.model_copy(update={"start": round(start, 2), "end": round(end, 2), "by": "hand"})
