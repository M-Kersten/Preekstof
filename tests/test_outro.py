"""The end screen: what the video shows has to be what the preview showed."""

import math
import os
import subprocess
from pathlib import Path

import pytest

from backend import fonts, outro
from backend.models import ChurchInfo, OutroBackground, OutroConfig, OutroLine


def config(**kwargs) -> OutroConfig:
    kwargs = {"duration": 4.0, "fade": 0.6, **kwargs}
    cfg = OutroConfig(**kwargs)
    cfg.logo.file = ""
    return cfg


def graph(command: list[str]) -> str:
    return command[command.index("-filter_complex") + 1]


def with_logo(tmp_path: Path, **kwargs) -> tuple[OutroConfig, Path]:
    logo = outro.OWN_TEMPLATES / "logos" / "testlogo.png"
    if not logo.is_file():
        logo.parent.mkdir(parents=True, exist_ok=True)
        subprocess.run(["ffmpeg", "-y", "-v", "error", "-f", "lavfi", "-i", "color=c=white:s=200x100",
                        "-frames:v", "1", "-update", "1", str(logo)], check=True)
    cfg = config(**kwargs)
    cfg.logo.file = logo.name
    return cfg, tmp_path


def test_logo_fades_over_the_same_seconds_as_the_text():
    cfg = config()
    cfg.logo.file = "whatever.png"
    chain = outro.logo_chain(cfg, 1.0)
    assert "fade=t=in:st=0:d=0.6:alpha=1" in chain
    assert "fade=t=out:st=3.4:d=0.6:alpha=1" in chain
    # Without alpha there is nothing to fade.
    assert chain.index("format=rgba") < chain.index("fade=t=in")


def test_a_fade_of_nothing_leaves_the_logo_alone():
    cfg = config(fade=0.0)
    cfg.logo.file = "whatever.png"
    assert "fade" not in outro.logo_chain(cfg, 1.0)


def test_logo_is_scaled_with_a_shorter_card():
    cfg = config()
    cfg.logo.file = "whatever.png"
    cfg.logo.width = 420
    assert "scale=420:-1" in outro.logo_chain(cfg, 1.0)
    assert "scale=210:-1" in outro.logo_chain(cfg, 0.5)


def test_the_logo_stays_put_while_the_background_moves(tmp_path):
    """The camera moves the background only. A logo carried along looked zoomed against the preview."""
    cfg, _ = with_logo(tmp_path, motion="in")
    steps = graph(outro.build_command(cfg, tmp_path / "bg.png", tmp_path / "o.ass", outro.BIG_W, tmp_path / "o.mp4"))
    assert steps.index("zoompan") < steps.index("overlay")
    assert f"scale={cfg.logo.width}:-1" in steps, "the logo is laid on the finished frame, at its own size"
    # And the text is drawn last, on the finished frame.
    assert steps.index("overlay") < steps.index("ass=filename=")


def test_the_text_stands_still_whatever_the_camera_does():
    for motion in ("none", "in", "out", "up"):
        ass = outro.build_ass(config(motion=motion), ChurchInfo(churchName="De Kerk"))
        assert "\\move" not in ass and "\\t(" not in ass and "\\fscx" not in ass
        assert "\\pos(540.00,860.00)" in ass, motion


def test_the_letters_are_as_big_as_the_preview_draws_them():
    """libass sizes the whole line box; the preview in the browser sizes the letters."""
    cfg = config(lines=[OutroLine(text="Kerk", size=100, font="Poppins")])
    ass = outro.build_ass(cfg, ChurchInfo())
    assert f"Style: L0,Poppins,{round(100 * fonts.box_of('Poppins'), 1):g}," in ass
    assert 1.7 < fonts.box_of("Poppins") < 1.8


def test_the_gradient_is_the_same_every_time_and_runs_like_css():
    """A point outside the picture made FFmpeg pick a random one, so each rebuild differed."""
    source = outro.gradient_source(OutroBackground(type="gradient", colors=["#000000", "#FFFFFF"], angle=115),
                                   1080, 1920)
    size = dict(part.split("=") for part in source.split(",")[0].removeprefix("gradients=").split(":"))
    width, height = (int(n) for n in size["s"].split("x"))
    for x, y in (("x0", "y0"), ("x1", "y1")):
        assert 0 <= int(size[x]) < width and 0 <= int(size[y]) < height
    crop = source.split(",crop=")[1].split(":")
    assert crop[:2] == ["1080", "1920"]
    # The colour line runs through the middle of the frame, at the angle the preview uses.
    cx, cy = int(crop[2]) + 540, int(crop[3]) + 960
    mid = ((int(size["x0"]) + int(size["x1"])) / 2, (int(size["y0"]) + int(size["y1"])) / 2)
    assert abs(mid[0] - cx) <= 1 and abs(mid[1] - cy) <= 1
    angle = math.degrees(math.atan2(int(size["y1"]) - int(size["y0"]), int(size["x1"]) - int(size["x0"])))
    assert abs(angle - 115) < 0.2


def test_without_a_logo_nothing_is_overlaid(tmp_path):
    steps = graph(outro.build_command(config(), tmp_path / "bg.png", tmp_path / "o.ass", outro.WIDTH, tmp_path / "o.mp4"))
    assert "overlay" not in steps
    assert "[card]ass=filename=" in steps


def test_the_silent_track_is_mapped_whether_or_not_there_is_a_logo(tmp_path):
    plain = outro.build_command(config(), tmp_path / "bg.png", tmp_path / "o.ass", outro.WIDTH, tmp_path / "o.mp4")
    assert plain[plain.index("-map") + 3] == "1:a"
    cfg, _ = with_logo(tmp_path)
    logo = outro.build_command(cfg, tmp_path / "bg.png", tmp_path / "o.ass", outro.WIDTH, tmp_path / "o.mp4")
    assert logo[logo.index("-map") + 3] == "2:a"


def test_the_background_still_no_longer_holds_the_logo(tmp_path, monkeypatch):
    """A still cannot fade, so the logo must not be baked into it."""
    seen: list[list[str]] = []

    class Done:
        returncode = 0
        stderr = ""

    monkeypatch.setattr(outro.subprocess, "run", lambda cmd, **kw: seen.append(cmd) or Done())
    cfg, _ = with_logo(tmp_path)
    outro.background_still(cfg, outro.WIDTH, outro.HEIGHT, tmp_path / "bg.png")
    assert "overlay" not in " ".join(seen[0])


def test_a_changed_way_of_drawing_rebuilds_the_end_screen(monkeypatch, tmp_path):
    """A pull changes outro.py, not the brand file; the video must still be made again."""
    built: list[str] = []
    video = tmp_path / "outro.mp4"
    video.write_bytes(b"old")
    monkeypatch.setattr(outro, "OUTRO_PATH", video)
    monkeypatch.setattr(outro, "build", lambda *a, **k: built.append("built") or video)
    monkeypatch.setattr(outro.brands, "migrate", lambda: None)

    # Ages are set against the code's own file, so the test does not depend on when it runs.
    code = Path(outro.__file__).stat().st_mtime
    for source in (outro.brands.ACTIVE_FILE, outro.brands.path_for(outro.brands.active().id)):
        if source.is_file():
            os.utime(source, (code - 100, code - 100))

    os.utime(video, (code + 100, code + 100))  # made after the last change to any of it
    outro.ensure_outro()
    assert built == [], "nothing changed, nothing is remade"

    os.utime(video, (code - 100, code - 100))  # made before backend/outro.py last changed
    outro.ensure_outro()
    assert built == ["built"]
