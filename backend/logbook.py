"""Everything the black window says, kept in a file somebody can send you.

Until now a failure ended in `print()` to a console window the volunteer closes, and the
only report you ever got was "het werkte niet". So the window keeps its output, and the
same lines go to `logs/preekstof.log` on the way past.

Two deliberate limits. One file per run, and the previous few runs kept beside it, because
the failure you are being told about happened either this run or the one before. And a
ceiling on the size, because a service that loops for an hour must not be able to fill the
disk it is supposed to be writing a recording to.

Nothing here sends anything anywhere. Writing the file is all it does; `diagnose.py` is
what turns it into something to attach to a mail, and only when a person asks.
"""

import re
import sys
import threading
from datetime import datetime
from pathlib import Path
from typing import TextIO

from .models import ROOT

LOGS = ROOT / "logs"
CURRENT = LOGS / "preekstof.log"
KEEP_RUNS = 5  # this run and the four before it
MAX_BYTES = 8 * 1024 * 1024

# What must never reach the file, let alone the zip. The key is the one secret this app
# holds, and it turns up in a config dump, in an error from the SDK, and in a stack trace.
SECRETS = (
    re.compile(r"sk-ant-[A-Za-z0-9_\-]{6,}"),
    re.compile(r"(?i)\b(ANTHROPIC_API_KEY|ANTHROPIC_AUTH_TOKEN|API[_-]?KEY)\s*[:=]\s*\S+"),
    re.compile(r"(?i)\b(authorization|x-api-key)\s*:\s*\S+"),
)


def without_secrets(text: str) -> str:
    """The same text with anything that looks like a key struck out.

    Deliberately blunt. A pattern that strikes out one line too many costs a support mail
    a little context; one that misses costs a church its key.
    """
    for pattern in SECRETS:
        text = pattern.sub(lambda m: m.group(0)[:0] + "«weggelaten»"
                           if m.group(0).startswith("sk-ant-")
                           else m.group(0).split("=")[0].split(":")[0] + ": «weggelaten»", text)
    return text


# A progress bar writes "  41%\r  42%\r" with no newline for minutes on end. Held back
# until a line is finished, only the last state of it is ever written down.
MAX_PENDING = 4096


class Tee:
    """Writes to the console and to the file, and never lets the file break the console.

    A full disk, a folder that turned read-only, a file somebody has open in Notepad: all
    of those must leave the app running. The window is what the user is looking at, so it
    is written first and the file is best effort.

    Whole lines, not whatever came in one call. `print("a", "b")` reaches a stream in four
    pieces and a download counter reaches it in hundreds, and a log with one timestamp per
    piece is not a log anybody can read.
    """

    def __init__(self, console: TextIO, log: Path):
        self.console = console
        self.path = log
        self.lock = threading.Lock()
        self.written = 0
        self.stopped = False
        self.full = False
        self.pending = ""

    def write(self, text: str) -> int:
        count = self.console.write(text)
        with self.lock:
            if not self.stopped:
                self._keep(text)
        return count

    def _keep(self, text: str) -> None:
        self.pending += text
        *lines, self.pending = self.pending.split("\n")
        if len(self.pending) > MAX_PENDING:  # a line that never ends is still worth having
            lines.append(self.pending)
            self.pending = ""
        said = [without_secrets(line.rsplit("\r", 1)[-1].rstrip()) for line in lines]
        self._write([line for line in said if line.strip()])

    def _write(self, lines: list[str]) -> None:
        if not lines:
            return
        if self.written >= MAX_BYTES:
            if not self.full:
                self.full = True
                self._append("[Preekstof] Het logboek is vol; de rest van deze keer wordt "
                             "niet meer opgeschreven.\n")
            return
        stamp = datetime.now().strftime("%H:%M:%S")
        block = "".join(f"{stamp} {line}\n" for line in lines)
        self._append(block)
        self.written += len(block)

    def _append(self, line: str) -> None:
        try:
            with self.path.open("a", encoding="utf-8", errors="replace") as out:
                out.write(line)
        except OSError:
            self.stopped = True  # the console keeps working; the file has given up

    def flush(self) -> None:
        self.console.flush()
        with self.lock:
            if self.pending.strip() and not self.stopped:
                self._write([without_secrets(self.pending.rsplit("\r", 1)[-1].rstrip())])
                self.pending = ""

    def isatty(self) -> bool:
        return getattr(self.console, "isatty", lambda: False)()

    def fileno(self) -> int:
        return self.console.fileno()


def older_runs() -> list[Path]:
    """The kept logs of earlier runs, newest first."""
    return sorted(LOGS.glob("preekstof-*.log"), reverse=True)


def rotate() -> None:
    """Put this run's log aside under its date, and drop the ones nobody will ask about."""
    if CURRENT.is_file() and CURRENT.stat().st_size:
        when = datetime.fromtimestamp(CURRENT.stat().st_mtime).strftime("%Y%m%d-%H%M%S")
        CURRENT.replace(LOGS / f"preekstof-{when}.log")
    for spent in older_runs()[KEEP_RUNS - 1:]:
        spent.unlink(missing_ok=True)


def begin() -> Path | None:
    """Start keeping this run. Returns the file, or nothing when it could not be opened."""
    try:
        LOGS.mkdir(parents=True, exist_ok=True)
        rotate()
        CURRENT.write_text("", encoding="utf-8")
    except OSError:
        return None  # a read-only folder is not a reason to refuse to start
    sys.stdout = Tee(sys.stdout, CURRENT)
    sys.stderr = Tee(sys.stderr, CURRENT)
    return CURRENT


def tail(lines: int = 400) -> str:
    """The last of what was said, this run and the run before it if this one is short."""
    said: list[str] = []
    for path in [CURRENT, *older_runs()]:
        try:
            said = path.read_text(encoding="utf-8", errors="replace").splitlines() + said
        except OSError:
            continue
        if len(said) >= lines:
            break
    return "\n".join(said[-lines:])
