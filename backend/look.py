"""Colour and contrast: a flat, greyish recording lifted to real black and white, with a little more colour.

A church camera is set up once and left alone, and what reaches the stream is often flat.
Measured on a real Kerkdienstgemist recording: the brightness ran from 30 to 204 where video
has room from 16 to 235, so nothing in it was black and nothing white, and the colour was
weak. Flat and dull reads as poor quality on a phone, even where the sharpness is the same.

So every clip is measured: a dozen frames spread over its seconds, the darkest and the
brightest that really occur (a speck of either does not count), and how much colour there
is. The brightness is then stretched to fill the range, within limits, and a dull picture
gets up to a fifth more colour. A recording that already uses the range is left as it is.
White balance is left alone on purpose: a coloured cloth on the pulpit or the light of a
projector sends any automatic guess the wrong way.

Only the brightness is stretched, not red, green and blue each: stretching those would
add the stretch to the colour as well, on top of the extra colour, and faces turned red.
"""

import json
import subprocess
from pathlib import Path

import numpy as np
from pydantic import BaseModel

SAMPLES = 12  # frames looked at per clip
SAMPLE_W, SAMPLE_H = 640, 360  # smaller, and the dark details blur into grey and the range looks narrower
TAILS = (0.2, 99.8)  # percentiles: a speck of black or of highlight is not the picture's range
BLACK, WHITE = 16, 235  # video range
MOST_LIFT = 24  # nothing brighter than BLACK + this is ever taken for black
MOST_DIM = 40  # nothing darker than WHITE - this is ever taken for white
MOST_GAIN = 1.3  # past this the darks close up and noise and blocking come up with the picture
LEAVE = 1.03  # a stretch smaller than this is not worth doing
COLOUR = 1.2  # extra colour for a dull picture
DULL, COLOURFUL = 15.0, 35.0  # average colour up to DULL gets all of COLOUR, from COLOURFUL none


class Levels(BaseModel):
    """What a clip looks like: its real darkest and brightest, and its average colour."""

    low: float
    high: float
    colour: float  # mean distance from grey in U and V, the same measure as FFmpeg's SATAVG


class Look(BaseModel):
    """What is done to it."""

    low: float  # this brightness becomes black
    gain: float  # and everything is stretched by this much from there
    colour: float  # saturation, 1 is unchanged


def sample(source: Path, at: float) -> np.ndarray | None:
    """One small frame as Y, U and V planes, or None when nothing could be read there."""
    try:
        raw = subprocess.run(
            ["ffmpeg", "-v", "error", "-ss", f"{max(0.0, at):.3f}", "-i", str(source), "-frames:v", "1",
             "-vf", f"scale={SAMPLE_W}:{SAMPLE_H},format=yuv444p", "-f", "rawvideo", "-"],
            capture_output=True, timeout=60).stdout
    except (OSError, subprocess.SubprocessError):
        return None
    if len(raw) != SAMPLE_W * SAMPLE_H * 3:
        return None
    return np.frombuffer(raw, np.uint8).reshape(3, SAMPLE_H, SAMPLE_W)


def measure(source: Path, start: float, length: float) -> Levels | None:
    """The clip's real range and colour, from frames spread over its seconds."""
    frames = [sample(source, start + length * (i + 0.5) / SAMPLES) for i in range(SAMPLES)]
    frames = [f for f in frames if f is not None]
    if not frames:
        return None
    planes = np.stack(frames)
    luma = planes[:, 0].astype(np.float32)
    u = planes[:, 1].astype(np.float32) - 128
    v = planes[:, 2].astype(np.float32) - 128
    low, high = np.percentile(luma, TAILS)
    return Levels(low=round(float(low), 1), high=round(float(high), 1),
                  colour=round(float(np.sqrt(u * u + v * v).mean()), 2))


def look_for(levels: Levels) -> Look | None:
    """The correction for a clip that measured like this, or None when it needs none."""
    low = min(max(levels.low, BLACK), BLACK + MOST_LIFT)
    high = max(min(levels.high, WHITE), WHITE - MOST_DIM)
    gain = (WHITE - BLACK) / max(1.0, high - low)
    if gain > MOST_GAIN:
        # Stretch less, around the middle of what is there, rather than not at all.
        middle, span = (low + high) / 2, (WHITE - BLACK) / MOST_GAIN
        low, gain = middle - span / 2, MOST_GAIN
    share = min(1.0, max(0.0, (COLOURFUL - levels.colour) / (COLOURFUL - DULL)))
    colour = 1 + (COLOUR - 1) * share
    if gain < LEAVE and low - BLACK < 2 and colour < 1.02:
        return None
    return Look(low=round(low, 1), gain=round(gain, 3), colour=round(colour, 2))


def chain(look: Look | None) -> str:
    """The FFmpeg filters for it, to go first in the picture's chain, or nothing."""
    if look is None:
        return ""
    return (f"lutyuv=y='clip((val-{look.low})*{look.gain}+{BLACK},{BLACK},{WHITE})',"
            f"eq=saturation={look.colour},")


def remembered(work: Path, source: Path, start: float, length: float) -> Levels | None:
    """Measure once per clip: the answer is kept next to the clip and used while the range holds."""
    cache = work / "levels.json"
    try:
        stamp = source.stat().st_mtime
    except OSError:
        return None
    key = {"source": source.name, "stamp": stamp, "start": round(start, 2), "length": round(length, 2)}
    try:
        kept = json.loads(cache.read_text(encoding="utf-8"))
        if kept.get("key") == key:
            return Levels(**kept["levels"])
    except (OSError, ValueError, KeyError, TypeError):
        pass
    levels = measure(source, start, length)
    if levels is not None:
        work.mkdir(parents=True, exist_ok=True)
        cache.write_text(json.dumps({"key": key, "levels": levels.model_dump()}), encoding="utf-8")
    return levels
