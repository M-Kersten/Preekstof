"""The shapes a clip goes out in.

A clip is made for a phone held upright. Reels, Shorts, TikTok and a WhatsApp status all fill
the screen from top to bottom, and that is where it starts. A Facebook timeline does not work
that way: a video that tall is cut off there or shrunk to a strip, and Facebook is where most
of a church's own people are. So the same clip can also be made in 4:5, as tall as a timeline
lets a video be, and square, which fits everywhere else: a website, a newsletter, Facebook on
a computer.

Every shape is the same clip. The words, the framing, the logo, the music and the end screen
all come along. What changes is how much of the church fits beside the speaker, and how far
the captions stay from the bottom edge.

Which shapes were made, and from what, is written down next to them. A shape made before
somebody fixed a name in the captions is the version with the wrong name in it, and the
delivery window has to be able to say so rather than hand it over as if nothing changed.
"""

import hashlib
import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from .models import ROOT, Output, Project, Transcript, project_dir, write_atomic


@dataclass(frozen=True)
class Shape:
    key: str  # what the API and the interface call it
    ratio: str  # how a person writes it
    name: str
    use: str  # where it goes, in the words of somebody posting it
    width: int
    height: int
    file: str  # in the clip's output folder
    tag: str  # added to the name of the download, so three files never end up with one name


UPRIGHT = Shape("9x16", "9:16", "Staand", "Reels, Shorts, TikTok en een WhatsApp-status",
                1080, 1920, "final.mp4", "")
TIMELINE = Shape("4x5", "4:5", "Tijdlijn", "De tijdlijn van Facebook en Instagram",
                 1080, 1350, "final-4x5.mp4", "-4x5")
SQUARE = Shape("1x1", "1:1", "Vierkant", "Facebook op de computer, de website en een nieuwsbrief",
               1080, 1080, "final-1x1.mp4", "-vierkant")

SHAPES = {shape.key: shape for shape in (UPRIGHT, TIMELINE, SQUARE)}
MAIN = UPRIGHT.key


def output_for(shape: Shape, base: Output) -> Output:
    """The frame to render this shape at. Upright keeps the clip's own settings exactly."""
    if shape.key == MAIN:
        return base
    return Output(width=shape.width, height=shape.height, fps=base.fps)


def work_name(shape: Shape, name: str) -> str:
    """A working file of one shape, apart from the same file of the others."""
    if shape.key == MAIN:
        return name
    stem, dot, suffix = name.rpartition(".")
    return f"{stem}-{shape.key}{dot}{suffix}"


def extras(keys: list[str]) -> list[str]:
    """The shapes somebody asked for besides the upright one: known, once each, in order."""
    return [key for key in SHAPES if key != MAIN and key in keys]


def wanted(asked: list[str] | None, always: list[str]) -> list[Shape]:
    """Which shapes one press of a button makes, upright first.

    Asking for nothing in particular is the button under the preview: the upright clip, and
    whatever this church said it wants every time on top of that.
    """
    keys = list(asked) if asked else [MAIN, *extras(always)]
    unknown = [key for key in keys if key not in SHAPES]
    if unknown:
        raise ValueError(f"Onbekend formaat: {', '.join(unknown)}")
    return [shape for key, shape in SHAPES.items() if key in keys]


# --- what was made, and from what ----------------------------------------------

# Everything about a clip that ends up in its picture or its sound. The title is not in
# here, and neither is where the footage happens to live: a clip that gets its own copy
# when the recording is cleaned up is still the same clip.
RECIPE = {"origin", "style", "output", "outro", "music", "watermark", "cropStrategy", "crop", "track"}


def recipe(project: Project, transcript: Transcript, brand) -> str:
    """What this clip would be made from right now, boiled down to one short string.

    Two renders with the same recipe are the same video. A shape made under an older one is
    out of date: somebody fixed a word, moved the frame or changed the end screen after it
    was made, and posting it means posting the version from before the fix.
    """
    said = {
        "clip": project.model_dump(mode="json", include=RECIPE),
        "words": transcript.model_dump(mode="json"),
        "end": brand.outro.model_dump(mode="json"),
        "church": brand.church.model_dump(mode="json",
                                          include={"churchName", "serviceTimes", "instagram"}),
    }
    if not brand.outro.generate:
        # A church that made its own end screen changes it by replacing the file.
        own = ROOT / project.outro
        said["own"] = own.stat().st_mtime if own.is_file() else None
    text = json.dumps(said, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def made_file(project_id: str) -> Path:
    return project_dir(project_id) / "output" / "made.json"


def made(project_id: str) -> dict[str, dict]:
    """Per shape: when it was made and from what. Empty for clips from before this was kept."""
    try:
        records = json.loads(made_file(project_id).read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return records if isinstance(records, dict) else {}


def note_made(project_id: str, shape: Shape, made_from: str) -> None:
    records = made(project_id)
    records[shape.key] = {"at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                          "recipe": made_from}
    target = made_file(project_id)
    target.parent.mkdir(parents=True, exist_ok=True)
    write_atomic(target, json.dumps(records, indent=2))


def overview(project: Project, transcript: Transcript, brand, busy: str | None = None) -> list[dict]:
    """Every shape, and where this clip stands with it."""
    now = recipe(project, transcript, brand)
    records = made(project.id)
    folder = project_dir(project.id) / "output"
    always = set(extras(brand.share.shapes))
    out = []
    for shape in SHAPES.values():
        path = folder / shape.file
        ready = path.is_file() and busy != shape.key
        record = records.get(shape.key) or {}
        out.append({
            "key": shape.key,
            "ratio": shape.ratio,
            "name": shape.name,
            "use": shape.use,
            "width": shape.width,
            "height": shape.height,
            "ready": ready,
            # Nothing on record means it was made before this was kept, and there is no
            # telling. Saying "out of date" about every older clip would be crying wolf.
            "stale": bool(ready and record.get("recipe") and record["recipe"] != now),
            "madeAt": record.get("at") if ready else None,
            "mb": round(path.stat().st_size / 1e6, 1) if ready else None,
            "always": shape.key == MAIN or shape.key in always,
        })
    return out
