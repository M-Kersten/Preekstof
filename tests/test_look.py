"""Colour and contrast: a flat recording lifted to real black and white, a full one left alone."""

import subprocess
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend import brands, formats, house, look, main, models, renderer
from backend.models import ChurchInfo, Enhance, Output, Project, Transcript, VideoInfo


def test_a_flat_picture_is_stretched_to_the_whole_range():
    found = look.look_for(look.Levels(low=35, high=213, colour=8.7))
    assert found is not None
    assert found.low == 35 and found.gain == pytest.approx(219 / 178, abs=0.001)
    assert found.colour == look.COLOUR, "a dull picture gets all the extra colour"


def test_a_picture_that_uses_the_range_is_left_alone():
    assert look.look_for(look.Levels(low=16, high=235, colour=40)) is None


def test_a_very_flat_picture_is_stretched_no_further_than_the_limit():
    found = look.look_for(look.Levels(low=90, high=150, colour=8))
    assert found.gain == look.MOST_GAIN
    assert found.low < 90, "the stretch is centred on what is there"


def test_specks_outside_the_range_do_not_count_as_room():
    found = look.look_for(look.Levels(low=4, high=250, colour=10))
    assert found.gain == pytest.approx(1.0) and found.low == look.BLACK


def test_a_colourful_picture_gets_no_extra_colour():
    assert look.look_for(look.Levels(low=35, high=213, colour=40)).colour == 1.0


def test_the_filter_stretches_brightness_only_and_adds_colour():
    chain = look.chain(look.Look(low=35, gain=1.23, colour=1.2))
    assert chain.startswith("lutyuv=y='clip((val-35")
    assert ":u=" not in chain and ":v=" not in chain, "the colour planes are not stretched"
    assert chain.endswith("eq=saturation=1.2,")
    assert look.chain(None) == ""


@pytest.fixture
def flat_video(tmp_path) -> Path:
    video = tmp_path / "flat.mp4"
    subprocess.run(["ffmpeg", "-v", "error", "-y", "-f", "lavfi", "-i", "testsrc2=s=640x360:r=10:d=3",
                    "-vf", "eq=contrast=0.6:saturation=0.4", "-c:v", "libx264", "-preset", "ultrafast",
                    "-pix_fmt", "yuv420p", str(video)], check=True)
    return video


def test_a_flat_recording_measures_flat(flat_video):
    levels = look.measure(flat_video, 0.0, 3.0)
    assert levels is not None
    assert levels.low > 30 and levels.high < 225
    assert look.look_for(levels).gain > 1.1


def test_a_clip_is_measured_once(flat_video, tmp_path, monkeypatch):
    first = look.remembered(tmp_path / "work", flat_video, 0.0, 3.0)
    monkeypatch.setattr(look, "measure", lambda *a: pytest.fail("measured again"))
    assert look.remembered(tmp_path / "work", flat_video, 0.0, 3.0) == first


def test_another_range_is_measured_again(flat_video, tmp_path, monkeypatch):
    look.remembered(tmp_path / "work", flat_video, 0.0, 3.0)
    asked = []
    monkeypatch.setattr(look, "measure", lambda *a: asked.append(a) or None)
    look.remembered(tmp_path / "work", flat_video, 1.0, 2.0)
    assert asked


def test_the_correction_goes_first_in_the_picture(tmp_path):
    info = VideoInfo(width=1280, height=720, duration=10.0, fps=25.0, videoCodec="h264",
                     hasAudio=False, audioCodec=None, audioSampleRate=None, audioChannels=None)
    cmd, _ = renderer.build_command(tmp_path / "in.mp4", info, tmp_path / "s.ass", None, None, Output(),
                                    tmp_path / "out.mp4", look="lutyuv=y='val',eq=saturation=1.2,")
    graph = cmd[cmd.index("-filter_complex") + 1]
    assert "[0:v]lutyuv=y='val',eq=saturation=1.2,hqdn3d" in graph


def test_a_clip_from_before_keeps_its_recipe():
    """Off, the setting is left out of the recipe, so videos made before it existed are not out of date."""
    clip = Project(id="c", createdAt="2026-10-01T10:00:00")
    assert clip.enhance.on is False
    brand = brands.Brand(id="b", name="B")
    before = formats.recipe(clip, Transcript(), brand)
    formats_without = formats.RECIPE - {"enhance"}
    assert "enhance" not in clip.model_dump(include=formats_without)
    clip.enhance = Enhance(on=True)
    assert formats.recipe(clip, Transcript(), brand) != before


@pytest.fixture
def folders(tmp_path, monkeypatch):
    monkeypatch.setattr(models, "PROJECTS_DIR", tmp_path / "projects")
    templates = tmp_path / "templates"
    (templates / "brands").mkdir(parents=True)
    monkeypatch.setattr(brands, "BRANDS_DIR", templates / "brands")
    monkeypatch.setattr(brands, "ACTIVE_FILE", templates / "brands" / "actief.json")
    brands.save(brands.Brand(id="kerk", name="De Kerk", church=ChurchInfo(churchName="De Kerk")))
    brands.set_active("kerk")
    return tmp_path


def a_clip(name: str) -> Project:
    (models.project_dir(name) / "output").mkdir(parents=True, exist_ok=True)
    project = house.dress(Project(id=name, createdAt="2026-10-08T10:00:00"))
    models.save_project(project)
    return project


def test_a_new_clip_has_it_on(folders):
    assert a_clip("a").enhance.on is True


def test_switching_it_off_goes_for_every_clip_not_yet_made(folders):
    a_clip("a"), a_clip("b")
    client = TestClient(main.app)
    assert client.put("/projects/a/enhance", json={"on": False}).status_code == 200
    assert models.load_project("b").enhance.on is False
    assert brands.active().enhance.on is False
    assert client.get("/projects/b/look").json() == {"on": False, "look": None}
