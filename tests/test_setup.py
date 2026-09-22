"""The first five minutes, the door the browser left open, and saying which version this is.

Everything here is about a church nobody in this room can see: somebody who cannot open a
terminal, on a machine nobody has touched, who will close the window rather than ask.
"""

import pytest
from fastapi.testclient import TestClient

from backend import brands, discovery, health, main, setup, version


@pytest.fixture
def client(tmp_path, monkeypatch):
    """The app with its own empty config.env and templates folder, never the real ones."""
    templates = tmp_path / "templates"
    (templates / "brands").mkdir(parents=True)
    monkeypatch.setattr(brands, "TEMPLATES_DIR", templates)
    monkeypatch.setattr(brands, "BRANDS_DIR", templates / "brands")
    monkeypatch.setattr(brands, "ACTIVE_FILE", templates / "brands" / "actief.json")
    monkeypatch.setattr(setup, "STATE", templates / "setup.json")
    monkeypatch.setattr(setup, "CONFIG", tmp_path / "config.env")
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    with TestClient(main.app) as running:
        yield running


A_KEY = "sk-ant-api03-" + "a" * 40


@pytest.fixture
def key_works(monkeypatch):
    monkeypatch.setattr(discovery, "try_key", lambda: "claude-opus-5")


# --- the door the browser left open -------------------------------------------------

def test_a_stranger_gets_no_permission(client):
    """Any website open in the same browser used to be able to read a whole service."""
    answer = client.get("/health", headers={"Origin": "https://ergens-anders.nl"})
    assert answer.headers.get("access-control-allow-origin") is None


def test_the_app_itself_still_works(client):
    answer = client.get("/health", headers={"Origin": "http://localhost:8000"})
    assert answer.headers.get("access-control-allow-origin") == "http://localhost:8000"


def test_the_dev_server_is_let_in(client):
    answer = client.get("/health", headers={"Origin": "http://127.0.0.1:5173"})
    assert answer.headers.get("access-control-allow-origin") == "http://127.0.0.1:5173"


def test_the_wildcard_is_gone_and_stays_gone():
    assert "*" not in main.allowed_origins(), "one line away from reading transcripts off localhost"


def test_a_different_port_is_followed(monkeypatch):
    monkeypatch.setenv("PORT", "9100")
    assert "http://localhost:9100" in main.allowed_origins()


def test_an_unusual_setup_can_still_say_so(monkeypatch):
    monkeypatch.setenv("ALLOWED_ORIGINS", "https://kerk.example, https://tweede.example")
    assert main.allowed_origins() == ["https://kerk.example", "https://tweede.example"]


# --- saying which version this is ------------------------------------------------------

def test_the_version_is_in_the_panel_somebody_already_opens(client):
    assert client.get("/health").json()["version"] == version.full()


def test_the_version_is_written_in_one_place_only():
    assert health.report()["version"] == version.full()
    assert main.app.version == version.VERSION


def test_the_version_says_what_stretch_of_the_road_this_is():
    assert version.full().startswith(version.VERSION)
    assert "pilot" in version.full()


# --- what the welcome still has to ask ---------------------------------------------------

def test_a_fresh_install_is_missing_everything(client):
    now = client.get("/setup").json()
    assert now["done"] is False
    assert now["missing"] == ["key", "church", "station"]


def test_a_church_that_does_not_publish_online_is_not_stuck_on_it(client, key_works):
    client.put("/setup/key", json={"key": A_KEY})
    client.put("/setup/church", json={"churchName": "Nieuwe Kerk"})
    client.post("/setup/done", json={"skippedStation": True})
    now = client.get("/setup").json()
    assert now["missing"] == [], "uploading a file by hand is an ordinary way to use this"
    assert now["done"] is True


def test_ollama_needs_no_key_at_all(client, monkeypatch):
    monkeypatch.setattr(discovery, "LLM_PROVIDER", "ollama")
    assert "key" not in client.get("/setup").json()["missing"]


# --- the key ------------------------------------------------------------------------------

def test_a_key_that_answers_is_kept(client, key_works):
    answer = client.put("/setup/key", json={"key": A_KEY})
    assert answer.status_code == 200
    assert answer.json()["hasKey"] is True
    assert A_KEY in setup.CONFIG.read_text(encoding="utf-8")


def test_the_key_is_never_handed_back_out(client, key_works):
    client.put("/setup/key", json={"key": A_KEY})
    for where in ("/setup", "/health"):
        assert A_KEY not in client.get(where).text, f"{where} gives the key away"


def test_something_that_is_not_a_key_is_caught_before_it_costs_anything(client, monkeypatch):
    monkeypatch.setattr(discovery, "try_key",
                        lambda: pytest.fail("no call should be made for an obvious paste error"))
    answer = client.put("/setup/key", json={"key": "mijn wachtwoord"})
    assert answer.status_code == 400
    assert "sk-ant-" in answer.json()["detail"]


def test_a_key_that_is_refused_is_not_written_down(client, monkeypatch):
    def refuse():
        raise RuntimeError("Deze sleutel wordt niet geaccepteerd.")

    monkeypatch.setattr(discovery, "try_key", refuse)
    answer = client.put("/setup/key", json={"key": A_KEY})
    assert answer.status_code == 400
    assert "niet geaccepteerd" in answer.json()["detail"]
    assert client.get("/setup").json()["hasKey"] is False
    assert not setup.CONFIG.exists() or A_KEY not in setup.CONFIG.read_text(encoding="utf-8")


def test_a_refused_key_leaves_the_working_one_alone(client, monkeypatch):
    """Trying a second key and getting it wrong must not lock the church out."""
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-api03-" + "w" * 40)

    def refuse():
        raise RuntimeError("Deze sleutel wordt niet geaccepteerd.")

    monkeypatch.setattr(discovery, "try_key", refuse)
    client.put("/setup/key", json={"key": A_KEY})
    import os

    assert os.environ["ANTHROPIC_API_KEY"] == "sk-ant-api03-" + "w" * 40


def test_the_key_works_without_restarting_the_app(client, key_works, monkeypatch):
    import os

    client.put("/setup/key", json={"key": A_KEY})
    assert os.environ["ANTHROPIC_API_KEY"] == A_KEY, "config.env alone would need a restart"


def test_settings_somebody_tuned_survive_the_welcome(client, key_works):
    setup.CONFIG.write_text("# mijn aantekeningen\nWHISPER_MODEL=medium\nKEEP_WEEKS=8\n", encoding="utf-8")
    client.put("/setup/key", json={"key": A_KEY})
    kept = setup.CONFIG.read_text(encoding="utf-8")
    assert "WHISPER_MODEL=medium" in kept and "KEEP_WEEKS=8" in kept
    assert "# mijn aantekeningen" in kept


def test_a_second_key_replaces_the_first_rather_than_stacking(client, key_works):
    client.put("/setup/key", json={"key": A_KEY})
    other = "sk-ant-api03-" + "b" * 40
    client.put("/setup/key", json={"key": other})
    written = setup.CONFIG.read_text(encoding="utf-8")
    assert written.count("ANTHROPIC_API_KEY=") == 1
    assert other in written and A_KEY not in written


def test_the_key_can_be_taken_back_out(client, key_works):
    client.put("/setup/key", json={"key": A_KEY})
    assert client.delete("/setup/key").json()["hasKey"] is False
    assert A_KEY not in setup.CONFIG.read_text(encoding="utf-8")


# --- the church ----------------------------------------------------------------------------

def test_what_the_welcome_asks_lands_where_the_app_reads_it(client):
    client.put("/setup/church", json={
        "churchName": "Nieuwe Kerk Utrecht", "station": "1341",
        "serviceTimes": ["10:00 Wittevrouwen", " "], "instagram": "@nieuwekerk"})
    church = client.get("/church").json()
    assert church["churchName"] == "Nieuwe Kerk Utrecht"
    assert church["kerkdienstgemistStation"] == "1341"
    assert church["serviceTimes"] == ["10:00 Wittevrouwen"], "an empty line is not a service time"
    assert church["instagram"] == "@nieuwekerk"


def test_filling_in_one_thing_leaves_the_rest_alone(client):
    client.put("/setup/church", json={"churchName": "Nieuwe Kerk", "instagram": "@nk"})
    client.put("/setup/church", json={"station": "1341"})
    church = client.get("/church").json()
    assert church["churchName"] == "Nieuwe Kerk" and church["instagram"] == "@nk"


# --- walking through it, and walking through it again -----------------------------------------

def test_once_it_is_done_the_app_opens_on_the_app(client, key_works):
    client.put("/setup/key", json={"key": A_KEY})
    client.put("/setup/church", json={"churchName": "Nieuwe Kerk", "station": "1341"})
    assert client.post("/setup/done", json={}).json()["done"] is True
    assert client.get("/setup").json()["missing"] == []


def test_it_can_be_opened_again_without_losing_anything(client, key_works):
    client.put("/setup/key", json={"key": A_KEY})
    client.put("/setup/church", json={"churchName": "Nieuwe Kerk", "station": "1341"})
    client.post("/setup/done", json={})
    again = client.post("/setup/reopen").json()
    assert again["done"] is False
    assert again["churchName"] == "Nieuwe Kerk" and again["hasKey"] is True


def test_a_damaged_setup_file_shows_the_welcome_rather_than_falling_over(client):
    setup.STATE.write_text("{ niet eens json", encoding="utf-8")
    assert client.get("/setup").json()["done"] is False
