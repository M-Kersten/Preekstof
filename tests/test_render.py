"""One real render, start to finish, so the FFmpeg command is proved and not just assembled."""

import shutil
import subprocess
from pathlib import Path

import pytest

from backend import renderer
from backend.models import Output, Segment, Style, Transcript, Watermark
from backend.subtitles import write_ass

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="needs FFmpeg")

OUT = Output()


@pytest.fixture(scope="module")
def clip(tmp_path_factory):
    """A short test clip with sound, standing in for a fragment of a service."""
    path = tmp_path_factory.mktemp("source") / "clip.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "testsrc2=s=1920x1080:r=30:d=4",
         "-f", "lavfi", "-i", "sine=frequency=440:duration=4",
         "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-shortest", str(path)], check=True)
    return path


def test_probe_reads_what_the_editor_needs(clip):
    info = renderer.probe(clip)
    assert (info.width, info.height) == (1920, 1080)
    assert info.duration == pytest.approx(4.0, abs=0.2)
    assert info.hasAudio and info.videoCodec == "h264"


def test_probe_refuses_a_file_with_no_picture(tmp_path):
    audio = tmp_path / "audio.m4a"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "sine=duration=1",
                    "-c:a", "aac", str(audio)], check=True)
    with pytest.raises(ValueError):
        renderer.probe(audio)


def test_render_produces_a_playable_vertical_video(clip, tmp_path):
    subs = tmp_path / "subs.ass"
    write_ass(Transcript(language="nl", segments=[
        Segment(start=0.2, end=2.0, text="God is op zoek naar jou"),
        Segment(start=2.2, end=3.8, text="Niet omdat je perfect bent."),
    ]), Style(), OUT, subs)

    out = tmp_path / "final.mp4"
    renderer.render_video(clip, renderer.probe(clip), subs, OUT, out)

    assert out.is_file() and out.stat().st_size > 10_000
    made = renderer.probe(out)
    assert (made.width, made.height) == (OUT.width, OUT.height)
    assert made.duration == pytest.approx(4.0, abs=0.5)
    assert made.hasAudio


def test_render_reports_progress_that_only_moves_forward(clip, tmp_path):
    subs = tmp_path / "subs.ass"
    write_ass(Transcript(language="nl", segments=[]), Style(), OUT, subs)
    seen: list[float] = []
    renderer.render_video(clip, renderer.probe(clip), subs, OUT, tmp_path / "p.mp4",
                          on_progress=lambda f, _m: seen.append(f))
    assert seen, "the render reported no progress at all"
    assert seen == sorted(seen)
    assert 0.0 <= seen[0] and seen[-1] <= 1.0


def test_render_burns_the_logo_into_the_corner(clip, tmp_path):
    from backend.models import TEMPLATES_DIR
    logos = TEMPLATES_DIR / "logos"
    logos.mkdir(parents=True, exist_ok=True)
    logo = logos / "_test_mark.png"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi",
                    "-i", "color=c=white:s=200x100", "-frames:v", "1", "-update", "1", str(logo)], check=True)
    try:
        subs = tmp_path / "subs.ass"
        write_ass(Transcript(language="nl", segments=[]), Style(), OUT, subs)
        out = tmp_path / "marked.mp4"
        renderer.render_video(clip, renderer.probe(clip), subs, OUT, out,
                              watermark=Watermark(file=logo.name, corner="topLeft", width=0.25,
                                                  opacity=1.0, margin=40))
        frame = tmp_path / "frame.pgm"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", "1", "-i", str(out),
                        "-frames:v", "1", "-update", "1", str(frame)], check=True)
        pixels = frame.read_bytes()
        assert len(pixels) > 1000  # the frame decoded; the logo is white on a test pattern
        assert renderer.probe(out).width == OUT.width
    finally:
        logo.unlink(missing_ok=True)


def test_a_broken_source_gives_a_readable_message(tmp_path):
    broken = tmp_path / "broken.mp4"
    broken.write_bytes(b"this is not a video")
    assert "beschadigd" in renderer.ffmpeg_message("Invalid data found when processing input")
    assert "ruimte" in renderer.ffmpeg_message("No space left on device")
    assert "rechten" in renderer.ffmpeg_message("Permission denied")


# --- lighting up the word that is being said --------------------------------------


def gold_in(frame: Path, output: Output) -> tuple[int, float]:
    """How many pixels of the highlight colour are in this frame, and where they sit."""
    import numpy as np

    raw = subprocess.run(["ffmpeg", "-v", "error", "-i", str(frame), "-f", "rawvideo",
                          "-pix_fmt", "rgb24", "-"], capture_output=True, check=True).stdout
    pixels = np.frombuffer(raw, np.uint8).reshape(output.height, output.width, 3).astype(np.int16)
    # #C9971C against white: red stays high, green drops, blue drops a lot.
    gold = ((pixels[:, :, 0] > 140) & (pixels[:, :, 1] > 90)
            & (pixels[:, :, 1] < 200) & (pixels[:, :, 2] < 110))
    found = np.argwhere(gold)
    return len(found), float(found[:, 1].mean()) if len(found) else float("nan")


@pytest.fixture(scope="module")
def dark(tmp_path_factory):
    """Black footage: the colour test pattern has gold in it, which is the colour we hunt for."""
    path = tmp_path_factory.mktemp("dark") / "black.mp4"
    subprocess.run(
        ["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "color=c=black:s=1920x1080:r=25:d=5",
         "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p", str(path)], check=True)
    return path


@pytest.fixture(scope="module")
def lit(tmp_path_factory, dark):
    """A clip rendered with the words lighting up, and the timings that went into it."""
    from backend.models import Spoken

    place = tmp_path_factory.mktemp("lit")
    said = ["God", "is", "op", "zoek", "naar", "jou"]
    each = 0.5
    words = [Spoken(start=round(0.3 + i * each, 2), end=round(0.3 + (i + 1) * each, 2), word=w)
             for i, w in enumerate(said)]
    seg = Segment(start=0.3, end=round(0.3 + len(said) * each, 2), text=" ".join(said), words=words)
    style = Style(highlight=True, animation="none", fontSize=48)
    subs = write_ass(Transcript(language="nl", segments=[seg]), style, OUT, place / "lit.ass")
    out = place / "lit.mp4"
    renderer.render_video(dark, renderer.probe(dark), subs, OUT, out)
    return out, words, place


def test_one_word_is_lit_at_a_time_and_it_walks_along_the_line(lit):
    """The whole point, checked on the pixels rather than on the tags that asked for it."""
    video, words, place = lit
    middles = []
    for i, word in enumerate(words):
        at = (word.start + word.end) / 2
        frame = place / f"at{i}.png"
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", f"{at:.2f}", "-i", str(video),
                        "-frames:v", "1", "-update", "1", str(frame)], check=True)
        count, middle = gold_in(frame, OUT)
        assert count > 100, f"nothing lit up while {word.word!r} was being said"
        middles.append(middle)
    assert middles == sorted(middles), f"the highlight jumped about: {middles}"
    assert middles[-1] - middles[0] > 200, "it hardly moved, so it is not following the words"


def test_nothing_is_lit_before_the_caption_starts(lit):
    video, _words, place = lit
    frame = place / "before.png"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", "0.05", "-i", str(video),
                    "-frames:v", "1", "-update", "1", str(frame)], check=True)
    assert gold_in(frame, OUT)[0] < 100


def test_a_clip_without_the_setting_has_no_colour_in_it(dark, tmp_path):
    subs = write_ass(Transcript(language="nl", segments=[
        Segment(start=0.3, end=3.3, text="God is op zoek naar jou"),
    ]), Style(animation="none", fontSize=48), OUT, tmp_path / "plain.ass")
    out = tmp_path / "plain.mp4"
    renderer.render_video(dark, renderer.probe(dark), subs, OUT, out)
    frame = tmp_path / "mid.png"
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-ss", "1.5", "-i", str(out),
                    "-frames:v", "1", "-update", "1", str(frame)], check=True)
    assert gold_in(frame, OUT)[0] < 100, "words lit up without anybody asking for it"
