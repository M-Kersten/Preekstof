"""What each run really took, written down as it happens.

At the end of a pilot the difference between "het werkte wel aardig" and something you can
act on is four numbers per church. Nobody reconstructs those afterwards from memory, and the
app is the only thing in the room that knows them, so it writes them down while it works.

One line of JSON per event in `logs/runs.jsonl`, appended and never rewritten. It survives
the log rotation next to it on purpose: the log is for the failure you are being told about
this week, this is for the question you will ask in March.

What is in a line: what happened, when, which service, and the numbers belonging to that
kind of event. What is not in a line: a word of anybody's transcript, a title, a church
name, a preacher. The whole file can be mailed without anybody reading it first, which is
the only way it will ever actually be mailed.
"""

import json
from datetime import datetime, timezone
from pathlib import Path

from .models import ROOT

KEPT = ROOT / "logs" / "runs.jsonl"
MAX_BYTES = 4 * 1024 * 1024  # a line is ~200 bytes; this is years of Sundays


def note(what: str, **numbers) -> None:
    """Write one event down. Never a reason for the work it describes to fail."""
    line = {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"), "what": what}
    for name, value in numbers.items():
        if isinstance(value, float):
            value = round(value, 3)
        line[name] = value
    try:
        KEPT.parent.mkdir(parents=True, exist_ok=True)
        if KEPT.is_file() and KEPT.stat().st_size > MAX_BYTES:
            return
        with KEPT.open("a", encoding="utf-8") as out:
            out.write(json.dumps(line, ensure_ascii=False) + "\n")
    except (OSError, TypeError, ValueError):
        pass


def read(path: Path = KEPT) -> list[dict]:
    """Every event, oldest first. A damaged line is skipped rather than fatal."""
    try:
        lines = path.read_text(encoding="utf-8").splitlines()
    except OSError:
        return []
    out = []
    for line in lines:
        try:
            said = json.loads(line)
        except ValueError:
            continue
        if isinstance(said, dict) and said.get("what"):
            out.append(said)
    return out
