"""The house style: set the subtitles and the logo once, not once per clip."""

import pytest
from fastapi.testclient import TestClient

from backend import brands, clips, house, main, models
from backend.models import ChurchInfo, Project, Style, Watermark


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


def a_clip(name: str, made: bool = False, **fields) -> Project:
    folder = models.project_dir(name)
    (folder / "output").mkdir(parents=True, exist_ok=True)
    if made:
        (folder / "output" / "final.mp4").write_bytes(b"made")
    project = house.dress(Project(id=name, createdAt="2026-10-08T10:00:00", **fields))
    models.save_project(project)
    return project


BIG = Style(fontSize=90, color="#FFE08A")
LOGO = Watermark(file="kerk.png", corner="topLeft")


def test_a_change_in_one_clip_goes_to_the_others_and_to_the_next(folders):
    first, second, third = a_clip("a"), a_clip("b"), a_clip("c")
    along = house.wear(first, "style", BIG)
    assert sorted(along) == ["b", "c"]
    assert models.load_project("b").style == BIG
    assert brands.active().subtitleStyle == BIG
    assert a_clip("d").style == BIG, "a clip made later starts from it too"


def test_a_finished_clip_keeps_the_look_it_was_made_with(folders):
    first, done = a_clip("a"), a_clip("b", made=True)
    house.wear(first, "watermark", LOGO)
    assert models.load_project("b").watermark == done.watermark
    assert brands.active().watermark == LOGO


def test_a_clip_that_already_looked_different_is_left_alone(folders):
    """From before the house style: whatever it was given then was given on purpose."""
    a_clip("a")
    other = a_clip("b")
    other.style = Style(fontSize=50)
    models.save_project(other)
    house.wear(models.load_project("a"), "style", BIG)
    assert models.load_project("b").style == Style(fontSize=50)


def test_a_clip_that_keeps_its_own_shares_nothing(folders):
    special, plain = a_clip("a"), a_clip("b")
    house.keep_own(special, "style", True)
    assert house.wear(models.load_project("a"), "style", BIG) == []
    assert brands.active().subtitleStyle == Style()
    assert models.load_project("b").style == Style()
    house.wear(models.load_project("b"), "style", Style(fontSize=70))
    assert models.load_project("a").style == BIG, "and nothing comes to it"


def test_letting_go_of_its_own_look_puts_the_house_style_back(folders):
    special = a_clip("a", own=["watermark"])
    special.watermark = LOGO
    models.save_project(special)
    back = house.keep_own(models.load_project("a"), "watermark", False)
    assert back.own == [] and back.watermark == Watermark()


def test_saving_the_same_look_again_touches_nothing(folders):
    a_clip("a")
    before = brands.path_for("kerk").stat().st_mtime_ns
    assert house.wear(models.load_project("a"), "style", Style()) == []
    assert brands.path_for("kerk").stat().st_mtime_ns == before, "an unchanged brand does not rebuild the end screen"


def test_a_clip_being_made_right_now_is_left_alone(folders):
    a_clip("a"), a_clip("b")
    house.wear(models.load_project("a"), "style", BIG, busy=lambda other: other == "b")
    assert models.load_project("b").style == Style()


def test_a_clip_cut_from_a_service_starts_from_the_house_style(folders, monkeypatch):
    brand = brands.active()
    brand.subtitleStyle, brand.watermark = BIG, LOGO
    brands.save(brand)
    info = models.VideoInfo(width=1920, height=1080, duration=600.0, fps=25.0, videoCodec="h264",
                            hasAudio=True, audioCodec="aac", audioSampleRate=48000, audioChannels=2)
    origin = models.ClipOrigin(serviceId="s", candidateId="c", start=10.0, end=40.0)
    project = clips.create_clip(folders / "dienst.mp4", 10.0, 40.0, origin=origin, source_info=info)
    assert project.style == BIG and project.watermark == LOGO
    assert models.load_project(project.id).style == BIG


def test_the_endpoint_shares_and_the_switch_keeps_apart(folders, monkeypatch):
    a_clip("a"), a_clip("b")
    client = TestClient(main.app)
    assert client.put("/projects/a/style", json=BIG.model_dump()).status_code == 200
    assert models.load_project("b").style == BIG
    answer = client.put("/projects/b/own", json={"part": "style", "own": True})
    assert answer.status_code == 200 and answer.json()["own"] == ["style"]


def test_saving_the_brand_window_does_not_put_an_old_house_style_back(folders):
    """The brand window sends the whole brand, loaded before the change in a clip."""
    client = TestClient(main.app)
    window = client.get("/brands/kerk").json()
    a_clip("a")
    house.wear(models.load_project("a"), "style", BIG)
    house.wear(models.load_project("a"), "watermark", LOGO)
    window["church"]["churchName"] = "De Nieuwe Kerk"
    window["outro"]["generate"] = False  # no FFmpeg needed for this
    assert client.put("/brands/kerk", json=window).status_code == 200
    kept = brands.active()
    assert kept.church.churchName == "De Nieuwe Kerk"
    assert kept.subtitleStyle == BIG and kept.watermark == LOGO
