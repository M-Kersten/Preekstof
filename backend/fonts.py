"""Which fonts are available, read from the files in templates/fonts.

Files follow {Stem}-{Weight}.ttf, and the family name inside the file is
"Family" for Regular and Bold and "Family Weight" for the rest. Drop another
pair of files in that folder and the font appears in the app.
"""

import re
import struct
from functools import lru_cache
from pathlib import Path

from pydantic import BaseModel

from .models import FONTS_DIR

WEIGHTS = ["regular", "medium", "semibold", "bold", "extrabold"]
FILE_WEIGHT = {"regular": "Regular", "medium": "Medium", "semibold": "SemiBold", "bold": "Bold", "extrabold": "ExtraBold"}
SYSTEM_FONT = "Arial"  # always offered; comes from the operating system
ARIAL_BOX = (1854 + 434) / 2048  # Arial's usWinAscent and usWinDescent; Liberation Sans has the same


class FontFamily(BaseModel):
    name: str  # "Open Sans"
    stem: str  # "OpenSans", the file name prefix
    weights: list[str]
    box: float = 1.0  # see line_box()


@lru_cache(maxsize=256)
def _line_box(path: Path, stamp: float) -> float:
    try:
        data = path.read_bytes()
        tables = {}
        for i in range(struct.unpack_from(">H", data, 4)[0]):
            tag, _, offset, _ = struct.unpack_from(">4sIII", data, 12 + 16 * i)
            tables[tag] = offset
        em = struct.unpack_from(">H", data, tables[b"head"] + 18)[0]
        top, bottom = struct.unpack_from(">hh", data, tables[b"OS/2"] + 74)
        if top + bottom == 0:  # libass then falls back on hhea, as FreeType does
            top, low = struct.unpack_from(">hh", data, tables[b"hhea"] + 4)
            bottom = -low
    except (OSError, KeyError, struct.error):
        return 1.0
    return round((top + bottom) / em, 4) if em and top + bottom > 0 else 1.0


def line_box(path: Path) -> float:
    """How tall libass draws a line of this font, against the letter size a browser uses.

    A browser asked for 92 pixels makes one em 92 pixels: the size of the letters. libass,
    which copies the old Windows renderer, makes the whole line box 92 pixels, from
    usWinAscent down to usWinDescent, so the same number gives smaller letters. In Poppins a
    little over half the size. Multiplying a size by this number before handing it to libass
    gives the letters the preview shows.
    """
    try:
        stamp = path.stat().st_mtime
    except OSError:
        return 1.0
    return _line_box(path, stamp)


_cache: tuple[float, list[FontFamily]] | None = None


def _display_name(stem: str) -> str:
    return re.sub(r"(?<=[a-z])(?=[A-Z])", " ", stem)


def catalogue() -> list[FontFamily]:
    """Families in templates/fonts, refreshed when the folder changes."""
    global _cache
    directory = Path(FONTS_DIR)
    stamp = directory.stat().st_mtime if directory.is_dir() else 0.0
    if _cache and _cache[0] == stamp:
        return _cache[1]

    found: dict[str, list[str]] = {}
    for path in sorted(directory.glob("*.ttf")):
        stem, _, weight = path.stem.rpartition("-")
        if not stem or weight not in FILE_WEIGHT.values():
            continue
        name = next(w for w, f in FILE_WEIGHT.items() if f == weight)
        found.setdefault(stem, []).append(name)

    # The weights of one family share their metrics, so the first file speaks for all of them.
    families = [FontFamily(name=_display_name(stem), stem=stem, weights=[w for w in WEIGHTS if w in weights],
                           box=line_box(directory / f"{stem}-{FILE_WEIGHT[weights[0]]}.ttf"))
                for stem, weights in sorted(found.items(), key=lambda kv: _display_name(kv[0]))]
    families.append(FontFamily(name=SYSTEM_FONT, stem="", weights=WEIGHTS, box=round(ARIAL_BOX, 4)))
    _cache = (stamp, families)
    return families


def names() -> list[str]:
    return [f.name for f in catalogue()]


def box_of(font: str) -> float:
    """line_box() of a family by its name. A family that is not there counts as 1."""
    return next((f.box for f in catalogue() if f.name == font), 1.0)


def resolve_weight(font: str, weight: str) -> str:
    """The closest weight this family actually has (prefer heavier, then lighter)."""
    family = next((f for f in catalogue() if f.name == font), None)
    if family is None or weight in family.weights:
        return weight
    order = WEIGHTS[WEIGHTS.index(weight):] + WEIGHTS[: WEIGHTS.index(weight)][::-1]
    return next((w for w in order if w in family.weights), "regular")
