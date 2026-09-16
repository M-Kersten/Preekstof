"""Reading a setting out of config.env without letting a typo take the app down.

config.env is edited by hand, in Notepad, by someone who is not a programmer, and people
write notes to themselves behind a value:

    LLM_EFFORT=medium   # of high als de momenten tegenvallen

The launcher used to hand that whole line over as the value. For a word that goes straight
to the API it came back as a 400 that named a setting nobody recognised; for a number it
was worse, because int() raised while the module was still being imported and the app did
not start at all.

So a value is read here: the note behind it is dropped, and anything that still makes no
sense falls back to what the app shipped with and says so in the black window. A setting
somebody mistyped is worth a line of complaint. It is not worth a Sunday.
"""

import os

# A note behind a value starts at a # with a space in front of it. Without that rule a
# password or a key with a # in it would quietly lose its tail.
COMMENT = (" #", "\t#")


def clean(raw: str) -> str:
    """One value as it was meant, without the note behind it or the quotes around it."""
    value = raw
    for mark in COMMENT:
        value = value.split(mark)[0]
    return value.strip().strip('"').strip("'").strip()


def complain(name: str, given: str, using, why: str) -> None:
    print(f"[instellingen] {name}={given!r} {why}. Er wordt {using!r} gebruikt. "
          f"Pas het aan in config.env en start opnieuw.", flush=True)


def text(name: str, fallback: str = "") -> str:
    """A setting that is a word or a sentence. Empty falls back."""
    raw = os.environ.get(name)
    return clean(raw) or fallback if raw is not None else fallback


def choice(name: str, allowed: tuple[str, ...], fallback: str) -> str:
    """A setting that may only be one of a handful of words."""
    value = text(name, fallback).lower()
    if value in allowed:
        return value
    complain(name, value, fallback, f"kan alleen {', '.join(allowed)} zijn")
    return fallback


def number(name: str, fallback: float, least: float | None = None) -> float:
    value = text(name, "")
    if not value:
        return fallback
    try:
        found = float(value.replace(",", "."))  # a Dutch keyboard writes 0,86
    except ValueError:
        complain(name, value, fallback, "is geen getal")
        return fallback
    if least is not None and found < least:
        complain(name, value, fallback, f"moet minstens {least} zijn")
        return fallback
    return found


def whole(name: str, fallback: int, least: int | None = None) -> int:
    """A setting that counts something, so a half of one is a mistake."""
    found = number(name, float(fallback), None if least is None else float(least))
    return int(found)
