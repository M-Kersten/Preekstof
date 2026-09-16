"""Speech on the Mac's own graphics chip.

faster-whisper decodes through CTranslate2, which has a CUDA backend and no Metal one, so on
an Apple laptop it runs on the processor while the graphics chip sits there doing nothing.
MLX is Apple's own array library, and mlx-whisper runs the same Whisper weights on that chip.

Underneath it is a different engine; above it nothing changes. The pieces handed back look
like faster-whisper's, so resuming, the progress bar, the caption chunking and the church
word list all carry on as they were.

It stays off unless the machine can really do it: Apple Silicon, with mlx-whisper installed
from backend/requirements-mac.txt, which is not part of the normal install because it pulls
in a couple of gigabytes nobody on Windows or Linux can use.

One thing MLX will not do is hand back a sentence at a time. It takes a file, thinks, and
answers when it is finished, which over an hour and a half would mean a bar that does not
move, a Stoppen button that does nothing and a closed laptop costing the lot. So the audio is
cut into pieces here and fed to it one at a time, and the cut goes looking for a silence so
it does not land in the middle of a word.
"""

import os
import platform
import wave
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterator

import numpy as np

from . import settings

SAMPLE_RATE = 16000
PIECE = settings.number("MLX_PIECE_SECONDS", 300, least=10)  # how much to hand over at once
LOOK = 20.0  # how far from the target to go looking for a quiet moment to cut at
FRAME = 0.1  # the silence is measured in tenths of a second

# Whisper weights converted for MLX. Same model names as faster-whisper uses, so a church
# that set WHISPER_MODEL=medium gets the medium one here too.
REPOS = {
    "tiny": "mlx-community/whisper-tiny-mlx",
    "base": "mlx-community/whisper-base-mlx",
    "small": "mlx-community/whisper-small-mlx",
    "medium": "mlx-community/whisper-medium-mlx",
    "large-v3": "mlx-community/whisper-large-v3-mlx",
}


@dataclass
class Said:
    """One stretch of speech, shaped like the pieces faster-whisper yields."""

    start: float
    end: float
    text: str
    words: list = field(default_factory=list)


@dataclass
class Spoken:
    """One word, likewise."""

    start: float
    end: float
    word: str


def apple_silicon() -> bool:
    return platform.system() == "Darwin" and platform.machine() == "arm64"


def installed() -> bool:
    """Is mlx-whisper actually here? Importing it is the only honest way to know."""
    try:
        import mlx_whisper  # noqa: F401
    except Exception:  # noqa: BLE001  not installed, or installed on the wrong machine
        return False
    return True


def possible() -> bool:
    """Can this machine listen on its graphics chip?"""
    return apple_silicon() and installed()


def repo_for(model: str) -> str:
    """Which converted model to fetch. An unknown name is passed on as a repo of its own."""
    return REPOS.get(model, model if "/" in model else REPOS["small"])


# --- cutting the audio into pieces -------------------------------------------------


def read_wav(path: Path) -> np.ndarray:
    """The 16 kHz mono audio the app already extracted, as it was written.

    Left as whole numbers on purpose. An hour and a half is 172 MB like this and twice that
    as floats, and only the piece being decoded has to be a float at any one moment.
    """
    with wave.open(str(path), "rb") as sound:
        if sound.getsampwidth() != 2 or sound.getnchannels() != 1:
            raise ValueError("verwacht werd mono 16-bit geluid")
        raw = sound.readframes(sound.getnframes())
    return np.frombuffer(raw, np.int16)


def as_floats(audio: np.ndarray) -> np.ndarray:
    """One piece, in the -1 to 1 that the model wants."""
    return audio.astype(np.float32) / 32768.0


def loudness(audio: np.ndarray, rate: int = SAMPLE_RATE) -> np.ndarray:
    """How loud each tenth of a second is, in blocks, so a whole service is never squared at once."""
    step = max(1, int(FRAME * rate))
    usable = len(audio) - len(audio) % step
    if usable <= 0:
        return np.zeros(1, np.float32)
    frames = audio[:usable].reshape(-1, step)
    level = np.empty(len(frames), np.float32)
    block = 10_000  # about a thousand seconds at a time
    for at in range(0, len(frames), block):
        part = frames[at:at + block].astype(np.float32)
        level[at:at + len(part)] = np.sqrt((part * part).mean(axis=1))
    return level


def seams(audio: np.ndarray, every: float = PIECE, rate: int = SAMPLE_RATE) -> list[int]:
    """Where to cut, in samples: near every `every` seconds, at the quietest moment there.

    A cut through the middle of a word costs that word, and the model is listening in
    thirty-second windows anyway, so the exact length of a piece matters far less than where
    its edge lands.
    """
    if every <= 0 or len(audio) <= every * rate:
        return []
    level = loudness(audio, rate)
    per_second = 1 / FRAME
    cuts: list[int] = []
    at = every
    while at * rate < len(audio) - rate:  # never leave a scrap of a piece at the end
        first = int(max(0, (at - LOOK) * per_second))
        last = int(min(len(level), (at + LOOK) * per_second))
        if last <= first:
            break
        quietest = first + int(np.argmin(level[first:last]))
        cut = int(quietest * FRAME * rate)
        if not cuts or cut > cuts[-1] + rate:  # keep the pieces in order and non-empty
            cuts.append(cut)
        at += every
    return cuts


def pieces(audio: np.ndarray, every: float = PIECE,
           rate: int = SAMPLE_RATE) -> list[tuple[float, np.ndarray]]:
    """The audio in order, each piece with the second it starts at."""
    edges = [0, *seams(audio, every, rate), len(audio)]
    return [(edges[i] / rate, audio[edges[i]:edges[i + 1]]) for i in range(len(edges) - 1)]


# --- listening ---------------------------------------------------------------------


def listen(wav: Path, model: str, prompt: str | None = None,
           should_stop: Callable[[], None] | None = None,
           language: str = "nl") -> Iterator[Said]:
    """Hand the audio over piece by piece, and give back what was said, in clip time.

    A generator on purpose: the caller asks for the next sentence, so a piece is only
    started when the one before it has been read, which is what makes Stoppen arrive
    within a piece rather than at the end of the service.
    """
    import mlx_whisper

    audio = read_wav(wav)
    repo = repo_for(model)
    for at, part in pieces(audio):
        if should_stop:
            should_stop()
        heard = mlx_whisper.transcribe(
            as_floats(part),
            path_or_hf_repo=repo,
            language=language,
            initial_prompt=prompt,
            word_timestamps=True,
            verbose=None,
        )
        for segment in heard.get("segments", []):
            yield Said(
                start=at + float(segment["start"]),
                end=at + float(segment["end"]),
                text=segment.get("text", ""),
                words=[Spoken(at + float(w["start"]), at + float(w["end"]), w["word"])
                       for w in segment.get("words") or []],
            )
