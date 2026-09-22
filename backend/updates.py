"""Is there a newer one, and what changed in it.

A church that installed this once will otherwise run that version until somebody visits.
So the launcher asks GitHub, once, on start, and says in the black window what is there
and where to get it.

What this deliberately is not: an update that installs itself. A church rebuilding
unattended at ten to ten on a Sunday morning is a worse outcome than a church running last
month's version, and the person who would have to fix it is not in the building.

Failing is the ordinary case, not the exception. No internet, GitHub down, a proxy in the
way, a rate limit: all of those mean the app starts without saying anything about updates.
"""

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass

from . import version

RELEASES = "https://api.github.com/repos/M-Kersten/Preekstof/releases/latest"
TIMEOUT = 6.0  # a start that waits on GitHub is a start nobody trusts
NUMBER = re.compile(r"(\d+)\.(\d+)\.(\d+)")


@dataclass
class Release:
    version: str
    url: str
    notes: str = ""

    def headline(self) -> str:
        """The first thing worth reading out of the release notes, if there is one.

        Headings are skipped. "## Wat er verandert" is what every set of notes starts
        with and it tells a volunteer nothing; the line under it is the one to show.
        """
        for line in self.notes.splitlines():
            said = line.strip()
            if not said or said.startswith(("#", "<", "---", "===")):
                continue
            said = said.lstrip("*-·+ ").strip()
            if said:
                return said[:160]
        return ""


def as_numbers(said: str) -> tuple[int, int, int] | None:
    found = NUMBER.search(said or "")
    return (int(found.group(1)), int(found.group(2)), int(found.group(3))) if found else None


def newer(there: str, here: str = version.VERSION) -> bool:
    """Is `there` a later version than `here`? An unreadable number is never newer."""
    theirs, ours = as_numbers(there), as_numbers(here)
    return bool(theirs and ours and theirs > ours)


def latest(url: str = RELEASES, timeout: float = TIMEOUT) -> Release | None:
    """What GitHub says the newest release is, or nothing at all."""
    try:
        request = urllib.request.Request(url, headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": f"Preekstof/{version.VERSION}",
        })
        with urllib.request.urlopen(request, timeout=timeout) as answer:
            said = json.loads(answer.read(1_000_000).decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError, json.JSONDecodeError):
        return None
    tag = said.get("tag_name") or said.get("name") or ""
    if not isinstance(tag, str) or not as_numbers(tag):
        return None
    where = said.get("html_url")
    return Release(
        version=tag.lstrip("vV"),
        url=where if isinstance(where, str) and where.startswith("https://") else
            "https://github.com/M-Kersten/Preekstof/releases/latest",
        notes=said.get("body") if isinstance(said.get("body"), str) else "",
    )


def note() -> str:
    """What to say in the black window, or nothing when there is nothing to say."""
    there = latest()
    if there is None or not newer(there.version):
        return ""
    said = [f"Er is een nieuwere versie: {there.version} (je draait {version.VERSION})."]
    headline = there.headline()
    if headline:
        said.append(f"Wat er verandert: {headline}")
    said.append(f"Ophalen: {there.url}")
    said.append("De app draait gewoon door; bijwerken doe je wanneer het jou uitkomt.")
    return "\n".join(said)
