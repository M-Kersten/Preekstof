"""How fast this computer writes out a service, measured rather than guessed.

The most common way a pilot fails is not a bug. It is a church that finds out on Sunday
afternoon that its computer needs two hours, and stops using the app. So the readiness
panel has to name a number before the first upload, and that number has to be about right.

Two ways of knowing, in order of how much they are worth:

  1. This machine, doing this. Every transcription writes down how many seconds of audio it
     heard and how long that took. From the second service onwards the panel is quoting the
     church's own computer, which cannot be argued with.
  2. Machines somebody measured. Until then, the processor this computer reports is looked
     up in a table of machines that were actually timed. A near match is said as a range and
     called what it is: an indication.

What is deliberately absent is a synthetic benchmark. Timing a model on generated audio
measures the encoder and not the decoding, which is where a slow machine loses its hour, and
a number that is confidently wrong is worse than a range that admits it.
"""

import json
import platform
import re
import statistics
from dataclasses import dataclass

from .models import TEMPLATES_DIR, write_atomic

KEPT = TEMPLATES_DIR / "speed.json"
REMEMBER = 8  # runs to average over; a laptop on battery is slower than the same one on mains
SERVICE_MINUTES = 90  # what "a service" means when the panel states a number
TOO_SHORT = 120.0  # a clip of ten seconds says nothing about an hour and a half


@dataclass
class Rate:
    """Seconds of work per second of audio. Below 1 is faster than real time."""

    per_second: float
    runs: int
    engine: str
    model: str
    measured_here: bool = True

    def minutes_for(self, audio_minutes: float = SERVICE_MINUTES) -> float:
        return audio_minutes * self.per_second


# Machines that were actually timed, writing out a service with the `small` model. The
# processor name is matched loosely, because Windows, macOS and Linux each report it
# differently and none of them agrees on spacing.
#
# Adding a row: run a real service, open templates/speed.json, and put the number here with
# the processor as platform.processor() reports it. A guessed row is worse than no row.
MEASURED = (
    # (pattern, seconds of work per second of audio, what to call the machine)
    # Measured: 4 cores, faster-whisper `small`, 493 seconds of Dutch preaching in 100.4
    # seconds of work. A modern desktop processor with more cores is faster than this and a
    # laptop on battery is slower, which is what RANGE below is for.
    (r"x86_64|amd64|intel|amd ", 0.20, "een gewone pc op de processor"),
)

RANGE = 1.6  # how wide to say it when the number is not from this machine


def processor() -> str:
    """What this machine calls its processor, as far as Python can tell."""
    return (platform.processor() or platform.machine() or "").strip()


def load() -> dict:
    try:
        said = json.loads(KEPT.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return said if isinstance(said, dict) else {}


def remember(audio_seconds: float, wall_seconds: float, engine: str, model: str) -> None:
    """Write down one real run. Never a reason for anything to fail.

    Only whole services count. Writing out a twenty-second clip is mostly the model loading,
    and averaging that in would tell a church its service takes four hours.
    """
    if audio_seconds < TOO_SHORT or wall_seconds <= 0:
        return
    said = load()
    here = said.get("runs")
    runs = here if isinstance(here, list) else []
    runs.append({"audio": round(audio_seconds, 1), "wall": round(wall_seconds, 1),
                 "engine": engine, "model": model})
    said["runs"] = runs[-REMEMBER:]
    said["processor"] = processor()
    try:
        write_atomic(KEPT, json.dumps(said, indent=2, ensure_ascii=False))
    except OSError:
        pass  # a read-only folder costs an estimate, not a transcription


def from_runs(model: str, engine: str) -> Rate | None:
    """What this machine has really done, when it has done enough to say."""
    runs = [r for r in load().get("runs", [])
            if isinstance(r, dict) and r.get("model") == model and r.get("engine") == engine
            and isinstance(r.get("audio"), (int, float)) and isinstance(r.get("wall"), (int, float))
            and r["audio"] >= TOO_SHORT and r["wall"] > 0]
    if not runs:
        return None
    # The median, not the mean: one run that was interrupted and resumed, or one that shared
    # the machine with a video call, should not move the number a church is shown.
    per = statistics.median(r["wall"] / r["audio"] for r in runs)
    return Rate(per_second=per, runs=len(runs), engine=engine, model=model)


def from_table(engine: str, model: str) -> Rate | None:
    """A machine somebody measured that looks like this one."""
    name = processor().lower()
    if not name:
        return None
    from .transcription import MLX

    for pattern, per, _said in MEASURED:
        if not re.search(pattern, name):
            continue
        wants_gpu = "mlx" in _said
        if wants_gpu is (engine == MLX):
            return Rate(per_second=per, runs=0, engine=engine, model=model, measured_here=False)
    return None


def known(engine: str, model: str) -> Rate | None:
    return from_runs(model, engine) or from_table(engine, model)


def as_minutes(minutes: float) -> str:
    """"ruim een uur", "25 minuten" — the way somebody would say it to you."""
    if minutes < 1:
        return "nog geen minuut"
    if minutes < 90:
        return f"{round(minutes)} minuten"
    hours = minutes / 60
    return f"ongeveer {hours:.1f} uur".replace(".", ",")


def sentence(engine: str, model: str) -> str:
    """What the readiness panel says about this machine, or nothing when it cannot say."""
    rate = known(engine, model)
    if rate is None:
        return ("Hoe lang uitschrijven op deze computer duurt, weet de app pas na de eerste "
                "dienst. Reken op een half uur tot twee uur voor anderhalf uur dienst.")
    took = rate.minutes_for()
    if rate.measured_here:
        seen = "gemeten op deze computer" if rate.runs == 1 else \
            f"gemeten over {rate.runs} diensten op deze computer"
        return f"Een dienst van anderhalf uur duurt {as_minutes(took)} ({seen})."
    return (f"Een dienst van anderhalf uur duurt naar verwachting {as_minutes(took / RANGE)} "
            f"tot {as_minutes(took * RANGE)}. Na de eerste dienst weet de app het precies.")
