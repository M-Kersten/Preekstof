"""The end screen (outro): its look comes from templates/outro.json.

The config holds background, fonts, colours and the text lines; the church name,
service times and Instagram handle come from templates/church.json and are filled
into the text with {churchName}, {serviceTimes} and {instagram}.

The video is rebuilt automatically whenever the config is newer than outro.mp4,
so editing the JSON is enough. Dropping in your own outro.mp4 keeps it: its file
date is then newer than the config and nothing is regenerated.

The layout is drawn and edited on an upright card. A clip made in 4:5 or square gets an end
screen of its own shape, made from the same settings when it is first needed: see Card.
"""

import json
import math
import shutil
import subprocess
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from . import brands, formats
from .models import FONTS_DIR, TEMPLATES_DIR, ChurchInfo, OutroBackground, OutroConfig
from .subtitles import ass_color, family_for

CONFIG_PATH = TEMPLATES_DIR / "outro.json"
CHURCH_PATH = TEMPLATES_DIR / "church.json"
OUTRO_PATH = TEMPLATES_DIR / "outro.mp4"
WIDTH, HEIGHT, FPS = 1080, 1920, 30
MARGIN = 60  # safe space left and right
ZOOM = 1.12  # how far a dolly travels
DRIFT = 1.08  # the fixed crop the upward drift moves within
# The background is drawn larger only when it has to move, so a pixel of rounding in the
# zoom lands well inside one pixel of the finished frame.
SUPER = 3
BIG_W, BIG_H = WIDTH * SUPER, HEIGHT * SUPER

_lock = threading.Lock()

DEFAULT_CONFIG = OutroConfig()


@dataclass(frozen=True)
class Card:
    """An end screen of one size, and where the designed layout lands on it.

    Every position in the config is a place on the upright 1080x1920 card, because that is
    where the end screen is edited. A shorter card cannot hold them where they stand, and
    moving each line in proportion pushes the lines into each other. So the whole block keeps
    its own spacing and moves to the middle, and it is drawn smaller only when it would not
    fit otherwise.
    """

    width: int = WIDTH
    height: int = HEIGHT
    scale: float = 1.0  # how much smaller the block is drawn than it was designed
    middle: float = HEIGHT / 2  # the middle of the block, on the designed card

    def y(self, designed: float) -> float:
        return self.height / 2 + (designed - self.middle) * self.scale

    @property
    def centre(self) -> tuple[float, float]:
        return self.width / 2, self.height / 2


UPRIGHT = Card()
EDGE = 0.07  # kept free above and below the block on a shorter card, as a share of its height
LINE_HEIGHT = 1.25  # how tall a line of text stands, against its font size


def picture_size(path: Path) -> tuple[int, int] | None:
    """Width and height of an image, or None when it cannot be read."""
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height",
             "-of", "csv=p=0:s=x", str(path)], capture_output=True, text=True, timeout=20).stdout
        width, height = (int(n) for n in out.strip().split("x")[:2])
    except (OSError, ValueError, subprocess.SubprocessError):
        return None
    return (width, height) if width > 0 and height > 0 else None


def logo_height(config: OutroConfig) -> float:
    """How tall the logo stands on the designed card. A picture that cannot be read counts as square."""
    try:
        logo = logo_file(config)
    except RuntimeError:
        return 0.0
    if logo is None:
        return 0.0
    size = picture_size(logo)
    return config.logo.width * size[1] / size[0] if size else float(config.logo.width)


def card_for(config: OutroConfig, church: ChurchInfo, width: int = WIDTH, height: int = HEIGHT) -> Card:
    """Where the layout goes on an end screen of this size."""
    if (width, height) == (WIDTH, HEIGHT):
        return UPRIGHT
    top, bottom = float(HEIGHT), 0.0
    for line in config.lines:
        if not fill(line.text, church).strip():
            continue
        half = line.size * LINE_HEIGHT / 2
        top, bottom = min(top, line.y - half), max(bottom, line.y + half)
    logo = logo_height(config)
    if logo:
        top, bottom = min(top, config.logo.y - logo / 2), max(bottom, config.logo.y + logo / 2)
    if bottom <= top:
        return Card(width, height)
    room = height * (1 - 2 * EDGE)
    return Card(width, height, scale=min(1.0, room / (bottom - top)), middle=(top + bottom) / 2)


def file_for(shape: formats.Shape) -> Path:
    """Where the end screen of this shape lives. The upright one keeps the name it always had."""
    if shape.key == formats.MAIN:
        return OUTRO_PATH
    return OUTRO_PATH.with_name(f"outro.{shape.key}.mp4")


def load_config() -> OutroConfig:
    """The end screen of the brand that is active."""
    return brands.active().outro


def save_config(config: OutroConfig) -> None:
    brand = brands.active()
    brand.outro = config
    brands.save(brand)


def save_default_config() -> None:
    brands.migrate()


# --- building -------------------------------------------------------------------


def fill(text: str, church: ChurchInfo) -> str:
    return (text.replace("{churchName}", church.churchName)
                .replace("{serviceTimes}", "  ·  ".join(church.serviceTimes))
                .replace("{instagram}", church.instagram))


def ass_seconds(seconds: float) -> str:
    seconds = max(0.0, seconds)
    return f"{int(seconds // 3600)}:{int(seconds % 3600 // 60):02d}:{seconds % 60:05.2f}"


def zoom_at(motion: str, moment: float, duration: float) -> float:
    """How far the camera has pushed in at `moment`."""
    part = 0.0 if duration <= 0 else max(0.0, min(1.0, moment / duration))
    if motion == "in":
        return 1 + (ZOOM - 1) * part
    if motion == "out":
        return ZOOM - (ZOOM - 1) * part
    if motion == "up":
        return DRIFT
    return 1.0


def drift_at(motion: str, moment: float, duration: float, height: int = HEIGHT) -> float:
    """Vertical offset of the whole card at `moment`, for the upward drift."""
    if motion != "up":
        return 0.0
    part = 0.0 if duration <= 0 else max(0.0, min(1.0, moment / duration))
    # How far the crop window's view travels on screen: the extra height the zoom bought.
    travel = height * (DRIFT - 1)
    return travel * (0.5 - part)


def place(anchor: tuple[float, float], motion: str, moment: float, duration: float,
          card: Card = UPRIGHT) -> tuple[float, float]:
    """Where an anchor point sits once the camera has moved."""
    zoom = zoom_at(motion, moment, duration)
    centre_x, centre_y = card.centre
    x = centre_x + (anchor[0] - centre_x) * zoom
    y = centre_y + (anchor[1] - centre_y) * zoom + drift_at(motion, moment, duration, card.height)
    return x, y


def motion_tags(motion: str, start: float, duration: float, anchor: tuple[float, float],
                card: Card = UPRIGHT) -> str:
    """Move and scale one line the way the camera does.

    libass interpolates positions and scales as floating point, so the text glides
    instead of snapping to whole pixels the way an FFmpeg crop would.
    """
    x0, y0 = place(anchor, motion, start, duration, card)
    if motion == "none":
        return f"\\pos({x0:.2f},{y0:.2f})"
    x1, y1 = place(anchor, motion, duration, duration, card)
    span = max(1, int((duration - start) * 1000))
    begin, end = zoom_at(motion, start, duration), zoom_at(motion, duration, duration)
    tags = f"\\move({x0:.2f},{y0:.2f},{x1:.2f},{y1:.2f},0,{span})\\fscx{begin * 100:.2f}\\fscy{begin * 100:.2f}"
    if abs(end - begin) > 1e-6:
        tags += f"\\t(0,{span},\\fscx{end * 100:.2f}\\fscy{end * 100:.2f})"
    return tags


def build_ass(config: OutroConfig, church: ChurchInfo, card: Card = UPRIGHT) -> str:
    fade_ms = int(config.fade * 1000)
    # While the text scales, the wrap width has to leave room for it, or a line that just
    # fits at rest would suddenly break in two halfway through the move.
    wrap_margin = 0 if config.motion != "none" else MARGIN
    styles, events = [], []
    for i, line in enumerate(config.lines):
        family, bold = family_for(line.font or config.font, line.weight)
        size = line.size if card.scale == 1 else max(1, round(line.size * card.scale))
        spacing = line.spacing if card.scale == 1 else round(line.spacing * card.scale, 2)
        styles.append(
            f"Style: L{i},{family},{size},{ass_color(line.color)},{ass_color(line.color)},"
            f"&H00000000,&H00000000,{-1 if bold else 0},0,0,0,100,100,{spacing},0,1,0,0,5,"
            f"{wrap_margin},{wrap_margin},0,1"
        )
        text = fill(line.text, church).replace("{", "(").replace("}", ")").strip()
        if line.uppercase:
            text = text.upper()
        if not text:
            continue
        align, anchor_x = {"left": (4, MARGIN), "center": (5, card.width // 2),
                           "right": (6, card.width - MARGIN)}[line.align]
        start = min(line.delay, config.duration)
        moves = motion_tags(config.motion, start, config.duration, (anchor_x, card.y(line.y)), card)
        events.append(
            f"Dialogue: 0,{ass_seconds(start)},{ass_seconds(config.duration)},L{i},,0,0,0,,"
            f"{{\\fad({fade_ms},{fade_ms})\\an{align}{moves}}}{text}"
        )
    return "\n".join([
        "[Script Info]", "ScriptType: v4.00+", f"PlayResX: {card.width}", f"PlayResY: {card.height}",
        "WrapStyle: 0", "ScaledBorderAndShadow: yes", "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, "
        "Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, "
        "MarginR, MarginV, Encoding",
        *styles, "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
        *events,
    ]) + "\n"


def motion_filter(motion: str, duration: float, card: Card = UPRIGHT) -> str:
    """Move the background the same way the text moves.

    A gradient or photograph has no fine detail, so the whole-pixel steps an FFmpeg
    crop takes are invisible here; the text, which does have fine detail, is moved by
    libass instead. Both follow the same straight line, so the two layers stay together.
    """
    size = f"{card.width}x{card.height}"
    if motion == "none":
        return f"scale={card.width}:{card.height}"
    frames = max(2, int(duration * FPS))
    centre = "x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
    step = (ZOOM - 1) / frames
    if motion == "in":
        return f"zoompan=z='min(1+{step:.6f}*on,{ZOOM})':d=1:{centre}:s={size}:fps={FPS}"
    if motion == "out":
        return f"zoompan=z='max({ZOOM}-{step:.6f}*on,1.0)':d=1:{centre}:s={size}:fps={FPS}"
    # "up": a fixed slight crop that travels down the card, so the picture rises.
    # The window walks the same 1 - 1/DRIFT of the height that drift_at() moves the text.
    return (f"zoompan=z={DRIFT}:d=1:x='iw/2-(iw/zoom/2)':y='(ih-ih/zoom)*(on/{frames})'"
            f":s={size}:fps={FPS}")


def gradient_source(background: OutroBackground, width: int, height: int) -> str:
    colors = [c for c in background.colors if c.strip()][:8] or ["#4B1E78", "#9B1B3A"]
    if len(colors) == 1:
        colors = colors * 2
    radians = math.radians(background.angle)
    dx, dy = math.cos(radians), math.sin(radians)
    half = (width * abs(dx) + height * abs(dy)) / 2
    points = [max(0, round(width / 2 - dx * half)), max(0, round(height / 2 - dy * half)),
              max(0, round(width / 2 + dx * half)), max(0, round(height / 2 + dy * half))]
    args = ":".join(f"c{i}=0x{c.lstrip('#')}" for i, c in enumerate(colors))
    # speed at its minimum keeps the gradient still instead of rotating.
    return (f"gradients=s={width}x{height}:r={FPS}:d=1:n={len(colors)}:{args}"
            f":x0={points[0]}:y0={points[1]}:x1={points[2]}:y1={points[3]}:speed=0.00001")


def filter_path(path: Path) -> str:
    """Escape a path for use inside an FFmpeg filter option (drive letters, quotes)."""
    return path.as_posix().replace("\\", "/").replace(":", "\\:").replace("'", "\\'")


def ffmpeg_binary() -> str:
    """ffmpeg from PATH, or the copy the launcher downloaded into tools/ffmpeg."""
    tools = TEMPLATES_DIR.parent / "tools" / "ffmpeg"
    for candidate in (shutil.which("ffmpeg"), tools / "ffmpeg.exe", tools / "ffmpeg"):
        if candidate and Path(candidate).is_file():
            return str(candidate)
    raise RuntimeError("FFmpeg is niet gevonden. Start de app een keer met start.bat of start.command, "
                       "of installeer FFmpeg en zet het in PATH.")


def logo_file(config: OutroConfig) -> Path | None:
    """The logo image on disk, or None when the end screen has no logo."""
    if not config.logo.file:
        return None
    logo = TEMPLATES_DIR / "logos" / config.logo.file
    if not logo.is_file():
        logo = TEMPLATES_DIR / config.logo.file  # older configs pointed straight at templates/
    if not logo.is_file():
        raise RuntimeError(f"Het logobestand {config.logo.file} staat niet in templates/logos.")
    return logo


def logo_chain(config: OutroConfig, scale: float) -> str:
    """Scale the logo and let it come up and go again with the text.

    The text fades because libass draws it with \\fad; the logo is a picture, so it needs
    its own fade over the alpha channel. Both use the same number of seconds, so the end
    screen arrives as one thing instead of a logo that is simply there from frame one.
    """
    steps = [f"scale={int(config.logo.width * scale)}:-1", "format=rgba"]
    if config.fade > 0:
        out = max(0.0, config.duration - config.fade)
        steps.append(f"fade=t=in:st=0:d={config.fade}:alpha=1")
        steps.append(f"fade=t=out:st={out}:d={config.fade}:alpha=1")
    return ",".join(steps)


def background_still(config: OutroConfig, width: int, height: int, destination: Path) -> None:
    """Draw the background once, as a single image the camera can move over.

    The logo is not in here: it has to fade, and a still cannot.
    """
    background = config.background
    inputs: list[str] = []
    chain: list[str] = []
    if background.type == "image":
        image = TEMPLATES_DIR / background.image
        if not image.is_file():
            raise RuntimeError(f"De achtergrondafbeelding templates/{background.image} bestaat niet.")
        inputs += ["-i", str(image)]
        chain.append(f"scale={width}:{height}:force_original_aspect_ratio=increase,crop={width}:{height}")
        if background.darken > 0:
            chain.append(f"drawbox=x=0:y=0:w=iw:h=ih:color=black@{background.darken}:t=fill")
    elif background.type == "gradient":
        inputs += ["-f", "lavfi", "-i", gradient_source(background, width, height)]
    else:
        color = background.color.lstrip("#")
        inputs += ["-f", "lavfi", "-i", f"color=c=0x{color}:s={width}x{height}:d=1"]

    filters = [f"[0:v]{','.join(chain)}[out]" if chain else "[0:v]null[out]"]

    command = [ffmpeg_binary(), "-y", "-hide_banner", "-loglevel", "error", *inputs,
               "-filter_complex", ";".join(filters), "-map", "[out]",
               "-frames:v", "1", "-update", "1", str(destination)]
    result = subprocess.run(command, capture_output=True, text=True)
    if result.returncode != 0:
        raise RuntimeError("De achtergrond van de afsluiter kon niet gemaakt worden: "
                           + result.stderr.strip()[-800:])


def build_command(config: OutroConfig, still: Path, ass: Path, width: int, destination: Path,
                  card: Card = UPRIGHT) -> list[str]:
    """The FFmpeg call that turns the background still into the end screen.

    Order matters. The logo is laid on the background first, so the camera carries it along
    exactly as it carries the background; the text comes last, drawn by libass at the size
    of the finished frame so it stays sharp.
    """
    inputs = ["-loop", "1", "-t", f"{config.duration}", "-r", str(FPS), "-i", str(still)]
    logo = logo_file(config)
    steps = ["[0:v]null[card]"]
    if logo:
        inputs += ["-loop", "1", "-t", f"{config.duration}", "-r", str(FPS), "-i", str(logo)]
        scale = width / card.width  # the background is drawn larger when it has to move
        steps = [f"[1:v]{logo_chain(config, scale * card.scale)}[logo]",
                 f"[0:v][logo]overlay=x=(W-w)/2:y={int(card.y(config.logo.y) * scale)}-h/2:format=auto[card]"]
    audio = 2 if logo else 1  # the silent track comes after the picture inputs
    inputs += ["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"]
    steps.append(f"[card]{motion_filter(config.motion, config.duration, card)},setsar=1,"
                 f"ass=filename='{filter_path(ass)}':fontsdir='{filter_path(FONTS_DIR)}',"
                 f"format=yuv420p[v]")
    return [ffmpeg_binary(), "-y", "-hide_banner", "-loglevel", "error", *inputs,
            "-filter_complex", ";".join(steps), "-map", "[v]", "-map", f"{audio}:a",
            "-t", f"{config.duration}", "-c:v", "libx264", "-preset", "medium", "-crf", "20",
            "-pix_fmt", "yuv420p", "-r", str(FPS), "-c:a", "aac", "-b:a", "96k", "-ar", "48000",
            "-movflags", "+faststart", str(destination)]


def build(config: OutroConfig | None = None, church: ChurchInfo | None = None,
          shape: formats.Shape = formats.UPRIGHT) -> Path:
    """Render the end screen of this shape from the config. Returns the path."""
    brand = brands.active()
    config = config or brand.outro
    church = church or brand.church
    target = file_for(shape)
    card = card_for(config, church, shape.width, shape.height)
    ass_path = target.with_suffix(".ass")
    ass_path.write_text(build_ass(config, church, card), encoding="utf-8")

    # A moving background needs the extra pixels to move into; a still one does not.
    moving = config.motion != "none"
    still_path = target.with_suffix(".bg.png")
    temp = target.with_suffix(".part.mp4")
    try:
        width = card.width * SUPER if moving else card.width
        background_still(config, width, card.height * SUPER if moving else card.height, still_path)
        command = build_command(config, still_path, ass_path, width, temp, card)
        result = subprocess.run(command, capture_output=True, text=True)
        if result.returncode != 0:
            temp.unlink(missing_ok=True)
            raise RuntimeError("De afsluiter kon niet gemaakt worden: " + result.stderr.strip()[-800:])
        temp.replace(target)
    finally:
        ass_path.unlink(missing_ok=True)
        still_path.unlink(missing_ok=True)
    return target


def ensure_outro(shape: formats.Shape = formats.UPRIGHT) -> Path | None:
    """Rebuild the end screen of this shape when the active brand or the way it is drawn changed.

    Returns the file to put behind the clip, or None when there is none. Never overwrites a
    newer hand-made video. This file counts as a source: a pull that changes how the end
    screen is made would otherwise leave the old video in place until someone happened to
    edit the brand.

    A church that makes its own end screen makes it upright. The other shapes then get that
    one, with bars beside it, rather than one drawn from settings the church switched off; a
    hand-made outro.4x5.mp4 next to it is used when there is one.
    """
    target = file_for(shape)
    with _lock:
        brands.migrate()
        brand = brands.active()
        if not brand.outro.generate:
            for own in (target, OUTRO_PATH):
                if own.is_file():
                    return own
            return None
        sources = [brands.path_for(brand.id), brands.ACTIVE_FILE, Path(__file__)]
        newest = max((p.stat().st_mtime for p in sources if p.is_file()), default=0.0)
        if target.is_file() and target.stat().st_mtime >= newest:
            return target
        build(brand.outro, brand.church, shape)
        return target
