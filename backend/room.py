"""Whether this will fit, asked before the first byte rather than at eighty percent.

A render that fills the disk halfway through is the worst failure this app has. It costs
the work already done, it leaves a half-written file behind, and worst of all it leaves
nothing free to clean up with: the button that would have made room needs room to run.

The readiness panel already warns under three gigabytes. That is a different question from
whether this particular service will fit, and a church with four gigabytes free and a
two-hour recording gets a green light today.

Every number below was measured rather than guessed, and then given headroom. The point is
not to predict the size of the output. It is to refuse the jobs that obviously cannot end
well, and to say how much short they are.
"""

import shutil
from dataclasses import dataclass
from pathlib import Path

from .models import ROOT

# Measured on a real render: a clip of nine seconds came to 879 kB, and the wav that fed it
# to 278 kB. Rounded up, because a busier picture encodes larger and nobody is helped by an
# estimate that is exactly right on a quiet one.
WAV_PER_SECOND = 40_000
CLIP_PER_SECOND = 250_000

# What a service weighs when nobody can ask first. A link is followed before its size is
# known, and a ninety-minute recording off a church stream runs from one to three gigabytes.
# Taken at the low end on purpose: this is here to stop a hopeless download, not to refuse
# a machine that would have managed.
SERVICE_GUESS = 1_500_000_000

# What must stay free whatever happens. Windows starts behaving strangely well before zero,
# and a machine with nothing left cannot even write the log that says so.
FLOOR = 1_000_000_000


class NotEnoughRoom(RuntimeError):
    """The job was refused before it started, with the numbers in the message."""


@dataclass
class Need:
    """What a job wants, and what is there."""

    wants: int
    free: int

    @property
    def enough(self) -> bool:
        return self.free - self.wants >= FLOOR

    @property
    def short(self) -> int:
        return max(0, self.wants + FLOOR - self.free)


def free_bytes(where: Path = ROOT) -> int:
    try:
        return shutil.disk_usage(where).free
    except OSError:
        return 0


def gb(size: float) -> str:
    """Bytes as somebody would say them, and never "0.0 GB" for something real."""
    if size >= 1e9:
        return f"{size / 1e9:.1f} GB".replace(".", ",")
    return f"{max(1, round(size / 1e6))} MB"


def for_transcribing(seconds: float) -> int:
    """The audio comes out of the recording as a wav before anything listens to it."""
    return int(max(0.0, seconds) * WAV_PER_SECOND)


def for_clips(seconds: float, count: int = 1) -> int:
    """Each clip is written out, and its own audio sits beside it while that happens."""
    each = max(0.0, seconds) * (CLIP_PER_SECOND + WAV_PER_SECOND)
    return int(each * max(1, count))


def recoverable() -> int:
    """What is standing by to be thrown away, so the message can point at it."""
    try:
        from . import storage

        return int(storage.survey()["usedMb"] * 1e6)
    except Exception:  # noqa: BLE001  a number we could not get is not a reason to refuse
        return 0


def check(wants: int, doing: str, where: Path = ROOT) -> Need:
    """Raise unless `wants` bytes can be written without going under the floor.

    `doing` goes into the message as the thing that will not fit, so a volunteer reads what
    they were trying to do rather than a number without a noun.
    """
    need = Need(wants=int(wants), free=free_bytes(where))
    if need.enough:
        return need
    said = [f"{doing} heeft ongeveer {gb(need.wants)} nodig en er is {gb(need.free)} vrij."]
    waiting = recoverable()
    if waiting >= 500_000_000:
        said.append(f"Onder Ruimte vrijmaken staat {gb(waiting)} aan opnames en werkbestanden "
                    "klaar om weg te gooien.")
    else:
        said.append("Maak ruimte vrij op deze computer en probeer het opnieuw.")
    # Said last because it is the number somebody types into a mail: how much short.
    said.append(f"Er is {gb(need.short)} te weinig.")
    raise NotEnoughRoom(" ".join(said))
