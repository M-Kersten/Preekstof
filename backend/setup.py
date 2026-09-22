"""The first five minutes: what a church fills in before the app can do anything.

Until now the API key went into config.env with Notepad and the church details were behind a
menu nobody knew to open. That is the wall most willing churches would fail at, and they
would fail at it quietly: nobody hears about the volunteer who closed the window again.

So the app asks. This module holds what it needs to know to decide whether it still has to,
writes the answers where the rest of the app already looks for them, and remembers that the
question has been dealt with.

Two things are deliberate. The key is written to config.env *and* put into the running
process, so it works without restarting. And it is never read back out over the API: the
interface is told whether there is one, never which.
"""

import os
import re
from pathlib import Path

from pydantic import BaseModel

from . import brands, discovery
from .models import ROOT, TEMPLATES_DIR, write_atomic

CONFIG = ROOT / "config.env"
STATE = TEMPLATES_DIR / "setup.json"

# A church that does not publish on kerkdienstgemist uploads its files by hand, which is a
# perfectly ordinary way to use this. Saying so once is the difference between a setting
# left empty and a step somebody is stuck on.
class Setup(BaseModel):
    done: bool = False  # the volunteer walked through the steps, whatever they filled in
    skippedStation: bool = False


class SetupState(BaseModel):
    """What the interface needs to decide whether to show the welcome or the app."""

    done: bool
    version: str
    provider: str
    hasKey: bool
    churchName: str
    station: str
    skippedStation: bool


def load() -> Setup:
    if not STATE.is_file():
        return Setup()
    try:
        return Setup.model_validate_json(STATE.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001  a damaged file means the welcome shows again, which is safe
        return Setup()


def save(setup: Setup) -> Setup:
    STATE.parent.mkdir(parents=True, exist_ok=True)
    write_atomic(STATE, setup.model_dump_json(indent=2))
    return setup


def has_key() -> bool:
    """Is there something to talk to? Ollama runs on this machine and needs no key at all."""
    if discovery.LLM_PROVIDER == "ollama":
        return True
    return bool(os.environ.get("ANTHROPIC_API_KEY") or os.environ.get("ANTHROPIC_AUTH_TOKEN"))


def state() -> SetupState:
    from .version import full

    church = brands.active().church
    setup = load()
    return SetupState(
        done=setup.done, version=full(), provider=discovery.LLM_PROVIDER, hasKey=has_key(),
        churchName=church.churchName.strip(), station=church.kerkdienstgemistStation.strip(),
        skippedStation=setup.skippedStation,
    )


# The name a brand carries before anybody has answered. It is the value the app ships
# with, so it means "nobody has filled this in", not "this church is called that". Without
# this, a fresh install would count as answered and put Example Church on the end screen of
# every clip the church posts.
UNANSWERED = "example church"


def what_is_missing() -> list[str]:
    """The steps still open, in the order the welcome asks them. Empty means ready."""
    now = state()
    missing = []
    if not now.hasKey:
        missing.append("key")
    if not now.churchName or now.churchName.lower() == UNANSWERED:
        missing.append("church")
    if not now.station and not now.skippedStation:
        missing.append("station")
    return missing


# --- the key --------------------------------------------------------------------------

# Anthropic's keys start like this. Checked only to catch the obvious paste of the wrong
# thing; the real answer comes from asking the API, which is what the welcome does next.
KEY_SHAPE = re.compile(r"^sk-ant-[A-Za-z0-9_\-]{20,}$")
KEY_LINE = re.compile(r"^\s*ANTHROPIC_API_KEY\s*=.*$", re.MULTILINE)


def looks_like_a_key(key: str) -> bool:
    return bool(KEY_SHAPE.match(key.strip()))


def remember_key(key: str) -> None:
    """Write the key into config.env and into this process, so it works straight away.

    Everything else in config.env is left exactly as it was, comments and all: a church that
    has been tuning settings should not lose them to the welcome screen.
    """
    key = key.strip()
    if not key or "\n" in key or "\r" in key:
        raise ValueError("Dat is geen sleutel.")
    line = f"ANTHROPIC_API_KEY={key}"
    if CONFIG.is_file():
        text = CONFIG.read_text(encoding="utf-8")
        updated = KEY_LINE.sub(line, text) if KEY_LINE.search(text) else \
            text.rstrip("\n") + f"\n\n# Ingevuld via het welkomstscherm.\n{line}\n"
    else:
        updated = f"# Preekstof settings.\n{line}\n"
    write_atomic(CONFIG, updated)
    # The app reads this at the moment it calls the API, so it takes effect without a restart.
    os.environ["ANTHROPIC_API_KEY"] = key


def forget_key() -> None:
    """Take the key back out of config.env and out of this process."""
    if CONFIG.is_file():
        text = CONFIG.read_text(encoding="utf-8")
        write_atomic(CONFIG, KEY_LINE.sub("ANTHROPIC_API_KEY=", text))
    os.environ.pop("ANTHROPIC_API_KEY", None)


# --- the church ------------------------------------------------------------------------

def remember_church(name: str | None = None, station: str | None = None,
                    times: list[str] | None = None, instagram: str | None = None) -> None:
    """Put what the welcome asked into the active brand, where the rest of the app reads it."""
    brand = brands.active()
    if name is not None:
        brand.church.churchName = name.strip()
    if station is not None:
        brand.church.kerkdienstgemistStation = station.strip()
    if times is not None:
        brand.church.serviceTimes = [t.strip() for t in times if t.strip()]
    if instagram is not None:
        brand.church.instagram = instagram.strip()
    brands.save(brand)


def finish(skipped_station: bool | None = None) -> Setup:
    setup = load()
    setup.done = True
    if skipped_station is not None:
        setup.skippedStation = skipped_station
    return save(setup)


def reopen() -> Setup:
    """Show the welcome again. The church details already filled in are left alone."""
    return save(Setup(done=False, skippedStation=load().skippedStation))
