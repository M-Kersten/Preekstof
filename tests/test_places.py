"""A church's work lives outside the app folder, and what was inside moves out once."""

from pathlib import Path

from backend import places


def an_old_install(app: Path) -> None:
    (app / "projects" / "project-1" / "output").mkdir(parents=True)
    (app / "projects" / "project-1" / "project.json").write_text("{}")
    (app / "projects" / ".gitkeep").write_text("")
    (app / "services" / "service-1").mkdir(parents=True)
    (app / "services" / "service-1" / "service.json").write_text("{}")
    (app / "config.env").write_text("ANTHROPIC_API_KEY=sk-ant-x\n")
    templates = app / "templates"
    (templates / "brands").mkdir(parents=True)
    (templates / "brands" / "kerk.json").write_text("{}")
    (templates / "logos").mkdir()
    (templates / "logos" / ".gitkeep").write_text("")
    (templates / "logos" / "kerk.png").write_bytes(b"png")
    (templates / "fonts").mkdir()
    (templates / "fonts" / "Inter-Bold.ttf").write_bytes(b"font")
    (templates / "woordenlijst.json").write_text("{}")
    (templates / "outro-achtergrond.jpg").write_bytes(b"jpg")
    (templates / "church.example.json").write_text("{}")


def test_the_churchs_work_moves_and_what_ships_stays(tmp_path):
    app, data = tmp_path / "app", tmp_path / "Preekstof"
    an_old_install(app)
    moved = places.move_in(app, data)
    assert (data / "projects" / "project-1" / "project.json").is_file()
    assert (data / "services" / "service-1" / "service.json").is_file()
    assert (data / "config.env").read_text().startswith("ANTHROPIC_API_KEY")
    assert (data / "templates" / "brands" / "kerk.json").is_file()
    assert (data / "templates" / "logos" / "kerk.png").is_file()
    assert (data / "templates" / "woordenlijst.json").is_file()
    assert (data / "templates" / "outro-achtergrond.jpg").is_file()
    assert not (app / "projects" / "project-1").exists() and not (app / "config.env").exists()
    # What comes with a download stays with the download.
    assert (app / "templates" / "fonts" / "Inter-Bold.ttf").is_file()
    assert (app / "templates" / "church.example.json").is_file()
    assert (app / "projects" / ".gitkeep").is_file() and (app / "templates" / "logos" / ".gitkeep").is_file()
    assert not (data / "templates" / "fonts").exists()
    assert len(moved) == 7


def test_nothing_already_in_the_new_place_is_overwritten(tmp_path):
    app, data = tmp_path / "app", tmp_path / "Preekstof"
    an_old_install(app)
    data.mkdir()
    (data / "config.env").write_text("NEWER=1\n")
    places.move_in(app, data)
    assert (data / "config.env").read_text() == "NEWER=1\n"
    assert (app / "config.env").is_file(), "the old one stays where it was rather than being lost"


def test_moving_twice_moves_nothing_the_second_time(tmp_path):
    app, data = tmp_path / "app", tmp_path / "Preekstof"
    an_old_install(app)
    places.move_in(app, data)
    assert places.move_in(app, data) == []


def test_an_app_unpacked_into_the_data_folder_moves_nothing(tmp_path):
    an_old_install(tmp_path)
    assert places.move_in(tmp_path, tmp_path) == []
    assert (tmp_path / "config.env").is_file()


def test_the_data_folder_can_be_put_elsewhere(monkeypatch, tmp_path):
    monkeypatch.setenv("PREEKSTOF_DATA", str(tmp_path / "ergens"))
    assert places.data_home() == tmp_path / "ergens"
    monkeypatch.delenv("PREEKSTOF_DATA")
    assert places.data_home() == Path.home() / "Preekstof"


def test_the_tests_never_touch_real_data():
    from backend import models
    assert "preekstof-tests-" in str(models.DATA_DIR)
    assert models.PROJECTS_DIR.parent == models.DATA_DIR


def test_one_address_serves_both_folders():
    from fastapi.testclient import TestClient

    from backend import main, models

    logos = models.OWN_TEMPLATES / "logos"
    logos.mkdir(parents=True, exist_ok=True)
    (logos / "eigen.png").write_bytes(b"own logo")
    client = TestClient(main.app)
    assert client.get("/templates/logos/eigen.png").content == b"own logo"
    assert client.get("/templates/fonts/Inter-Bold.ttf").status_code == 200, "a font that ships"
    assert client.get("/templates/../backend/main.py").status_code == 404
    assert client.get("/templates/%2e%2e/config.env").status_code == 404
