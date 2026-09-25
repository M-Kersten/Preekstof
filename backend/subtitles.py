"""Convert transcript segments into an ASS subtitle file.

The layout rules here (safe margins, two-line wrapping, font shrinking) are
mirrored in frontend/src/subtitleLayout.ts so the preview matches the render.
"""

from pathlib import Path

from . import fonts
from .models import Output, Segment, Spoken, Style, Transcript

SAFE_MARGIN_BOTTOM = 320  # px from the bottom edge at 1080x1920 (clear of the Reels UI)
TIMELINE_MARGIN = 0.09  # share of the height, in a shape nothing is laid over (4:5, square)
SAFE_MARGIN_SIDE = 90  # px from the left/right edges
CHAR_WIDTH_RATIO = 0.58  # average glyph width relative to font size (bold sans-serif)
MIN_FONT_SCALE = 0.6  # never shrink a line below this fraction of the chosen size
MAX_LINES = 3  # a bigger font spreads over more lines before it is shrunk
BACKGROUND_ALPHA = 0x80  # 50% translucent box

# Font family names as libass finds them in templates/fonts (and system fonts for Arial).
# Non-bold/regular weights ship as their own family name ("Montserrat SemiBold").
WEIGHT_SUFFIX = {"regular": "", "medium": " Medium", "semibold": " SemiBold", "bold": "", "extrabold": " ExtraBold"}


def family_for(font: str, weight: str) -> tuple[str, bool]:
    """Return (ASS Fontname, bold flag) for a font family and weight.

    Families that do not have the asked-for weight fall back to their nearest one,
    so a single-weight display font like Bebas Neue still renders.
    """
    if font == fonts.SYSTEM_FONT:
        return fonts.SYSTEM_FONT, weight in ("semibold", "bold", "extrabold")
    weight = fonts.resolve_weight(font, weight)
    return font + WEIGHT_SUFFIX.get(weight, ""), weight == "bold"


def font_name(style: Style) -> tuple[str, bool]:
    """Return (ASS Fontname, bold flag) for a subtitle style."""
    return family_for(style.font, style.fontWeight)


def wrap_words(words: list[str], width: int) -> list[str]:
    """Greedy fill: put as many words on a line as fit within `width` characters."""
    lines: list[str] = []
    current = ""
    for word in words:
        candidate = f"{current} {word}".strip()
        if current and len(candidate) > width:
            lines.append(current)
            current = word
        else:
            current = candidate
    if current:
        lines.append(current)
    return lines


def fit_lines(words: list[str], count: int, max_chars: int) -> list[str] | None:
    """Split the words over at most `count` lines, none wider than max_chars.

    Starts from evenly divided lines and widens until the greedy fill needs no
    extra line, so the lines come out roughly equal instead of one long, one short.
    """
    total = len(" ".join(words))
    start = max(max(len(w) for w in words), -(-total // count))
    for width in range(start, max_chars + 1):
        lines = wrap_words(words, width)
        if len(lines) <= count:
            return lines
    return None


def layout_text(text: str, style: Style, output: Output) -> tuple[list[str], int]:
    """Wrap text over as few lines as it needs; shrink the font only as a last resort.

    Returns (lines, font_size). A large font takes more lines, up to MAX_LINES, so
    the text really does get bigger on screen instead of being scaled straight back.
    """
    text = " ".join(text.split())
    available = output.width - 2 * SAFE_MARGIN_SIDE
    max_chars = max(8, int(available / (style.fontSize * CHAR_WIDTH_RATIO)))
    if len(text) <= max_chars:
        return [text], style.fontSize

    words = text.split(" ")
    if len(words) == 1:
        return [text], style.fontSize

    for count in range(2, MAX_LINES + 1):
        lines = fit_lines(words, count, max_chars)
        if lines is not None:
            return lines, style.fontSize

    # Still too wide: use MAX_LINES lines at the largest size those lines fit at.
    # Sizing from the lines rather than from a fraction of the asked-for size keeps this
    # monotonic, so turning the size up never renders the text smaller than before.
    lines = fit_lines(words, MAX_LINES, len(text)) or [text]
    longest = max(len(line) for line in lines)
    fitted = int(available / (longest * CHAR_WIDTH_RATIO))
    return lines, max(int(style.fontSize * MIN_FONT_SCALE), min(style.fontSize, fitted))


def word_times(seg: Segment) -> list[Spoken]:
    """When each word of this caption is said. Mirrored in frontend/src/subtitleLayout.ts.

    Whisper's own timings are used when they still describe the text. They stop describing it
    the moment somebody corrects a name in the editor, and a caption that lights up a word
    that is no longer there is worse than one that guesses, so the fallback spreads the words
    over the caption by how long they are. Long words take longer to say than short ones,
    which is crude and close enough to follow a voice.
    """
    said = seg.text.split()
    if not said or seg.end <= seg.start:
        return []
    kept = [w for w in seg.words if w.word.strip()]
    if len(kept) == len(said):
        return [Spoken(start=w.start, end=w.end, word=text) for w, text in zip(kept, said)]
    weights = [len(word) + 1 for word in said]
    total = sum(weights)
    span = seg.end - seg.start
    out, at = [], seg.start
    for word, weight in zip(said, weights):
        ends = at + span * weight / total
        out.append(Spoken(start=round(at, 3), end=round(ends, 3), word=word))
        at = ends
    return out


def ass_color(hex_color: str, alpha: int = 0) -> str:
    """'#RRGGBB' -> '&HAABBGGRR'."""
    hex_color = hex_color.lstrip("#")
    if len(hex_color) != 6:
        hex_color = "FFFFFF"
    r, g, b = hex_color[0:2], hex_color[2:4], hex_color[4:6]
    return f"&H{alpha:02X}{b}{g}{r}".upper()


def ass_time(seconds: float) -> str:
    seconds = max(0.0, seconds)
    h = int(seconds // 3600)
    m = int(seconds % 3600 // 60)
    s = seconds % 60
    return f"{h}:{m:02d}:{s:05.2f}"


def escape_text(text: str) -> str:
    return text.replace("{", "(").replace("}", ")").replace("\n", " ")


def safe_bottom(output: Output) -> int:
    """How far the captions stay above the bottom edge.

    Upright, Instagram, TikTok and YouTube lay the account name, the post text and their
    buttons over the lowest sixth of the picture, and a caption down there is a caption
    nobody can read. A timeline lays nothing over the video, so in the shorter shapes the
    captions come down to where the eye expects them.
    """
    if output.height * 9 >= output.width * 16:
        return SAFE_MARGIN_BOTTOM
    return round(output.height * TIMELINE_MARGIN)


def animation_tags(style: Style, output: Output) -> str:
    """The ASS tags that make a line appear, in the style the user picked."""
    ms = style.animationSpeed
    if style.animation == "fade":
        return f"\\fad({ms},{min(ms, 200)})"
    if style.animation == "pop":
        # Start slightly small and settle: reads as a snap without moving the line.
        return f"\\fad(60,80)\\fscx72\\fscy72\\t(0,{ms},\\fscx100\\fscy100)"
    if style.animation == "slide":
        # Alignment 2 anchors the bottom centre of the block; slide it up into that spot.
        anchor_y = output.height - safe_bottom(output)
        return f"\\fad(60,80)\\move({output.width // 2},{anchor_y + 40},{output.width // 2},{anchor_y},0,{ms})"
    return ""


def lit_words(lines: list[str], said: list[Spoken]) -> list[list[Spoken | None]]:
    """Pair every word of every wrapped line with when it is said, in order.

    The wrapping only decides where the breaks go, so walking the timings from the front
    keeps them lined up with the words. Mirrored in frontend/src/subtitleLayout.ts.
    """
    left = list(said)
    out = []
    for line in lines:
        row: list[Spoken | None] = []
        for word in line.split(" "):
            timing = left.pop(0) if left else None
            row.append(Spoken(start=timing.start, end=timing.end, word=word) if timing else None)
        out.append(row)
    return out


def lit_line(line: str, timings: list[Spoken | None], start: float, style: Style) -> str:
    """One caption line with each word set to change colour while it is being spoken.

    libass applies an override tag to the text that follows it, so every word carries its own
    colour and its own two switches: on at the moment it is said, off again after. Written
    that way rather than as karaoke tags, which colour everything said so far and leave it
    coloured, and rather than as a line per word, which would restart the entrance animation
    on every word.
    """
    out = []
    for word, timing in zip(line.split(" "), timings):
        if timing is None:
            out.append(escape_text(word))
            continue
        on = max(0, int((timing.start - start) * 1000))
        off = max(on + 1, int((timing.end - start) * 1000))
        out.append(f"{{\\1c{ass_color(style.color)}"
                   f"\\t({on},{on + 1},\\1c{ass_color(style.highlightColor)})"
                   f"\\t({off},{off + 1},\\1c{ass_color(style.color)})}}"
                   f"{escape_text(word)}")
    return " ".join(out)


def build_ass(transcript: Transcript, style: Style, output: Output) -> str:
    name, bold = font_name(style)
    border_style = 4 if style.background else 1  # 4 = libass: box behind each line, outline kept
    lines = [
        "[Script Info]",
        "ScriptType: v4.00+",
        f"PlayResX: {output.width}",
        f"PlayResY: {output.height}",
        "WrapStyle: 0",
        "ScaledBorderAndShadow: yes",
        "YCbCr Matrix: TV.709",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, "
        "Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, "
        "Alignment, MarginL, MarginR, MarginV, Encoding",
        f"Style: Default,{name},{style.fontSize},{ass_color(style.color)},{ass_color(style.color)},"
        f"{ass_color(style.outlineColor)},{ass_color('#000000', BACKGROUND_ALPHA)},"
        f"{-1 if bold else 0},0,0,0,100,100,0,0,{border_style},{style.outline},0,2,"
        f"{SAFE_MARGIN_SIDE},{SAFE_MARGIN_SIDE},{safe_bottom(output)},1",
        "",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ]
    tags = animation_tags(style, output)
    for seg in sorted(transcript.segments, key=lambda s: s.start):
        if not seg.text.strip() or seg.end <= seg.start:
            continue
        wrapped, size = layout_text(seg.text, style, output)
        if style.highlight:
            timed = lit_words(wrapped, word_times(seg))
            text = "\\N".join(lit_line(line, row, seg.start, style)
                              for line, row in zip(wrapped, timed))
        else:
            text = "\\N".join(escape_text(line) for line in wrapped)
        prefix = tags + (f"\\fs{size}" if size != style.fontSize else "")
        if prefix:
            text = "{" + prefix + "}" + text
        lines.append(f"Dialogue: 0,{ass_time(seg.start)},{ass_time(seg.end)},Default,,0,0,0,,{text}")
    return "\n".join(lines) + "\n"


def write_ass(transcript: Transcript, style: Style, output: Output, path: Path) -> Path:
    path.write_text(build_ass(transcript, style, output), encoding="utf-8")
    return path
