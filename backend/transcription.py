"""Dutch speech-to-text with faster-whisper."""

import io
import json
import logging
import os
import re
import subprocess
import threading
import warnings
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Callable

from . import gpu, mac, settings
from .models import TEMPLATES_DIR, Segment, Spoken, Transcript, write_atomic

LANGUAGE = "nl"
VOCABULARY_PATH = TEMPLATES_DIR / "woordenlijst.json"
MODEL_SIZE = settings.text("WHISPER_MODEL", "small")
# Only a few minutes of a service ever become clips, so the clip is worth a bigger model.
ACCURATE_MODEL_SIZE = settings.text("WHISPER_MODEL_ACCURATE", "medium")

# How wide a search the decoder runs at each step. Five is the careful setting and one is
# greedy. Measured on ninety seconds of Dutch preaching with the church word list, on the
# small model: 25.6 seconds at five, 14.4 at one, and 6% of the words different, nearly all
# of that a full stop that became a comma. Worth it for a scan, not for what a viewer reads.
SCAN_BEAM = settings.whole("WHISPER_SCAN_BEAM", 1, least=1)
CLIP_BEAM = settings.whole("WHISPER_CLIP_BEAM", 5, least=1)

# Which engine does the listening. "auto" takes the Mac's graphics chip when the machine has
# one and mlx-whisper is installed, and the processor everywhere else. Name one of them to
# settle it yourself, which is also how the two get compared (see tools/speechbench.py).
BACKEND = settings.choice("WHISPER_BACKEND", ("auto", "mlx", "faster-whisper"), "auto")
MLX, CTRANSLATE = "mlx", "faster-whisper"
# "cpu", "cuda", or "auto" to take the card when it works and the processor when it does not.
DEVICE = settings.choice("WHISPER_DEVICE", ("cpu", "cuda", "auto"), "cpu")
COMPUTE_TYPE = settings.text("WHISPER_COMPUTE_TYPE")
CPU_COMPUTE = "int8"  # what the processor can actually do, whatever the card was set to

# Set when a graphics card was asked for and could not be used. The service that was being
# written out says so, so a volunteer knows why it is taking longer than last week.
DEVICE_NOTE: str | None = None

# Caption chunking: subtitles for reels read best as short phrases.
MAX_CHARS = 60  # roughly two lines of subtitle text
MAX_DURATION = 6.0  # seconds
PAUSE_SPLIT = 0.7  # a pause longer than this starts a new segment
MIN_CHARS = 20  # under this a line is too short to be worth ending, full stop or not

# Where a caption may end, and where it had better not. Breaking at sixty characters puts the
# break wherever the counting happens to land, which strands "van" or "de" at the end of a
# line and reads like a machine did it. These are the words that lean on what comes after
# them: articles, prepositions, the bits of a verb that are waiting for the rest.
LEANS_FORWARD = {
    "de", "het", "een", "der", "des", "den",
    "van", "in", "op", "met", "voor", "naar", "bij", "uit", "over", "door", "tot", "aan",
    "om", "te", "onder", "tegen", "tussen", "zonder", "binnen", "langs", "richting", "per",
    "en", "of", "maar", "want", "dus", "als", "dan", "zoals", "omdat", "doordat", "terwijl",
    "mijn", "jouw", "zijn", "haar", "onze", "hun", "deze", "die", "dat", "dit", "wat", "wie",
    "is", "was", "zijn", "wordt", "werd", "heeft", "had", "kan", "zal", "moet", "gaat",
    "niet", "geen", "wel", "ook", "nog", "al", "er", "hier", "daar",
}

# A caption that starts with one of these reads as a continuation rather than a fragment.
STARTS_WELL = {
    "en", "maar", "want", "dus", "omdat", "terwijl", "toen", "als", "wanneer", "zodat",
    "dat", "die", "waarin", "waarmee", "waarop", "waardoor", "hoewel", "totdat", "voordat",
}

ENDS_SENTENCE = (".", "?", "!", "…")
ENDS_CLAUSE = (",", ";", ":")
EXTRACT_SHARE = 0.08  # first slice of the progress bar: pulling the audio out of the video
MODEL_SHARE = 0.04  # second slice: loading the speech model, which is slow only the first time

# The phases a caller is told about, so it can say what is happening rather than guess
# from a number. "text" is the long one and the only one worth estimating a time for.
AUDIO, MODEL, TEXT = "audio", "model", "text"

_models: dict[str, object] = {}
_models_lock = threading.Lock()

# Whisper listens to the last 223 tokens of a prompt and drops the rest without a word
# (`previous_tokens[-(max_length // 2 - 1):]` in faster_whisper's get_prompt). Measured on this
# vocabulary with the small model's own tokenizer: a comma list of Dutch church words runs
# about 2.7 characters to the token, prose about 3.6, and the most expensive single word 1.75.
# The trimming below counts characters at 2.3, which under-fills rather than overruns.
PROMPT_TOKENS = 223
CHARS_PER_TOKEN = 2.3
PROMPT_CHARS = int(PROMPT_TOKENS * CHARS_PER_TOKEN)

OPENING = "Opname van een Nederlandse kerkdienst. Er komen woorden in voor als:"

# Ordered droppable first, precious last, inside every group and between them, because the end
# of the list is what survives when there is not room for all of it. Words the model gets right
# on its own earn nothing here and are left out; what is in here is what it gets wrong: church
# jobs, the spelling of the books, the names, and the words a sermon leans on.
DEFAULT_WORDS = {
    "algemeen": ["gemeente", "eredienst", "kerkenraad", "schriftlezing", "voorbede",
                 "mededelingen", "collecte", "ouderling", "diaken", "voorganger"],
    "geloofswoorden": ["gerechtigheid", "heiliging", "wederkomst", "opstanding", "verzoening",
                       "barmhartigheid", "ontferming", "genade", "avondmaal", "zegenbede"],
    "bijbelboeken": ["Genesis", "Exodus", "Openbaring", "Handelingen", "Jesaja", "Jeremia",
                     "Ezechiël", "Mattheüs", "Korinthiërs", "Galaten", "Efeziërs",
                     "Filippenzen", "Kolossenzen", "Hebreeën"],
    "namen": ["David", "Salomo", "Elia", "Jona", "Petrus", "Paulus", "Martha", "Lazarus",
              "Nicodemus", "Zacheüs", "Pilatus", "Herodes", "Mozes", "Aäron", "farao",
              "Farizeeën", "Schriftgeleerden", "Messias"],
    "moeilijk": ["profeten", "apostelen", "discipelen", "gezang", "psalm", "liederen", "lied",
                 "Sela", "Opwekking", "kudde", "schapen", "herders", "herder",
                 "Heere", "Here", "HEER", "Heilige Geest", "Jezus Christus"],
}

DEFAULT_VOCABULARY = {
    "opening": OPENING,
    "words": DEFAULT_WORDS,
    # No room in the prompt is no reason to let a mishearing stand: this is applied to the
    # finished text instead, and nothing limits how long it gets.
    # Every one of these is a mishearing that is not itself a Dutch word, so putting it right
    # cannot damage a sentence that meant something else. "heller" is left alone for exactly
    # that reason, even though it is what the model used to say: it is a real word.
    "corrections": {
        # Respellings: none of these is a Dutch word, so putting them right is safe.
        "lee": "Lied",
        "lie": "Lied",
        "heerder": "herder",
        "heerders": "herders",
        "heider": "herder",
        "heiders": "herders",
        "header": "herder",
        "headers": "herders",
        "heiligegeest": "Heilige Geest",
        # Capitals: the words are heard right and written small.
        "here jezus": "Here Jezus",
        "heer jezus": "Heer Jezus",
        "jezus christus": "Jezus Christus",
        "heilige geest": "Heilige Geest",
        "koninkrijk van god": "Koninkrijk van God",
        "gods woord": "Gods Woord",
    },
}


def load_vocabulary() -> dict:
    """Words that help the speech model, and fixes for the mistakes it keeps making.

    Lives in templates/woordenlijst.json so every church can add its own names.
    """
    if not VOCABULARY_PATH.is_file():
        VOCABULARY_PATH.write_text(json.dumps(DEFAULT_VOCABULARY, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        return dict(DEFAULT_VOCABULARY)
    try:
        data = json.loads(VOCABULARY_PATH.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001  a broken file should not stop a transcription
        return dict(DEFAULT_VOCABULARY)
    return {"opening": data.get("opening", OPENING),
            "words": data.get("words", {}),
            # Written before the list had groups: one ready-made sentence is all there was.
            "initialPrompt": data.get("initialPrompt", ""),
            "corrections": data.get("corrections", {})}


def church_words() -> tuple[str, dict[str, str]]:
    """This church's own names and fixes, on top of the shared word list.

    Returns (a sentence naming them for the model, the corrections to apply afterwards).
    """
    try:
        from . import brands

        brand = brands.active()
    except Exception:  # noqa: BLE001  a broken brand must not stop a transcription
        return "", {}
    said = []
    name = brand.church.churchName
    if name:
        said.append(f"De kerk heet {name}.")
    vocabulary = brand.vocabulary
    for label, group in (("Er wordt gepreekt door", vocabulary.preachers),
                         ("De serie heet", vocabulary.series),
                         ("Er wordt gezongen uit", vocabulary.songbooks),
                         ("Plaatsen en locaties", vocabulary.places),
                         ("Let ook op", vocabulary.extra)):
        words = [w.strip() for w in group if w.strip()]
        if words:
            said.append(f"{label}: {', '.join(words)}.")
    return " ".join(said), dict(vocabulary.corrections)


def fit_words(words: list[str], room: int) -> list[str]:
    """As many words as fit in `room` characters, counted from the back.

    From the back because the back is what reaches the model: whisper keeps the tail of a
    prompt, and the list is ordered with the words worth protecting at the end.
    """
    kept: list[str] = []
    used = 0
    for word in reversed(words):
        cost = len(word) + 2  # ", "
        if used + cost > room:
            break
        kept.append(word)
        used += cost
    return list(reversed(kept))


def initial_prompt() -> str:
    """The shared vocabulary plus what this church calls things, inside what whisper reads.

    The church's own names go last and are never trimmed: a preacher's name is the one thing
    the model cannot guess, and the shared list is only there to fill what is left.
    """
    vocabulary = load_vocabulary()
    mine, _fixes = church_words()
    groups = vocabulary.get("words") or {}
    listed = [word.strip() for group in groups.values() for word in group if word.strip()]
    if not listed:
        # A word list from before the groups: one ready-made sentence, left as it was written.
        prompt = vocabulary.get("initialPrompt", "")
        for sentence in mine.split(". "):
            clean = sentence.strip(" .")
            if clean and clean.lower() not in prompt.lower():
                prompt = f"{prompt} {clean}."
        return prompt.strip()

    opening = vocabulary.get("opening") or OPENING
    room = PROMPT_CHARS - len(opening) - len(mine) - 2
    kept = fit_words(listed, max(0, room))
    said = f"{opening} {', '.join(kept)}." if kept else opening
    return f"{said} {mine}".strip() if mine else said


def all_corrections() -> dict[str, str]:
    """The shared fixes, with this church's own on top."""
    fixes = dict(load_vocabulary().get("corrections", {}))
    _prompt, mine = church_words()
    fixes.update(mine)
    return fixes


def apply_corrections(text: str, corrections: dict[str, str]) -> str:
    """Replace known mishearings, whole words only, keeping the sentence's capital."""
    for wrong, right in corrections.items():
        if not wrong.strip():
            continue
        pattern = re.compile(rf"\b{re.escape(wrong)}\b", re.IGNORECASE)
        text = pattern.sub(right, text)
    return text


@dataclass(frozen=True)
class Listening:
    """How carefully to listen, and why.

    Reading a whole service to find what is worth posting and writing out the words a
    viewer will read are two different jobs. The first runs over an hour and a half and
    only has to be good enough to follow the argument; the second runs over the three or
    four minutes that became clips, where a slower setting costs seconds.
    """

    model: str
    beam: int
    why: str  # for the log, and for anyone wondering which pass they are looking at


def scanning() -> Listening:
    """The whole service, once, to find the moments worth clipping."""
    return Listening(MODEL_SIZE, SCAN_BEAM, "scan")


def writing(accurate: bool = False) -> Listening:
    """One clip, so the words under it are the ones that were said."""
    return Listening(ACCURATE_MODEL_SIZE if accurate else MODEL_SIZE, CLIP_BEAM, "clip")


def engine() -> str:
    """Which of the two does the work, given the setting and what this machine has."""
    if BACKEND in (MLX, CTRANSLATE):
        return BACKEND
    return MLX if mac.possible() else CTRANSLATE


def batch_size(model: str = MODEL_SIZE) -> int:
    """How many 30-second windows to decode at once.

    Batching is what makes this bearable on a laptop CPU: the windows go through the
    encoder together instead of one after another. Measured on four cores with the small
    model over eight minutes of Dutch speech: 3.6x realtime one at a time, 6.8x at two,
    8.3x at four, 8.6x at eight, and back down to 7.5x at sixteen, where the cores are
    oversubscribed. The bigger model holds more weights, so it gets a smaller batch.
    """
    override = os.environ.get("WHISPER_BATCH_SIZE")
    if override and override.isdigit() and int(override) > 0:
        return int(override)
    room = min(8, max(2, (os.cpu_count() or 2) * 2))
    return max(2, room // 2) if model == ACCURATE_MODEL_SIZE else room


def quiet_hub_notices() -> None:
    """Keep Hugging Face's housekeeping advice out of the window a volunteer is watching.

    The speech model is public and downloads perfectly well without an account, but their
    client asks for an access token on every run. A warning in the black window reads like
    something is broken when nothing is. Put HF_TOKEN in config.env and this stops at the
    source, and the first download goes quicker; without one, it is only noise.
    """
    if os.environ.get("HF_TOKEN") or os.environ.get("HUGGING_FACE_HUB_TOKEN"):
        return
    # It has arrived over both channels depending on the version, so close both.
    for pattern in (r".*unauthenticated requests.*", r".*HF_TOKEN.*", r".*higher rate limits.*"):
        warnings.filterwarnings("ignore", message=pattern)
    for name in ("huggingface_hub", "huggingface_hub.file_download", "huggingface_hub._http", "hf_xet"):
        logging.getLogger(name).setLevel(logging.ERROR)


# What the speech models weigh, so a bar can move before the first byte is counted. These
# are the download, not what they take on disk after unpacking.
MODEL_MB = {"tiny": 75, "base": 145, "small": 484, "medium": 1530, "large-v2": 3090,
            "large-v3": 3090, "distil-large-v3": 1510}


def model_repo(size: str) -> str | None:
    """Which Hugging Face repository holds this model."""
    if "/" in size:
        return size
    try:
        from faster_whisper import utils

        return utils._MODELS.get(size)
    except Exception:  # noqa: BLE001
        return f"Systran/faster-whisper-{size}" if size else None


def base_bar() -> type:
    """The tqdm class Hugging Face uses, to inherit from rather than imitate.

    `huggingface_hub.utils.tqdm` is a class until something imports the submodule of that
    name, after which the attribute is the module and subclassing it raises. Both spellings
    turn up depending on what else has been imported, so both are tried, and plain tqdm is
    there for the day they rename it again.
    """
    try:
        from huggingface_hub.utils import tqdm as maybe

        if isinstance(maybe, type):
            return maybe
        found = getattr(maybe, "tqdm", None)
        if isinstance(found, type):
            return found
    except Exception:  # noqa: BLE001
        pass
    from tqdm.auto import tqdm

    return tqdm


class Arriving:
    """What has come in so far, out of the progress bars Hugging Face keeps.

    Since hf-xet came along the files are assembled somewhere else and the cache folder
    stays empty until the very end, so counting bytes on disk reports five megabytes of
    four hundred and then jumps. The bars are the only honest signal left.

    There are two of them over the same download, one for what comes over the wire and one
    for what gets put back together. Adding them up counts every megabyte twice, so this
    takes the furthest-along of them and the largest total, each on its own. Neither can
    overshoot the download, and a release of theirs that adds a third bar changes nothing.

    What it must not do is read tqdm's own counter. A bar that is switched off keeps taking
    updates and quietly stops adding them up, and this app switches them off itself, in
    quiet_hub_notices, to keep Hugging Face's housekeeping advice out of the window. So the
    bytes are added up here, where nothing else can decide they do not matter.
    """

    def __init__(self, expected: float, report: Callable[[float, str], None]):
        self.expected = expected
        self.report = report
        self.bars: list = []
        self.lock = threading.Lock()
        self.said = -1.0

    def note(self) -> None:
        with self.lock:
            done = max((b.seen for b in self.bars), default=0.0)
            widest = max((float(getattr(b, "total", 0) or 0) for b in self.bars), default=0.0)
            total = max(widest, self.expected, done)
            share = min(0.99, done / total) if total else 0.0
            # Once per megabyte is plenty. A callback per chunk is thousands of writes to a
            # job message nobody reads faster than they can blink.
            if done and abs(done - self.said) < 1e6:
                return
            self.said = done
        self.report(share, f"Spraakmodel wordt opgehaald \u00b7 {done / 1e6:.0f} van "
                           f"{total / 1e6:.0f} MB \u00b7 dit gebeurt \u00e9\u00e9n keer")

    def bar(self):
        """A progress bar Hugging Face can use, that counts instead of drawing.

        Built on their own tqdm rather than from scratch. Their downloader reaches for more
        of tqdm than a progress bar looks like it needs, and which parts differ per version;
        inheriting means a new release cannot take the download down over a method nobody
        here has heard of. The drawing goes to a sink, because the window already has the
        line this writes.
        """
        counter = self
        hub_tqdm = base_bar()

        class Counted(hub_tqdm):
            def __init__(self, *args, **kwargs):
                kwargs["file"] = io.StringIO()
                kwargs["leave"] = False
                self.seen = float(kwargs.get("initial") or 0)
                super().__init__(*args, **kwargs)
                with counter.lock:
                    counter.bars.append(self)
                counter.note()

            def update(self, n=1):
                done = super().update(n)
                self.seen += float(n or 0)
                counter.note()
                return done

        return Counted


def fetch_model(size: str, on_progress: Callable[[float, str], None] | None = None) -> str:
    """Fetch the model with the download in plain sight, and hand back the folder.

    `WhisperModel(size)` downloads it silently. On a first run that is 460 MB of nothing
    happening while the interface says "Het spraakmodel wordt geladen" and the bar sits at
    four percent, which is the one moment in this app where it looks broken and is not.

    faster-whisper's own `download_model` hard-codes a disabled progress bar, so this asks
    Hugging Face directly with the same patterns it uses. Anything that goes wrong hands the
    size back unchanged and lets `WhisperModel` do its own downloading, quietly, the way it
    always did; a model that is already here comes back in a moment and says nothing.
    """
    repo = model_repo(size)
    if on_progress is None or not repo:
        return size
    try:
        import huggingface_hub
    except Exception:  # noqa: BLE001
        return size

    counter = Arriving(MODEL_MB.get(size, 0) * 1e6, on_progress)
    try:
        return huggingface_hub.snapshot_download(
            repo,
            allow_patterns=["config.json", "preprocessor_config.json", "model.bin",
                            "tokenizer.json", "vocabulary.*"],
            tqdm_class=counter.bar(),
        )
    except Exception:  # noqa: BLE001  never a reason not to transcribe
        return size


def compute_for(device: str) -> str:
    """Which number format to decode in. int8 on the processor, float16 on a card."""
    if COMPUTE_TYPE:
        return COMPUTE_TYPE
    return CPU_COMPUTE if device == "cpu" else "float16"


def load_whisper(size: str, on_progress: Callable[[float, str], None] | None = None):
    """Build the model on the card when there is one, and on the processor when there is not.

    A Windows machine with WHISPER_DEVICE=cuda and no CUDA libraries used to take the whole
    app down with "Library cublas64_12.dll is not found or cannot be loaded". CTranslate2
    ships without those libraries and nothing puts the pip ones on the search path, so most
    of the time pointing at them is enough. When it is not, the processor takes over: a
    transcription that is slower beats one that never starts, and Sunday afternoon is a bad
    time to be installing CUDA.
    """
    global DEVICE_NOTE
    from faster_whisper import WhisperModel

    gpu.make_findable()
    # Downloaded here, where it can be counted, rather than inside WhisperModel where it
    # cannot. Hands back the same string when there is nothing to fetch or nobody watching.
    size = fetch_model(size, on_progress)
    device = "cuda" if DEVICE == "auto" else DEVICE
    if device == "cpu":
        return WhisperModel(size, device="cpu", compute_type=compute_for("cpu"))
    try:
        return WhisperModel(size, device=device, compute_type=compute_for(device))
    except Exception as exc:  # noqa: BLE001
        if not gpu.blames_cuda(exc):
            raise
        DEVICE_NOTE = gpu.advice(exc)
        print(f"[uitschrijven] {DEVICE_NOTE}")
        # Not compute_for("cpu"): a WHISPER_COMPUTE_TYPE set for the card is float16, which
        # the processor cannot decode in either.
        return WhisperModel(size, device="cpu", compute_type=CPU_COMPUTE)


def get_model(size: str | None = None, on_progress: Callable[[float, str], None] | None = None):
    """The loaded model of this size, kept for the life of the process."""
    size = size or MODEL_SIZE
    with _models_lock:
        if size not in _models:
            quiet_hub_notices()
            from faster_whisper import WhisperModel  # noqa: F401  checked before we go on

            try:
                _models[size] = load_whisper(size, on_progress)
            except Exception as exc:  # noqa: BLE001
                raise RuntimeError(
                    f"Het spraakmodel '{size}' kon niet geladen worden. De eerste keer wordt het gedownload; "
                    f"controleer de internetverbinding en de vrije schijfruimte. ({exc})"
                ) from exc
        return _models[size]


def extract_audio(source: Path, wav_path: Path, should_stop: Callable[[], None] | None = None,
                  on_progress: Callable[[float], None] | None = None, duration: float | None = None,
                  start: float = 0.0) -> None:
    """Pull the audio out of the video, or out of a range of it.

    Reports how far it is and checks `should_stop` while running, so the bar moves from the
    first second and stopping feels immediate.
    """
    seek = ["-ss", f"{start:.3f}"] if start else []
    limit = ["-t", f"{duration:.3f}"] if duration else []
    command = ["ffmpeg", "-y", "-loglevel", "error", "-nostats", "-progress", "pipe:1",
               *seek, "-i", str(source), *limit,
               "-vn", "-ac", "1", "-ar", "16000", "-c:a", "pcm_s16le", str(wav_path)]
    try:
        proc = subprocess.Popen(command, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)
    except FileNotFoundError as exc:
        raise RuntimeError("FFmpeg is niet gevonden. Sluit de app en start opnieuw met start.bat of start.command.") from exc
    assert proc.stdout is not None
    for line in proc.stdout:
        if should_stop:
            try:
                should_stop()
            except BaseException:
                proc.terminate()
                proc.wait(timeout=10)
                wav_path.unlink(missing_ok=True)
                raise
        key, _, value = line.strip().partition("=")
        if key in ("out_time_us", "out_time_ms") and value.lstrip("-").isdigit() and on_progress and duration:
            on_progress(min(1.0, (int(value) / 1_000_000) / duration))
    if proc.wait() != 0:
        stderr = proc.stderr.read() if proc.stderr else ""
        raise RuntimeError("Het geluid kon niet uit de video gehaald worden: " + stderr.strip()[-400:])


PARTIAL_FILE = "partial.json"
SAVE_EVERY = 30.0  # seconds of audio between saves of the work in progress


@dataclass
class Word:
    """One word with its timing. Plain data, so a half-finished run can be written to disk."""

    start: float
    end: float
    word: str


def load_partial(work_dir: Path) -> tuple[float, list[Word], list[Segment]]:
    """Where an interrupted run got to: (seconds done, words, whole-sentence fallback)."""
    path = work_dir / PARTIAL_FILE
    if not path.is_file():
        return 0.0, [], []
    try:
        saved = json.loads(path.read_text(encoding="utf-8"))
        return (float(saved["upTo"]),
                [Word(**w) for w in saved["words"]],
                [Segment(**s) for s in saved["segments"]])
    except Exception:  # noqa: BLE001  a damaged half-finished file just means starting over
        return 0.0, [], []


def save_partial(work_dir: Path, up_to: float, words: list[Word], segments: list[Segment]) -> None:
    write_atomic(work_dir / PARTIAL_FILE, json.dumps({
        "upTo": round(up_to, 2),
        "words": [asdict(w) for w in words],
        "segments": [s.model_dump() for s in segments],
    }))


def transcribe(source: Path, work_dir: Path, on_progress: Callable[[float, str], None] | None = None,
               duration: float | None = None, should_stop: Callable[[], None] | None = None,
               start: float = 0.0, how: "Listening | None" = None) -> Transcript:
    """Transcribe `source`, or the `duration` seconds of it that begin at `start`.

    `how` says which job this is: scanning() reads a whole service to find the moments,
    writing() writes out one clip for people to read. Left out, it writes out a clip,
    because a clip that arrived on its own is the only thing anyone asks for by hand.

    `on_progress(fraction, phase)` is called as the work moves along, with `phase` one of
    AUDIO, MODEL or TEXT so the caller can say what is happening instead of inferring it
    from the number. `should_stop()` is called between segments and may raise to end the
    work early. Timecodes come back relative to the start of the range, matching the clip
    the user sees.

    The work is written down as it goes. Closing the laptop during a half-hour run used to
    throw all of it away; now the next attempt carries on from the last saved point.
    """
    report = on_progress or (lambda _f, _p: None)
    how = how or writing()
    work_dir.mkdir(parents=True, exist_ok=True)
    done_to, words, fallback = load_partial(work_dir)
    if duration and done_to >= duration - 1.0:
        done_to, words, fallback = 0.0, [], []  # nothing left to do; start over rather than stall

    wav_path = work_dir / "audio.wav"
    report(0.0, AUDIO)
    remaining = (duration - done_to) if duration else None
    extract_audio(source, wav_path, should_stop,
                  on_progress=lambda f: report(EXTRACT_SHARE * f, AUDIO),
                  duration=remaining, start=start + done_to)

    report(EXTRACT_SHARE, MODEL)
    base = EXTRACT_SHARE + MODEL_SHARE
    # Both engines hand back the same shape: pieces with .start, .end, .text and .words, in
    # the seconds of the audio just decoded. Everything below this line is the same either way.
    if engine() == MLX:
        # The model loads on the first piece rather than here, so the bar is told now that
        # the waiting has started and the pieces move it along from there.
        report(base, TEXT)
        if should_stop:
            should_stop()
        whisper_segments = mac.listen(wav_path, how.model, initial_prompt() or None,
                                      should_stop, LANGUAGE)
    else:
        from faster_whisper import BatchedInferencePipeline

        # The model phase owns its own slice of the bar, and on a first run that slice is a
        # 460 MB download. Everything reported from in there lands inside it.
        def while_fetching(share: float, message: str) -> None:
            report(EXTRACT_SHARE + MODEL_SHARE * share, message)

        model = get_model(how.model, while_fetching)
        if should_stop:
            should_stop()
        report(base + (1 - base) * (done_to / duration) if duration else base, TEXT)
        whisper_segments, _info = BatchedInferencePipeline(model=model).transcribe(
            str(wav_path),
            language=LANGUAGE,
            beam_size=how.beam,
            vad_filter=True,
            word_timestamps=True,
            initial_prompt=initial_prompt() or None,
            batch_size=batch_size(how.model),
        )

    saved_at = done_to
    try:
        for seg in whisper_segments:
            if should_stop:
                should_stop()
            # Timings come back relative to the piece of audio just decoded, so shift them
            # onto the clip the user is looking at.
            at = done_to + seg.end
            if duration:
                report(min(0.99, base + (1 - base) * (at / duration)), TEXT)
            fallback.append(Segment(start=round(done_to + seg.start, 2), end=round(at, 2),
                                    text=seg.text.strip()))
            words.extend(Word(round(done_to + w.start, 2), round(done_to + w.end, 2), w.word)
                         for w in (seg.words or []))
            if at - saved_at >= SAVE_EVERY:
                save_partial(work_dir, at, words, fallback)
                saved_at = at
    except BaseException:
        # Interrupted or stopped: keep what has been heard so far for the next attempt.
        save_partial(work_dir, saved_at, words, fallback)
        raise

    segments = chunk_words(words) if words else fallback
    corrections = all_corrections()
    for seg in segments:
        # Only the text. The words beside it are there for their timings; subtitles.word_times
        # takes the words themselves from the text, so a correction lands in both at once.
        seg.text = apply_corrections(seg.text, corrections)
    (work_dir / PARTIAL_FILE).unlink(missing_ok=True)
    return Transcript(language=LANGUAGE, segments=[s for s in segments if s.text])


def plain(word) -> str:
    """The word without its punctuation or capital, for looking it up in a list."""
    return word.word.strip().strip("\"'“”‘’()[[]").rstrip(".,!?;:…").lower()


def length_of(words, first: int, last: int) -> int:
    """How many characters words[first:last] make as one line."""
    return sum(len(w.word.strip()) for w in words[first:last]) + max(0, last - first - 1)


def furthest(words, first: int) -> int:
    """The last word that could still go in this caption, on length, time and silence.

    A long pause or a finished sentence ends a caption whatever the length says, because
    reading on past either of those is what makes a caption feel out of step with the voice.
    """
    last = first + 1
    while last < len(words):
        if length_of(words, first, last + 1) > MAX_CHARS:
            break
        if words[last].end - words[first].start > MAX_DURATION:
            break
        if words[last].start - words[last - 1].end > PAUSE_SPLIT:
            break
        if (words[last - 1].word.strip().endswith(ENDS_SENTENCE)
                and length_of(words, first, last) >= MIN_CHARS):
            break
        last += 1
    return min(last, len(words))


def break_score(words, first: int, at: int) -> float:
    """How good a caption ending just before words[at] would be.

    Punctuation and silence are where a listener hears the sentence stop, so those are worth
    the most. A line is docked for ending on a word that leans on the next one, and credited
    for being reasonably full, so a good break early still beats a bad one at the limit.
    """
    before = words[at - 1]
    said = before.word.strip()
    length = length_of(words, first, at)
    score = 0.0
    if length < MIN_CHARS:
        # Three words on a line of their own read as a stutter, full stop or not, so a short
        # line gets no credit for the punctuation it happens to end on.
        score -= 8.0
    elif said.endswith(ENDS_SENTENCE):
        score += 10.0
    elif said.endswith(ENDS_CLAUSE):
        score += 4.0
    if at < len(words):
        gap = max(0.0, words[at].start - before.end)
        # A silence this long is where the voice stopped, which beats any punctuation for
        # knowing where the caption should stop too.
        score += 8.0 if gap >= PAUSE_SPLIT else min(3.0, gap * 4.0)
        if plain(words[at]) in STARTS_WELL:
            score += 2.0
    if plain(before) in LEANS_FORWARD:
        score -= 6.0
    return score + 2.0 * min(1.0, length / MAX_CHARS)


def chunk_words(words) -> list[Segment]:
    """Group whisper words into caption-sized segments, breaking where a sentence breathes."""
    segments: list[Segment] = []
    first = 0
    while first < len(words):
        end = furthest(words, first)
        best = end
        if end - first > 2:
            best = max(range(first + 1, end + 1), key=lambda at: (break_score(words, first, at), at))
        taken = words[first:best]
        segments.append(Segment(
            start=round(taken[0].start, 2),
            end=round(taken[-1].end, 2),
            text=" ".join(w.word.strip() for w in taken),
            words=[Spoken(start=round(w.start, 2), end=round(w.end, 2), word=w.word.strip())
                   for w in taken],
        ))
        first = best
    return segments
