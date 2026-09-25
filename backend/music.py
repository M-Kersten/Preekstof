"""Background music: the library that ships with the app, and what a church adds itself.

Two folders, kept apart on purpose. templates/library/music is part of the repository and of
every release, so a church that has never uploaded anything still has music to choose from.
templates/music holds what a church uploads itself; git ignores it, so an update never
overwrites or deletes a church's own tracks, and a church's tracks never end up in the
repository.

A clip remembers its music by file name only, the way it always did. A name is looked up in
the church's own folder first and in the library after that; an upload may not take a name the
library already uses, so the two never have to be told apart by anything else.

templates/library/music/tracks.json gives the library its titles and credits. A file that is
not listed there still shows, under its file name. Music under a Creative Commons licence
usually asks for a credit, and the credit written there is shown next to the track.
"""

import json
from pathlib import Path
from urllib.parse import quote

from pydantic import BaseModel

from .models import TEMPLATES_DIR

OWN_DIR = TEMPLATES_DIR / "music"
LIBRARY_DIR = TEMPLATES_DIR / "library" / "music"
ALLOWED = {".mp3", ".m4a", ".wav", ".aac", ".ogg"}


class Track(BaseModel):
    file: str
    title: str
    credit: str = ""  # who made it, as the licence asks for it to be named
    library: bool  # shipped with the app, rather than uploaded by this church
    sizeMb: float
    url: str  # where the browser can play it


def title_of(file: str) -> str:
    """"rustige_piano-01.mp3" reads as "rustige piano 01"."""
    plain = Path(file).stem.replace("_", " ").replace("-", " ")
    return " ".join(plain.split()) or file


def catalogue() -> dict[str, dict]:
    """What tracks.json says about each library file, keyed on the file name."""
    try:
        said = json.loads((LIBRARY_DIR / "tracks.json").read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    rows = said.get("tracks", []) if isinstance(said, dict) else []
    return {row["file"]: row for row in rows if isinstance(row, dict) and row.get("file")}


def files_in(folder: Path) -> list[Path]:
    if not folder.is_dir():
        return []
    return [p for p in folder.iterdir() if p.is_file() and p.suffix.lower() in ALLOWED]


def library() -> list[Track]:
    """The shipped tracks, in the order tracks.json lists them, the rest after by name."""
    known = catalogue()
    order = {name: n for n, name in enumerate(known)}
    found = sorted(files_in(LIBRARY_DIR), key=lambda p: (order.get(p.name, len(order)), p.name.lower()))
    return [Track(file=p.name, title=str(known.get(p.name, {}).get("title") or title_of(p.name)),
                  credit=str(known.get(p.name, {}).get("credit") or ""), library=True,
                  sizeMb=round(p.stat().st_size / 1e6, 1), url=f"/templates/library/music/{quote(p.name)}")
            for p in found]


def own() -> list[Track]:
    return [Track(file=p.name, title=title_of(p.name), library=False,
                  sizeMb=round(p.stat().st_size / 1e6, 1), url=f"/templates/music/{quote(p.name)}")
            for p in sorted(files_in(OWN_DIR), key=lambda p: p.name.lower())]


def everything() -> list[Track]:
    return library() + own()


def path_for(name: str) -> Path | None:
    """The file behind a name a clip or brand remembers, wherever it lives, or None."""
    if not name:
        return None
    plain = Path(name).name
    for folder in (OWN_DIR, LIBRARY_DIR):
        path = folder / plain
        if path.is_file():
            return path
    return None


def in_library(name: str) -> bool:
    return (LIBRARY_DIR / Path(name).name).is_file()
