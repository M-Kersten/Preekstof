"""The zip a volunteer attaches to a mail: it names the cause, and it holds no key.

The roadmap asks for three failures staged on purpose. They are here, each one producing a
report whose first page says what went wrong, and none of the three carrying the key.
"""

import json
import zipfile
from io import BytesIO

import pytest
from fastapi.testclient import TestClient

from backend import diagnose, logbook, main, models
from backend.models import Service, VideoInfo

KEY = "sk-ant-api03-AAAABBBBCCCCDDDDEEEEFFFFGGGG"


@pytest.fixture
def alone(tmp_path, monkeypatch):
    """A tree of its own: its own services, its own config.env, its own logs."""
    services = tmp_path / "services"
    services.mkdir()
    monkeypatch.setattr(models, "SERVICES_DIR", services)
    monkeypatch.setattr(main, "SERVICES_DIR", services, raising=False)
    monkeypatch.setattr(diagnose, "SERVICES_DIR", services)
    monkeypatch.setattr(diagnose, "CONFIG", tmp_path / "config.env")
    monkeypatch.setattr(logbook, "LOGS", tmp_path / "logs")
    monkeypatch.setattr(logbook, "CURRENT", tmp_path / "logs" / "preekstof.log")
    (tmp_path / "logs").mkdir()
    return tmp_path


def opened(data: bytes) -> dict[str, str]:
    with zipfile.ZipFile(BytesIO(data)) as z:
        return {name: z.read(name).decode("utf-8") for name in z.namelist()}


def a_service(sid: str, **fields) -> Service:
    folder = models.SERVICES_DIR / sid
    (folder / "work").mkdir(parents=True, exist_ok=True)
    service = Service(id=sid, createdAt="2026-09-06T10:00:00+00:00", title="Kerkdienst", **fields)
    models.save_service(service)
    return service


# --- the three failures the roadmap names -----------------------------------------


def test_no_key_names_itself_on_the_first_page(alone, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    said = opened(diagnose.build("Er is geen sleutel ingesteld."))["melding.txt"]
    assert "geen sleutel" in said.lower()
    assert "Momenten zoeken" in said, "the readiness check says the same thing on its own"


def test_a_recording_that_cannot_be_read_names_itself(alone):
    a_service("service-stuk", status="error",
              error="Wat er binnenkwam is geen video die de app kan lezen: moov atom not found")
    kept = opened(diagnose.build("Wat er binnenkwam is geen video die de app kan lezen: "
                                 "moov atom not found", "service-stuk"))
    assert "moov atom not found" in kept["melding.txt"]
    assert "service-stuk" in kept["melding.txt"]
    assert json.loads(kept["dienst.json"])["status"] == "error"


def test_a_full_disk_names_itself(alone, monkeypatch):
    class Nearly:
        total, used, free = int(500e9), int(499.8e9), int(0.2e9)

    monkeypatch.setattr(diagnose.shutil, "disk_usage", lambda *_: Nearly)
    monkeypatch.setattr("backend.health.shutil.disk_usage", lambda *_: Nearly)
    said = opened(diagnose.build("De schijf zit vol."))["melding.txt"]
    assert "0.2" in said
    assert "Schijfruimte" in said


# --- and none of the three carries the key ----------------------------------------


@pytest.mark.parametrize("trouble, sid", [
    ("Er is geen sleutel ingesteld.", None),
    (f"De API weigerde {KEY}", None),
    ("moov atom not found", "service-stuk"),
])
def test_no_report_ever_carries_the_key(alone, monkeypatch, trouble, sid):
    monkeypatch.setenv("ANTHROPIC_API_KEY", KEY)
    diagnose.CONFIG.write_text(f"ANTHROPIC_API_KEY={KEY}\nLLM_EFFORT=medium\n", encoding="utf-8")
    logbook.begin()
    print(f"de aanvraag met {KEY} liep vast")
    if sid:
        a_service(sid, status="error", error=f"mislukt met {KEY}")
    for name, said in opened(diagnose.build(trouble, sid)).items():
        assert "sk-ant-" not in said, f"{name} carries the key"
        assert KEY not in said, f"{name} carries the key"


# --- what is in it, and what deliberately is not ----------------------------------


def test_the_report_opens_on_the_cause_and_the_machine(alone):
    said = opened(diagnose.build("Uitschrijven liep vast"))["melding.txt"]
    assert said.startswith("Preekstof ")
    assert "Uitschrijven liep vast" in said
    assert "besturingssysteem" in said and "versie" in said


def test_a_report_without_a_stated_cause_says_so_rather_than_being_blank(alone):
    assert "gereedheidspaneel" in opened(diagnose.build())["melding.txt"]


def test_the_settings_come_along_with_their_comments(alone):
    diagnose.CONFIG.write_text("# de sleutel van onze kerk\nLLM_EFFORT=high\n", encoding="utf-8")
    said = opened(diagnose.build())["instellingen.txt"]
    assert "# de sleutel van onze kerk" in said
    assert "wat de app hiervan gemaakt heeft" in said


def test_a_missing_config_is_not_a_reason_to_refuse_a_report(alone):
    assert "geen config.env" in opened(diagnose.build())["instellingen.txt"]


def test_the_written_out_text_is_left_out_of_the_service(alone):
    """It is the largest thing in the folder and the most personal."""
    a_service("service-1", status="error", transcript="transcript.json", error="iets")
    said = json.loads(opened(diagnose.build("iets", "service-1"))["dienst.json"])
    assert "transcript" not in said
    assert "let op" in " ".join(said)


def test_a_service_that_is_gone_still_gives_a_report(alone):
    kept = opened(diagnose.build("iets", "service-weg"))
    assert "melding.txt" in kept
    assert "dienst.json" not in kept


def test_the_logbook_rides_along(alone):
    logbook.begin()
    print("hier ging het mis")
    assert "hier ging het mis" in opened(diagnose.build())["logboek.txt"]


def test_an_empty_logbook_says_so_rather_than_being_an_empty_file(alone):
    assert "niets opgeschreven" in opened(diagnose.build())["logboek.txt"]


# --- through the endpoint a volunteer presses -------------------------------------


@pytest.fixture
def client(alone):
    with TestClient(main.app) as running:
        yield running


def test_the_button_hands_back_a_zip_with_a_name_you_can_mail(client):
    answer = client.get("/diagnose", params={"trouble": "Uitschrijven liep vast"})
    assert answer.status_code == 200
    assert answer.headers["content-type"] == "application/zip"
    assert "preekstof-melding-" in answer.headers["content-disposition"]
    assert "melding.txt" in opened(answer.content)


def test_naming_a_service_puts_that_service_in_it(client):
    a_service("service-1", status="error", error="iets",
              sourceInfo=VideoInfo(width=1920, height=1080, duration=60, fps=25,
                                   videoCodec="h264", hasAudio=True, audioCodec="aac",
                                   audioSampleRate=48000, audioChannels=2))
    kept = opened(client.get("/diagnose", params={"service": "service-1"}).content)
    assert json.loads(kept["dienst.json"])["id"] == "service-1"
    assert "service-1" in kept["melding.txt"]


def test_naming_a_service_that_does_not_exist_is_not_an_error(client):
    """A volunteer clicking after a service was cleaned up still gets their report."""
    answer = client.get("/diagnose", params={"service": "../../etc", "trouble": "iets"})
    assert answer.status_code == 200
    assert "dienst.json" not in opened(answer.content)
