"""One clip, three shapes: upright for Reels, 4:5 for a timeline, square for everywhere else.

What has to hold is that every shape is the same clip. The words, the framing, the end
screen and the choice of what was made when all carry over; only the frame changes. And a
shape made before somebody fixed a word has to say so, because posting it would post the
version with the mistake still in it.
"""

import time

import pytest
from fastapi.testclient import TestClient

from backend import brands, formats, main, models, outro, subtitles
from backend.models import (ChurchInfo, Output, OutroConfig, OutroLine, Project, Segment, ShareSettings, Style,
                            Transcript, VideoInfo)


# --- which shapes, and where they go -------------------------------------------------


def test_the_button_under_the_preview_makes_upright_and_what_the_church_always_wants():
    made = formats.wanted(None, ["1x1"])
    assert [s.key for s in made] == ["9x16", "1x1"]


def test_asking_for_one_shape_makes_only_that_one():
    assert [s.key for s in formats.wanted(["4x5"], ["1x1"])] == ["4x5"]


def test_shapes_come_out_in_one_order_and_once_each():
    assert [s.key for s in formats.wanted(["1x1", "9x16", "1x1", "4x5"], [])] == ["9x16", "4x5", "1x1"]


def test_an_unknown_shape_is_refused():
    with pytest.raises(ValueError):
        formats.wanted(["16x9"], [])


def test_upright_is_never_an_extra_and_unknown_extras_are_dropped():
    assert formats.extras(["9x16", "4x5", "banana", "4x5"]) == ["4x5"]


def test_upright_keeps_the_names_it_always_had():
    assert formats.UPRIGHT.file == "final.mp4"
    assert formats.work_name(formats.UPRIGHT, "subtitles.ass") == "subtitles.ass"
    assert formats.work_name(formats.SQUARE, "subtitles.ass") == "subtitles-1x1.ass"
    assert formats.work_name(formats.TIMELINE, "track.cmd") == "track-4x5.cmd"


def test_every_shape_renders_at_the_clips_own_frame_rate():
    base = Output(width=1080, height=1920, fps=25)
    assert formats.output_for(formats.UPRIGHT, base) is base
    square = formats.output_for(formats.SQUARE, base)
    assert (square.width, square.height, square.fps) == (1080, 1080, 25)


# --- the captions -------------------------------------------------------------------


def test_upright_captions_stay_clear_of_the_buttons_laid_over_a_reel():
    assert subtitles.safe_bottom(Output()) == subtitles.SAFE_MARGIN_BOTTOM


def test_in_a_timeline_nothing_lies_over_the_video_so_captions_come_down():
    assert subtitles.safe_bottom(Output(width=1080, height=1350)) == 122
    assert subtitles.safe_bottom(Output(width=1080, height=1080)) == 97


def test_the_caption_file_of_a_square_clip_says_so():
    square = Output(width=1080, height=1080)
    ass = subtitles.build_ass(Transcript(segments=[Segment(start=0, end=2, text="Genade")]), Style(), square)
    assert "PlayResY: 1080" in ass
    assert ",90,90,97,1" in ass  # left, right and bottom margins of the style


# --- the end screen -----------------------------------------------------------------


def a_config(*lines: OutroLine) -> OutroConfig:
    config = OutroConfig(lines=list(lines) or OutroConfig().lines)
    config.logo.file = ""
    return config


def test_the_upright_end_screen_is_drawn_exactly_where_it_is_designed():
    assert outro.card_for(a_config(), ChurchInfo()) is outro.UPRIGHT
    assert outro.UPRIGHT.y(760) == 760


def test_a_shorter_end_screen_keeps_its_spacing_and_moves_to_the_middle():
    config = a_config()
    card = outro.card_for(config, ChurchInfo(), 1080, 1080)
    assert card.scale == 1.0, "the default block fits a square as it is"
    ys = [card.y(line.y) for line in config.lines]
    designed = [line.y for line in config.lines]
    assert [b - a for a, b in zip(ys, ys[1:])] == [b - a for a, b in zip(designed, designed[1:])]
    assert 0 < min(ys) and max(ys) < 1080
    assert card.y(card.middle) == 540


def test_a_block_too_tall_for_the_frame_is_drawn_smaller():
    config = a_config(OutroLine(text="Boven", y=200, size=60), OutroLine(text="Onder", y=1700, size=60))
    card = outro.card_for(config, ChurchInfo(), 1080, 1080)
    assert card.scale < 1.0
    assert card.y(200) >= 1080 * outro.EDGE
    assert card.y(1700) <= 1080 * (1 - outro.EDGE)


def test_a_line_that_says_nothing_takes_no_room():
    empty = OutroLine(text="{instagram}", y=1800, size=60)
    config = a_config(OutroLine(text="Welkom", y=900, size=60), empty)
    card = outro.card_for(config, ChurchInfo(instagram=""), 1080, 1080)
    assert card.middle == 900


def test_the_square_end_screen_is_written_for_a_square():
    config = a_config()
    card = outro.card_for(config, ChurchInfo(), 1080, 1080)
    ass = outro.build_ass(config, ChurchInfo(churchName="De Kerk"), card)
    assert "PlayResX: 1080" in ass and "PlayResY: 1080" in ass
    assert "De Kerk" in ass


def test_each_shape_has_its_own_end_screen_file():
    assert outro.file_for(formats.UPRIGHT) == outro.OUTRO_PATH
    assert outro.file_for(formats.SQUARE).name == "outro.1x1.mp4"


def test_a_hand_made_end_screen_is_used_for_every_shape(tmp_path, monkeypatch):
    """A church that switched drawing off made its own, upright. That one goes behind the others too."""
    own = tmp_path / "outro.mp4"
    own.write_bytes(b"hand made")
    monkeypatch.setattr(outro, "OUTRO_PATH", own)
    monkeypatch.setattr(outro.brands, "migrate", lambda: None)
    brand = brands.Brand(id="eigen", name="Eigen", outro=OutroConfig(generate=False))
    monkeypatch.setattr(outro.brands, "active", lambda: brand)
    monkeypatch.setattr(outro, "build", lambda *a, **k: pytest.fail("a hand-made end screen is never redrawn"))
    assert outro.ensure_outro(formats.SQUARE) == own


# --- what was made, and whether it still is ------------------------------------------


@pytest.fixture
def client(tmp_path, monkeypatch):
    folder = tmp_path / "projects"
    folder.mkdir()
    monkeypatch.setattr(models, "PROJECTS_DIR", folder)
    templates = tmp_path / "templates"
    (templates / "brands").mkdir(parents=True)
    monkeypatch.setattr(brands, "BRANDS_DIR", templates / "brands")
    monkeypatch.setattr(brands, "ACTIVE_FILE", templates / "brands" / "actief.json")
    brands.save(brands.Brand(id="kerk", name="De Kerk", church=ChurchInfo(churchName="De Kerk")))
    brands.set_active("kerk")
    monkeypatch.setattr(main, "end_screen", lambda project, shape: None)
    monkeypatch.setattr(main.posts, "write", lambda project_id: None)
    made: list[tuple[str, int, int]] = []

    def fake_render(source, info, subs, output, destination, **kwargs):
        made.append((destination.name, output.width, output.height))
        if kwargs.get("on_progress"):
            kwargs["on_progress"](0.5, "Video wordt gemaakt")
        destination.write_bytes(b"x" * 2000)
        return destination

    monkeypatch.setattr(main.renderer, "render_video", fake_render)
    with TestClient(main.app) as running:
        running.made = made
        yield running


def a_project(pid: str = "clip") -> Project:
    folder = models.project_dir(pid)
    (folder / "work").mkdir(parents=True, exist_ok=True)
    (folder / "output").mkdir(exist_ok=True)
    (folder / "source.mp4").write_bytes(b"not really a video")
    project = Project(
        id=pid, createdAt="2026-09-21T10:00:00", title="Genade is geen beloning", sourceVideo="source.mp4",
        sourceInfo=VideoInfo(width=1920, height=1080, duration=30.0, fps=25.0, hasAudio=True))
    models.save_project(project)
    models.save_transcript(project, Transcript(segments=[Segment(start=0, end=2, text="Genade is een geschenk")]))
    return project


def finished(client, pid: str = "clip", seconds: float = 5.0) -> dict:
    limit = time.monotonic() + seconds
    while True:
        status = client.get(f"/projects/{pid}/render-status").json()
        if status["status"] in ("done", "error", "cancelled"):
            return status
        if time.monotonic() > limit:
            raise AssertionError("de render is nooit klaar gekomen")
        time.sleep(0.02)


def shapes_of(client, pid: str = "clip") -> dict[str, dict]:
    return {s["key"]: s for s in client.get(f"/projects/{pid}/delivery").json()["shapes"]}


def test_video_maken_makes_upright_and_the_shapes_the_church_always_wants(client):
    a_project()
    brand = brands.active()
    brand.share = ShareSettings(shapes=["4x5"])
    brands.save(brand)
    assert client.post("/projects/clip/render").status_code == 200
    assert finished(client)["status"] == "done"
    assert client.made == [("final.mp4", 1080, 1920), ("final-4x5.mp4", 1080, 1350)]
    state = shapes_of(client)
    assert state["9x16"]["ready"] and state["4x5"]["ready"] and not state["1x1"]["ready"]
    assert state["4x5"]["always"] and not state["1x1"]["always"]


def test_one_shape_can_be_made_on_its_own_afterwards(client):
    a_project()
    client.post("/projects/clip/render")
    finished(client)
    answer = client.post("/projects/clip/render", json={"shapes": ["1x1"]})
    assert answer.status_code == 200
    finished(client)
    assert client.made[-1] == ("final-1x1.mp4", 1080, 1080)
    assert shapes_of(client)["1x1"]["ready"]


def test_asking_for_a_shape_that_does_not_exist_is_refused(client):
    a_project()
    assert client.post("/projects/clip/render", json={"shapes": ["16x9"]}).status_code == 400


def test_a_shape_made_before_a_fix_says_it_is_out_of_date(client):
    a_project()
    client.post("/projects/clip/render", json={"shapes": ["9x16", "4x5"]})
    finished(client)
    assert not any(s["stale"] for s in shapes_of(client).values())
    client.put("/projects/clip/transcript", json={"language": "nl", "segments": [
        {"start": 0, "end": 2, "text": "Genade is een cadeau"}]})
    state = shapes_of(client)
    assert state["9x16"]["stale"] and state["4x5"]["stale"]


def test_a_clip_that_gets_its_own_copy_of_the_footage_is_still_the_same_clip():
    """Cleaning up the recording moves the footage; it does not change the video."""
    project = Project(id="p", createdAt="x", sourceInfo=VideoInfo(width=1920, height=1080, duration=30, fps=25))
    brand = brands.Brand(id="b", name="B")
    before = formats.recipe(project, Transcript(), brand)
    project.sourceVideo = "source.mp4"
    project.sourceInfo = VideoInfo(width=1920, height=1080, duration=29.98, fps=25)
    assert formats.recipe(project, Transcript(), brand) == before


def test_a_different_end_screen_is_a_different_video():
    project = Project(id="p", createdAt="x")
    brand = brands.Brand(id="b", name="B")
    before = formats.recipe(project, Transcript(), brand)
    brand.church.churchName = "Andere Kerk"
    assert formats.recipe(project, Transcript(), brand) != before


def test_each_shape_downloads_under_its_own_name(client):
    a_project()
    client.post("/projects/clip/render", json={"shapes": ["9x16", "1x1"]})
    finished(client)
    upright = client.get("/projects/clip/output")
    square = client.get("/projects/clip/output?shape=1x1")
    assert upright.status_code == square.status_code == 200
    assert 'filename="genade-is-geen-beloning.mp4"' in upright.headers["content-disposition"]
    assert 'filename="genade-is-geen-beloning-vierkant.mp4"' in square.headers["content-disposition"]
    assert client.get("/projects/clip/output?shape=4x5").status_code == 404


def test_the_message_says_which_shape_when_there_is_more_than_one(client, monkeypatch):
    seen: list[str] = []
    original = main.renderer.render_video

    def watching(*args, **kwargs):
        told = kwargs["on_progress"]
        kwargs["on_progress"] = lambda f, m: (told(f, m), seen.append(main.jobs.get("clip").message))
        return original(*args, **kwargs)

    monkeypatch.setattr(main.renderer, "render_video", watching)
    a_project()
    client.post("/projects/clip/render", json={"shapes": ["9x16", "4x5"]})
    finished(client)
    assert seen[0].startswith("Staand 9:16 · ") and seen[1].startswith("Tijdlijn 4:5 · ")


def test_the_window_knows_when_nothing_new_can_be_made(client):
    project = a_project()
    (models.project_dir(project.id) / "source.mp4").unlink()
    assert client.get("/projects/clip/delivery").json()["canMake"] is False
