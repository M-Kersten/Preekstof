"""AI clip discovery: transcript passages -> LLM analysis -> ranked, deduplicated ClipCandidates.

This layer only knows what the service contains and where good moments are.
It never renders video; selected candidates go through backend/clips.py into
the existing clip-production pipeline.
"""

import hashlib
import json
import os
import random
import re
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from pydantic import BaseModel

from .jobs import Cancelled
from . import settings, structure
from .models import ClipCandidate, Segment, TimeRange, Transcript, write_atomic
from .structure import Block

LLM_PROVIDER = settings.choice("LLM_PROVIDER", ("anthropic", "ollama"), "anthropic")
LLM_MODEL = settings.text("LLM_MODEL") or None  # defaults per provider below
# How long the model thinks before it answers. With one call left this is most of the wait.
# The API takes these five words and nothing else, so a sixth never leaves the house.
EFFORT_LEVELS = ("low", "medium", "high", "xhigh", "max")
LLM_EFFORT = settings.choice("LLM_EFFORT", EFFORT_LEVELS, "medium")
LLM_CONCURRENCY = settings.whole("LLM_CONCURRENCY", 3, least=1)
LLM_ATTEMPTS = settings.whole("LLM_ATTEMPTS", 3, least=1)  # tries per passage before giving up on it
LLM_TIMEOUT = settings.number("LLM_TIMEOUT", 300, least=1)  # a sermon takes longer to read than four minutes
LLM_MAX_TOKENS = settings.whole("LLM_MAX_TOKENS", 16000, least=1000)  # thinking included; an answer is a few hundred
OLLAMA_URL = settings.text("OLLAMA_URL", "http://localhost:11434")

# How much of the service goes into one call. This used to be four minutes, from a time
# when a model could not hold more, and a ninety-minute service then became sixteen calls
# plus a second round to compare their answers: three waits in a row for a volunteer who
# wanted a clip in a hurry. A whole sermon is around twenty thousand tokens and fits in one
# call with room to spare, so that is what gets sent.
PASSAGE_MINUTES = settings.number("LLM_PASSAGE_MINUTES", 40, least=1)
PASSAGE_SECONDS = PASSAGE_MINUTES * 60
PASSAGE_OVERLAP = 90.0  # only comes into play for a sermon too long for one passage
PASSAGE_LEAD = 60.0  # transcript before the passage, given as context but never proposed from
MIN_CLIP = 25.0  # hard limits: shorter/longer proposals are dropped
MAX_CLIP = 180.0
PREFERRED = (45.0, 90.0)
COLD_PENALTY = 0.12  # a clip that opens on a back-reference drops this far
SNAP_TOLERANCE = 4.0  # seconds: snap proposed boundaries to the nearest sentence boundary
OVERLAP_DUPLICATE = 0.5  # fraction of the shorter candidate that overlaps -> same moment

ProgressCallback = Callable[[float, str], None]


# --- LLM output schema --------------------------------------------------------


class LlmCandidate(BaseModel):
    start: float
    end: float
    title: str
    summary: str
    reason: str
    confidence: float


class LlmAnalysis(BaseModel):
    candidates: list[LlmCandidate]


class Verdict(BaseModel):
    """The second pass's judgement on one proposal."""

    id: str
    keep: bool
    rank: int  # 1 is the best of the service; 0 for a moment that is not shortlisted
    verdict: str  # one line: why it was picked, or why another moment beat it


class LlmShortlist(BaseModel):
    verdicts: list[Verdict]


SYSTEM_PROMPT = """Je bent redacteur voor de social-media kanalen van een kerk. Je krijgt het transcript \
van een Nederlandse kerkdienst, met tijdcodes per zin. Zoek de momenten die als losse korte video \
(Instagram Reel, YouTube Short) werken voor iemand die de dienst niet gehoord heeft.

Zo iemand kent het verhaal niet, scrolt voorbij, en heeft twee seconden om te snappen waar dit over gaat. \
Een fragment dat begint met "en dus moeten we dat doen" zegt die kijker niets, hoe mooi de zin ook is. Kies \
liever een moment dat zijn eigen aanloop meeneemt dan de losse rake zin.

Een moment is bruikbaar als de eerste zin het onderwerp zelf noemt, de gedachte daarna binnen het fragment \
af komt, en iemand die de kerk niet kent er iets aan heeft.

Laat liggen: fragmenten die openen op een terugverwijzing ("dat", "die", "hij", "daarom", "dus", "zoals ik \
net zei"), losse rake zinnen zonder de opbouw eromheen, onafgemaakte gedachten, herhaling, mededelingen, \
collecte, liedaankondigingen, gebed, en een verhaal waarvan de clou buiten het fragment valt.

Grenzen:
- start en end zijn tijden in seconden en vallen samen met het begin en het einde van zinnen uit het transcript
- richt op 45-90 seconden; 30-120 mag als de gedachte dat vraagt. Korter dan 30 seconden is bijna altijd te \
kort om iets uit te leggen
- kandidaten mogen elkaar niet overlappen, en verdeel ze over de preek in plaats van ze op een kluitje te kiezen
- uit de tekst onder "Wat hieraan voorafging" kies je geen begin- of eindtijd

Geef per kandidaat: start, end, een korte pakkende Nederlandse titel (max 60 tekens, geen aanhalingstekens), \
een samenvatting van een zin, en bij reason: wat een kijker die niets weet in de eerste vijf seconden \
begrijpt, en waarom de gedachte binnen het fragment af is. Confidence tussen 0 en 1, onderling vergelijkbaar: \
0.9 gaat alleen naar wat er echt uitspringt. Optimaliseer voor heldere, zelfstandige preekmomenten, niet \
voor "viraal"."""


SHORTLIST_PROMPT = """Je bent eindredacteur voor de social-media kanalen van een kerk. Een collega \
heeft de hele dienst doorgelezen in losse stukken en per stuk voorstellen gedaan. Die collega zag steeds \
maar een paar minuten tegelijk en kon de voorstellen dus niet met elkaar vergelijken. Dat is jouw werk.

Je krijgt de opbouw van de dienst en alle voorgestelde momenten met hun tijd, titel, samenvatting, reden, \
de zin waarmee het fragment opent en een stuk van het transcript. Kies welke momenten deze week \
daadwerkelijk gepost worden.

Weeg in deze volgorde:
1. de openingszin. Snapt iemand die niets van deze dienst weet binnen vijf seconden waar dit over gaat? \
Opent het fragment op "dat", "die", "hij", "daarom", "dus" of iets anders dat terugverwijst, dan valt het af, \
hoe sterk de rest ook is
2. is de gedachte binnen het fragment af, of loopt de kijker vast omdat het antwoord er niet in staat
3. heeft iemand die de kerk niet kent er iets aan
4. zegt het iets anders dan de andere gekozen momenten; twee keer dezelfde gedachte is een keer te veel
5. komt het uit de kern van de preek, niet uit een aankondiging of een terzijde

Regels:
- kies er 3 tot 6. Liever drie momenten die een vreemde begrijpt dan acht die alleen kloppen voor wie erbij was
- een fragment onder de 30 seconden kies je alleen als het echt in zichzelf af is
- rank 1 is het sterkste moment van de dienst, daarna aflopend
- geef ieder voorstel een verdict van een zin, ook de afvallers: waarom het het niet werd
- verzin geen momenten en verander geen tijden; je kiest alleen uit wat je krijgt"""


# --- windows -----------------------------------------------------------------


@dataclass
class Window:
    index: int
    start: float
    end: float
    segments: list[Segment]
    part: str = "preek"  # which part of the service this window falls in
    # The minutes before the window. The model reads them so it knows what the preacher is
    # talking about, but it may not propose a clip out of them: snapping and the boundary
    # checks only know about `segments`.
    lead: list[Segment] = field(default_factory=list)


def build_windows(segments: list[Segment], length: float = PASSAGE_SECONDS, overlap: float = PASSAGE_OVERLAP,
                  lead: float = PASSAGE_LEAD) -> list[Window]:
    """Split timestamped segments into overlapping analysis windows (not clip boundaries)."""
    segments = [s for s in sorted(segments, key=lambda s: s.start) if s.text.strip()]
    windows: list[Window] = []
    i = 0
    while i < len(segments):
        t0 = segments[i].start
        j = i
        while j < len(segments) and (segments[j].start < t0 + length or j == i):
            j += 1
        chunk = segments[i:j]
        run_up = [s for s in segments[:i] if s.end > t0 - lead]
        windows.append(Window(len(windows), chunk[0].start, chunk[-1].end, chunk, lead=run_up))
        if j >= len(segments):
            break
        # Next window starts `overlap` seconds before this one ends, but always makes progress.
        # It steps back onto the last sentence that begins before that point rather than
        # forward onto the first one after it: a transcript with long gaps would otherwise
        # hand the next window a seam of a second or two, and a moment sitting on that seam
        # would be cut short in both windows and then dropped for being too short.
        seam = chunk[-1].end - overlap
        next_i = i + 1
        for k in range(i + 1, j):
            if segments[k].start > seam:
                break
            next_i = k
        i = max(next_i, i + 1)
    return windows


def say(segments: list[Segment]) -> str:
    return "\n".join(f"[{s.start:.1f}-{s.end:.1f}] {s.text.strip()}" for s in segments)


def format_window(window: Window) -> str:
    """The window itself, preceded by the run-up that explains what it is about.

    A moment reads as self-contained or not depending on what came before it, and a model
    that only sees the window cannot tell the difference. So it gets the minutes before as
    well, marked as off-limits for the answer.
    """
    if not window.lead:
        return say(window.segments)
    return ("Wat hieraan voorafging (alleen om te begrijpen waar het over gaat, kies hier niets uit):\n"
            f"{say(window.lead)}\n\n"
            f"Kies je momenten uit dit stuk, van {window.start:.1f}s tot {window.end:.1f}s:\n"
            f"{say(window.segments)}")


def worth_sending(shape: list[Block], segments: list[Segment]) -> tuple[list[Segment], float]:
    """The sentences that go to the model, and the seconds of speech that were dropped.

    Roughly half a Sunday morning is welcome, songs, notices and blessing. Those cost money
    and put moments in the list that nobody would post, so they are dropped here rather
    than argued away in the prompt. The filter runs per sentence, so what is left packs
    tightly and forty minutes of preaching stays forty minutes instead of becoming an hour
    and a half with the singing still in it.
    """
    keeping: list[Segment] = []
    left_out = 0.0
    for segment in sorted(segments, key=lambda s: s.start):
        if not segment.text.strip():
            continue
        if structure.worth_analysing(shape, segment.start, segment.end):
            keeping.append(segment)
        else:
            left_out += max(0.0, segment.end - segment.start)
    return keeping, left_out


def sermon_windows(segments: list[Segment],
                   duration: float | None = None) -> tuple[list[Window], list[Block], float]:
    """The passages worth sending, each told which part of the service it sits in.

    What survives the filter is packed into as few passages as it fits in. A model that
    reads the whole sermon at once can tell the best moment of the service from the best
    moment of a dull three minutes, which no single four-minute window ever could, and one
    call is one wait instead of sixteen. Returns (passages, the shape of the service, the
    seconds of service that were left out).
    """
    shape = structure.blocks(segments, duration)
    keeping, _spoken = worth_sending(shape, segments)
    left_out = sum(b.seconds for b in shape if b.part in structure.SKIP)
    passages = build_windows(keeping)
    for passage in passages:
        passage.part = structure.PART_LABEL[structure.part_at(shape, (passage.start + passage.end) / 2)]
    return passages, shape, left_out


# --- LLM call ----------------------------------------------------------------


class Retryable(RuntimeError):
    """A failure that is worth trying again: rate limit, server error, network hiccup."""


def wanted_from(window: Window, alone: bool) -> int:
    """How many moments to ask for out of one passage.

    When the whole sermon arrives in one call the model is already choosing what gets
    posted, so it is asked for the shortlist itself and the round that compares proposals
    afterwards has nothing left to do. A sermon long enough to need splitting is proposed
    from more generously, because that round still follows and can throw away the excess.
    """
    if alone:
        return SHORTLIST_RANGE[1]
    minutes = max(1.0, (window.end - window.start) / 60.0)
    return max(2, min(10, round(minutes / 5.0)))


def window_request(window: Window, about: str = "", wanted: int = 2, alone: bool = False) -> str:
    """Everything the model is told about one passage, in the order it reads it."""
    if alone:
        low, high = SHORTLIST_RANGE[0], max(SHORTLIST_RANGE[0], wanted)
        job = (f"Dit is de hele preek. Kies de {low} tot {high} momenten die deze week daadwerkelijk gepost "
               f"worden, het sterkste eerst. Liever {low} momenten die een vreemde begrijpt dan acht die "
               f"alleen kloppen voor wie erbij was.")
        where = f"De preek, van {window.start:.0f}s tot {window.end:.0f}s in de dienst."
    else:
        job = (f"Geef hooguit {wanted} kandidaten uit dit stuk, en alleen wat je echt zou posten; een lege "
               f"lijst is een prima antwoord. Een collega vergelijkt straks de stukken met elkaar.")
        where = (f"Fragment {window.index + 1}, van {window.start:.0f}s tot {window.end:.0f}s in de dienst, "
                 f"ongeveer {int(window.start // 60)} minuten na het begin.")
    setting = f"{where} Dit deel van de dienst is: {window.part}.{(' ' + about) if about else ''}"
    return f"{setting}\n\n{job}\n\n{format_window(window)}"


def window_file(cache_dir: Path, window: Window, request: str) -> Path:
    """Where one passage's answer is kept.

    The name carries everything the model was told, so a re-transcription, a different
    model, an edited prompt, a different passage length or a church that filled in what
    the sermon is about all miss the cache instead of handing back something that no
    longer matches.
    """
    recipe = f"{request}\n{LLM_PROVIDER}\n{LLM_MODEL}\n{SYSTEM_PROMPT}"
    digest = hashlib.sha1(recipe.encode("utf-8")).hexdigest()[:16]
    return cache_dir / f"{window.index:03d}-{digest}.json"


def cached_window(cache_dir: Path | None, window: Window, request: str) -> list[LlmCandidate] | None:
    if cache_dir is None:
        return None
    path = window_file(cache_dir, window, request)
    if not path.is_file():
        return None
    try:
        return [LlmCandidate(**c) for c in json.loads(path.read_text(encoding="utf-8"))]
    except Exception:  # noqa: BLE001  a damaged answer is simply asked again
        return None


def remember_window(cache_dir: Path | None, window: Window, found: list[LlmCandidate], request: str) -> None:
    if cache_dir is None:
        return
    cache_dir.mkdir(parents=True, exist_ok=True)
    write_atomic(window_file(cache_dir, window, request), json.dumps([c.model_dump() for c in found]))


def analyze_window(window: Window, about: str = "", wanted: int = 2, alone: bool = False) -> list[LlmCandidate]:
    return ask(window_request(window, about, wanted, alone), SYSTEM_PROMPT, LlmAnalysis).candidates


def ask(user: str, system: str, schema):
    """One call to the model, retried on the failures that are worth retrying."""
    last: Exception | None = None
    for attempt in range(LLM_ATTEMPTS):
        try:
            return _ollama(user, system, schema) if LLM_PROVIDER == "ollama" else _anthropic(user, system, schema)
        except Retryable as exc:
            last = exc
            if attempt < LLM_ATTEMPTS - 1:
                # Wait a bit longer every time, with a little spread so parallel windows do not sync up.
                time.sleep((2 ** attempt) * 3 + random.uniform(0, 1.5))
        except Exception:  # noqa: BLE001  a bad answer for one window should not stop the rest
            raise
    raise last if last else RuntimeError("Onbekende fout bij het analyseren")


NO_KEY_MESSAGE = ("Er is geen Claude API-sleutel ingesteld. Zet ANTHROPIC_API_KEY=... in config.env en start de app "
                  "opnieuw, of kies LLM_PROVIDER=ollama voor een lokaal model.")


def check_provider() -> None:
    """Fail early with a readable message instead of after the first window."""
    if LLM_PROVIDER == "ollama":
        return
    try:
        import anthropic  # noqa: F401
    except ImportError as exc:
        raise RuntimeError("Het onderdeel 'anthropic' ontbreekt. Sluit de app en start opnieuw met start.bat of "
                           "start.command; de ontbrekende onderdelen worden dan geïnstalleerd.") from exc
    if not (os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN")):
        raise RuntimeError(NO_KEY_MESSAGE)


def _anthropic(user: str, system: str = SYSTEM_PROMPT, schema=LlmAnalysis):
    import anthropic

    client = anthropic.Anthropic(timeout=LLM_TIMEOUT, max_retries=0)  # retries are handled per window
    try:
        response = _anthropic_request(client, user, system, schema)
    except anthropic.AuthenticationError as exc:
        raise RuntimeError("De Claude API-sleutel wordt niet geaccepteerd. Controleer ANTHROPIC_API_KEY in config.env.") from exc
    except anthropic.RateLimitError as exc:
        raise Retryable("De Claude API is even vol (limiet bereikt).") from exc
    except anthropic.APIStatusError as exc:
        if exc.status_code >= 500:
            raise Retryable(f"De Claude API gaf een serverfout ({exc.status_code}).") from exc
        # A 400 is nearly always a setting the API does not recognise, and repeating the
        # request will not change that. Say where to go and look.
        hint = " Kijk de instellingen in config.env na." if exc.status_code == 400 else ""
        raise RuntimeError(f"De Claude API gaf een fout ({exc.status_code}): {exc.message}{hint}") from exc
    except anthropic.APIConnectionError as exc:
        raise Retryable("Geen verbinding met de Claude API.") from exc
    if response.stop_reason == "max_tokens":
        raise RuntimeError("Het antwoord van Claude werd afgekapt voordat het af was. Zet LLM_EFFORT op "
                           "medium of low in config.env, of verhoog LLM_MAX_TOKENS.")
    if response.stop_reason == "refusal" or response.parsed_output is None:
        return schema()
    return response.parsed_output


def _anthropic_request(client, user: str, system: str, schema):
    return client.messages.parse(
        model=LLM_MODEL or "claude-opus-5",
        max_tokens=LLM_MAX_TOKENS,
        system=system,
        output_config={"effort": LLM_EFFORT},
        messages=[{"role": "user", "content": user}],
        output_format=schema,
    )


def _ollama(user: str, system: str = SYSTEM_PROMPT, schema=LlmAnalysis):
    body = json.dumps({
        "model": LLM_MODEL or "llama3.1",
        "stream": False,
        "format": schema.model_json_schema(),
        "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}],
    }).encode("utf-8")
    req = urllib.request.Request(f"{OLLAMA_URL}/api/chat", data=body, headers={"content-type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=LLM_TIMEOUT * 4) as res:
            data = json.loads(res.read().decode("utf-8"))
    except OSError as exc:
        raise Retryable(f"Ollama antwoordde niet op {OLLAMA_URL}.") from exc
    return schema.model_validate_json(data["message"]["content"])


# --- post-processing -----------------------------------------------------------


def snap(candidate: LlmCandidate, window: Window) -> tuple[float, float]:
    """Move boundaries onto the nearest sentence start/end so clips begin and end naturally."""
    starts = [s.start for s in window.segments]
    ends = [s.end for s in window.segments]
    start = min(starts, key=lambda t: abs(t - candidate.start))
    end = min(ends, key=lambda t: abs(t - candidate.end))
    if abs(start - candidate.start) > SNAP_TOLERANCE:
        start = candidate.start
    if abs(end - candidate.end) > SNAP_TOLERANCE:
        end = candidate.end
    return round(max(window.start, start), 2), round(min(window.end, end), 2)


# Words a sentence opens with when it is finishing something the listener already heard.
# Someone who scrolled past has heard none of it, so a clip starting here begins in the
# middle of a story. "Het" and "Wat" are left out on purpose: they open plenty of sentences
# that stand perfectly well on their own.
COLD_WORDS = {
    "dat", "dit", "die", "deze", "hij", "zij", "ze", "hem", "haar", "hen", "hun",
    "daarom", "daardoor", "daarin", "daarover", "daarmee", "daaruit", "daarvan", "daarnaast",
    "hierdoor", "hiermee", "hierin", "hiervan", "vandaar", "dus", "want", "immers",
    "namelijk", "bovendien", "trouwens", "toch", "ook", "zo", "dan", "vervolgens", "daarna",
}
COLD_PHRASES = ("zoals ik", "zoals we", "zoals gezegd", "zoals net", "zoals je net",
                "daarnet", "zonet", "net al", "wat ik net", "dat wil zeggen", "met andere woorden")
FIRST_WORD = re.compile(r"[a-zà-ÿ']+")


def cold_open(text: str) -> bool:
    """Does this sentence lean on something the viewer has not heard?"""
    head = text.strip().lower()
    if not head:
        return False
    if any(head.startswith(phrase) for phrase in COLD_PHRASES):
        return True
    match = FIRST_WORD.match(head)
    if not match:
        return False
    if match.group() == "en":  # "En toen", "En dat" lean back; "En God zei" does not
        rest = FIRST_WORD.search(head[match.end():])
        return bool(rest and rest.group() in COLD_WORDS)
    return match.group() in COLD_WORDS


def opening_line(segments: list[Segment], start: float) -> str:
    """The sentence a clip starts on, which is all a scrolling viewer gets to go on."""
    for segment in sorted(segments, key=lambda s: s.start):
        if segment.end > start + 0.05 and segment.text.strip():
            return segment.text.strip()
    return ""


def score(candidate: LlmCandidate, duration: float, opening: str = "") -> float:
    s = max(0.0, min(1.0, candidate.confidence))
    if PREFERRED[0] <= duration <= PREFERRED[1]:
        s += 0.05
    elif duration < 30 or duration > 120:
        s -= 0.15
    if opening and cold_open(opening):
        s -= COLD_PENALTY
    return round(s, 4)


def overlap_fraction(a: ClipCandidate, b: ClipCandidate) -> float:
    inter = min(a.end, b.end) - max(a.start, b.start)
    if inter <= 0:
        return 0.0
    return inter / max(1e-6, min(a.end - a.start, b.end - b.start))


def dedupe_and_rank(raw: list[ClipCandidate]) -> list[ClipCandidate]:
    """Keep one primary candidate per moment; overlapping proposals become alternate boundaries."""
    kept: list[ClipCandidate] = []
    for cand in sorted(raw, key=lambda c: c.score, reverse=True):
        twin = next((k for k in kept if overlap_fraction(k, cand) >= OVERLAP_DUPLICATE), None)
        if twin is None:
            kept.append(cand)
        elif (cand.start, cand.end) != (twin.start, twin.end):
            twin.alternateBoundaries.append(TimeRange(start=cand.start, end=cand.end))
    for n, cand in enumerate(kept, start=1):
        cand.id = f"candidate-{n:02d}"
    return kept


# --- the second pass: choosing between everything that was found -----------------

SHORTLIST_MIN = 4  # below this many proposals there is nothing to choose between
SHORTLIST_RANGE = (3, 6)  # how many moments a service is worth posting
EXCERPT_CHARS = 400  # how much of each moment the editor gets to read


def excerpt(segments: list[Segment], start: float, end: float, limit: int = EXCERPT_CHARS) -> str:
    """What is actually said during a proposed moment, trimmed to something readable."""
    said = " ".join(s.text.strip() for s in segments if s.end > start and s.start < end)
    return said if len(said) <= limit else said[:limit - 1].rsplit(" ", 1)[0] + "…"


def shortlist_request(found: list[ClipCandidate], segments: list[Segment], shape: list[Block],
                      about: str = "") -> str:
    """Everything the editor needs to weigh the moments against each other."""
    lines = [f"De dienst duurt {int((segments[-1].end if segments else 0) // 60)} minuten en is opgebouwd als: "
             f"{structure.summary(shape)}."]
    if about:
        lines.append(about)
    lines += ["", f"Er zijn {len(found)} momenten voorgesteld:", ""]
    for candidate in found:
        opening = opening_line(segments, candidate.start)
        cold = "  let op: dit fragment opent op een terugverwijzing\n" if cold_open(opening) else ""
        lines.append(
            f"[{candidate.id}] {candidate.start:.0f}-{candidate.end:.0f}s "
            f"({candidate.end - candidate.start:.0f} sec, {candidate.part or 'preek'})\n"
            f"  titel: {candidate.title}\n"
            f"  opent met: {opening}\n"
            f"{cold}"
            f"  samenvatting: {candidate.summary}\n"
            f"  reden van de collega: {candidate.reason}\n"
            f"  transcript: {excerpt(segments, candidate.start, candidate.end)}\n"
        )
    return "\n".join(lines)


def shortlist(found: list[ClipCandidate], segments: list[Segment], shape: list[Block],
              about: str = "", alone: bool = False) -> list[ClipCandidate]:
    """Weigh every proposal against all the others and rank the ones worth posting.

    A sermon split over several passages is scored a passage at a time, and that confidence
    is not comparable between them: the best moment of a dull three minutes gets the same
    0.9 as the best moment of the service. This round sees them all at once, so the order
    means something. Everything is kept; the ones that lose are marked, not thrown away.

    A sermon that fitted in one passage skips the round entirely. The model had all of it
    in front of it and was asked for the shortlist there, so a second call would re-rank
    what it already ranked and cost another minute of waiting to do it.
    """
    if alone:
        for candidate in found:
            candidate.shortlisted = True
            candidate.selected = True
        return found
    if len(found) < SHORTLIST_MIN:
        for candidate in found:
            candidate.shortlisted = True
        return found
    answer = ask(shortlist_request(found, segments, shape, about), SHORTLIST_PROMPT, LlmShortlist)
    judged = {v.id: v for v in answer.verdicts}
    if not any(v.keep for v in judged.values()):
        return found  # an answer that keeps nothing is not an answer; leave the order alone
    for candidate in found:
        verdict = judged.get(candidate.id)
        candidate.shortlisted = bool(verdict and verdict.keep)
        candidate.verdict = verdict.verdict.strip() if verdict else ""
        candidate.selected = candidate.shortlisted
    # Rank decides the order among the chosen; the rest keep their own order behind them.
    order = {v.id: v.rank if v.rank > 0 else 999 for v in answer.verdicts}
    found.sort(key=lambda c: (not c.shortlisted, order.get(c.id, 999), -c.score))
    return found


# Rough list price per million tokens (input, output), for the cost estimate shown before analysing.
PRICES = {"claude-opus-5": (5.0, 25.0), "claude-sonnet-5": (2.0, 10.0), "claude-haiku-4-5": (1.0, 5.0)}

# Anthropic publishes those prices in dollars and the church pays in euros, so one rate,
# in one place, adjustable from config.env when it has drifted far enough to matter.
EUR_PER_USD = settings.number("EUR_PER_USD", 0.86, least=0)


def estimate(transcript: Transcript, duration: float | None = None) -> dict:
    """What a run would send and cost, so the interface can say so before spending anything.

    Only the passages that will actually be sent are counted, plus the round that weighs
    the proposals against each other, which a sermon that fits in one passage never pays for.
    """
    passages, _shape, left_out = sermon_windows(transcript.segments, duration)
    alone = len(passages) == 1
    # The run-up is sent along with every passage, so it is paid for too.
    characters = sum(len(w.text) + 16 for passage in passages for w in passage.segments + passage.lead)
    input_tokens = int(characters / 3.5) + len(passages) * 700  # transcript plus the instructions per passage
    proposals = sum(wanted_from(passage, alone) for passage in passages)
    output_tokens = proposals * 220
    if len(passages) > 1:  # the round that reads a summary of every proposal and answers briefly
        input_tokens += proposals * 280 + 700
        output_tokens += proposals * 60
    model = LLM_MODEL or ("llama3.1" if LLM_PROVIDER == "ollama" else "claude-opus-5")
    if LLM_PROVIDER == "ollama":
        cost = 0.0
    else:
        price_in, price_out = PRICES.get(model, PRICES["claude-opus-5"])
        dollars = input_tokens * price_in / 1e6 + output_tokens * price_out / 1e6
        cost = round(dollars * EUR_PER_USD, 2)
    return {"provider": LLM_PROVIDER, "model": model, "windows": len(passages),
            "skippedMinutes": int(left_out // 60), "tokens": input_tokens + output_tokens, "costEur": cost}


class Result(BaseModel):
    """What one analysis run produced, including the windows that would not cooperate."""

    candidates: list[ClipCandidate] = []
    windows: int = 0  # passages actually sent to the model
    skippedMinutes: int = 0  # minutes of service left out because they were not preaching
    failed: int = 0
    shortlisted: int = 0  # how many the second pass judged worth posting
    shape: list[dict] = []  # the parts of the service, for the timeline
    warning: str | None = None


def discover(transcript: Transcript, on_progress: ProgressCallback | None = None,
             should_stop: Callable[[], None] | None = None, cache_dir: Path | None = None,
             duration: float | None = None, about: str = "") -> Result:
    """Read the whole transcript and come back with ranked moments.

    The parts that are not preaching never leave the house. What is left goes to the model
    in as few passages as it fits in, usually one, and that one call also does the choosing:
    a model that has read the whole sermon knows which moments are the best of the service.
    A sermon too long for one passage gets a second round afterwards that weighs the
    passages against each other, because confidence from two separate reads is not
    comparable on its own.

    Passages that were already answered are read from `cache_dir` instead of being sent
    again, so a run that was interrupted or that lost a passage to a rate limit picks up
    where it left off instead of paying for the whole service twice.
    """
    check_provider()
    windows, shape, left_out = sermon_windows(transcript.segments, duration)
    total = len(windows)
    skipped_minutes = int(left_out // 60)
    if total == 0:
        return Result(shape=[b.as_dict() for b in shape], skippedMinutes=skipped_minutes)
    alone = total == 1
    raw: list[ClipCandidate] = []
    failures: list[str] = []
    done = 0

    # Every passage is told what kind of service it sits in, so a moment can be judged
    # against the whole rather than against the minutes around it.
    setting = f"De dienst is opgebouwd als: {structure.summary(shape)}."
    context = f"{setting} {about}".strip()

    def work(window: Window) -> list[ClipCandidate]:
        if should_stop:
            should_stop()
        wanted = wanted_from(window, alone)
        request = window_request(window, context, wanted, alone)
        found = cached_window(cache_dir, window, request)
        if found is None:
            found = analyze_window(window, context, wanted=wanted, alone=alone)
            remember_window(cache_dir, window, found, request)
        out = []
        for c in found:
            start, end = snap(c, window)
            length = end - start
            if length < MIN_CLIP or length > MAX_CLIP or not c.title.strip():
                continue
            opening = opening_line(window.segments, start)
            out.append(ClipCandidate(
                id="", start=start, end=end, title=c.title.strip()[:80], summary=c.summary.strip(),
                reason=c.reason.strip(), confidence=round(c.confidence, 3),
                score=score(c, length, opening),
                part=structure.PART_LABEL[structure.part_at(shape, (start + end) / 2)],
            ))
        return out

    def guarded(window: Window) -> list[ClipCandidate]:
        """One difficult window must not throw away the work done on all the others."""
        try:
            return work(window)
        except Cancelled:
            raise
        except Exception as exc:  # noqa: BLE001
            failures.append(str(exc))
            return []

    def reading(done_so_far: int) -> str:
        if alone:
            return "De preek wordt in een keer doorgelezen"
        extra = f" · {len(failures)} niet gelukt" if failures else ""
        return f"Tekst wordt doorgelezen · deel {min(done_so_far + 1, total)} van {total}{extra}"

    if on_progress:
        on_progress(0.0, reading(0))
    with ThreadPoolExecutor(max_workers=max(1, LLM_CONCURRENCY)) as pool:
        for result in pool.map(guarded, windows):
            raw.extend(result)
            done += 1
            if on_progress:
                on_progress(done / total, reading(done))

    if failures and len(failures) == total:
        nothing = ("De tekst kon niet geanalyseerd worden." if alone
                   else "Geen enkel deel van de tekst kon geanalyseerd worden.")
        raise RuntimeError(f"{nothing} {failures[0]}")
    warning = None
    if failures:
        warning = (f"{len(failures)} van de {total} stukken tekst konden niet geanalyseerd worden, de rest wel. "
                   f"Reden: {failures[0]} Je kunt opnieuw zoeken om ze alsnog te proberen.")

    candidates = dedupe_and_rank(raw)
    chosen = 0
    if candidates:
        if on_progress and not alone:
            on_progress(0.97, "De gevonden momenten worden met elkaar vergeleken")
        if should_stop:
            should_stop()
        try:
            candidates = shortlist(candidates, transcript.segments, shape, about, alone)
            chosen = sum(1 for c in candidates if c.shortlisted)
        except Cancelled:
            raise
        except Exception as exc:  # noqa: BLE001  the moments are worth having even unranked
            print(f"[analyse] kiezen mislukt, de volgorde van de eerste ronde blijft staan: {exc}")
            warning = (warning + " " if warning else "") + (
                "De momenten konden niet met elkaar vergeleken worden, dus de volgorde is die van de "
                "eerste ronde. Je kunt opnieuw zoeken om dat alsnog te proberen.")
    return Result(candidates=candidates, windows=total, failed=len(failures), warning=warning,
                  shape=[b.as_dict() for b in shape], skippedMinutes=skipped_minutes, shortlisted=chosen)
