"""Where the app lives, and where a church's own work is kept. Two different places.

Everything a church makes used to sit inside the app folder: recordings, clips, the brand,
logos, the word list, the key. Updating meant unpacking a new folder somewhere and finding
all of it gone, or unpacking over the old one and hoping. So the app folder now holds only
what comes with a download, and the church's work lives in a folder of its own that an
update never touches: ~/Preekstof, which is C:\\Users\\<naam>\\Preekstof on Windows.

Not Documents: on many church laptops OneDrive or iCloud syncs that folder, and a service
recording is two gigabytes. PREEKSTOF_DATA puts it elsewhere.

Moving the old contents across happens once, when the launcher starts (move_in). Nothing
here moves anything on import: the tests point PREEKSTOF_DATA at a temporary folder, and a
developer's checkout must not be emptied into it.
"""

import os
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent  # the app: code, fonts, the music library


def data_home() -> Path:
    chosen = os.environ.get("PREEKSTOF_DATA", "").strip()
    return Path(chosen).expanduser() if chosen else Path.home() / "Preekstof"


DATA = data_home()
OWN_TEMPLATES = DATA / "templates"  # the church's own: brands, logos, music, end screen, word list
LOGS = DATA / "logs"
CONFIG = DATA / "config.env"

# What used to be in the app folder and belongs to the church. Folders are merged entry by
# entry, so a half-finished earlier move simply carries on.
TOP = ("config.env", "projects", "services", "logs")
IN_TEMPLATES = ("brands", "church.json", "outro.json", "outro.mp4", "outro.4x5.mp4", "outro.1x1.mp4",
                "speed.json", "woordenlijst.json", "verbeteringen.json", "setup.json")
SHARED_FOLDERS = ("logos", "music")
PATTERNS = ("outro-achtergrond.*",)


def ensure() -> None:
    OWN_TEMPLATES.mkdir(parents=True, exist_ok=True)


KEEP = frozenset({".gitkeep"})  # ships with the app, so it stays with the app


def merge(source: Path, target: Path, keep: frozenset[str] = KEEP) -> list[str]:
    """Move `source` to `target`; a folder goes entry by entry, and nothing is overwritten."""
    if not source.exists() and not source.is_symlink():
        return []
    if source.is_dir() and not source.is_symlink():
        moved: list[str] = []
        target.mkdir(parents=True, exist_ok=True)
        for entry in sorted(source.iterdir()):
            if entry.name in keep:
                continue
            moved += merge(entry, target / entry.name)
        try:
            if not any(source.iterdir()):
                source.rmdir()
        except OSError:
            pass
        return moved
    if target.exists():
        return []  # already there: the one in the new place wins, the old one stays put
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(source), str(target))
    return [str(target)]


def move_in(app: Path = ROOT, data: Path | None = None) -> list[str]:
    """Bring a church's work out of the app folder into the data folder. Returns what moved."""
    data = data or DATA
    if app.resolve() == data.resolve():
        return []
    moved: list[str] = []
    for name in TOP:
        moved += merge(app / name, data / name)
    old, new = app / "templates", data / "templates"
    for name in IN_TEMPLATES:
        moved += merge(old / name, new / name)
    for name in SHARED_FOLDERS:
        moved += merge(old / name, new / name)
    for pattern in PATTERNS:
        for found in sorted(old.glob(pattern)):
            moved += merge(found, new / found.name)
    return moved
