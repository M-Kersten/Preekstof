"""Throwing away an older version of a fragment, from the list of clips made from a service."""

import pytest
from fastapi.testclient import TestClient

from backend import main, models
from backend.models import ProcessedClip, Project, Service


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(models, "PROJECTS_DIR", tmp_path / "projects")
    monkeypatch.setattr(models, "SERVICES_DIR", tmp_path / "services")
    monkeypatch.setattr(main, "SERVICES_DIR", tmp_path / "services")
    return TestClient(main.app)


def a_clip(project_id: str) -> ProcessedClip:
    folder = models.project_dir(project_id)
    (folder / "output").mkdir(parents=True)
    (folder / "output" / "final.mp4").write_bytes(b"made")
    models.save_project(Project(id=project_id, createdAt="2026-10-08T10:00:00"))
    return ProcessedClip(candidateId="c1", projectId=project_id, title="Genade", start=300, end=345,
                         createdAt="2026-10-08T10:00:00")


def a_service(*clips: ProcessedClip) -> Service:
    (models.service_dir("s1") / "work").mkdir(parents=True)
    service = Service(id="s1", createdAt="2026-10-08T09:00:00", clips=list(clips))
    models.save_service(service)
    return service


def test_an_older_version_goes_with_everything_in_it(client):
    a_service(a_clip("p1"), a_clip("p2"))
    answer = client.delete("/services/s1/clips/p1")
    assert answer.status_code == 200
    assert [c["projectId"] for c in answer.json()["clips"]] == ["p2"]
    assert not models.project_dir("p1").exists()
    assert models.project_dir("p2").is_dir(), "the other version stays"


def test_only_a_clip_of_this_service_can_go_this_way(client):
    a_service(a_clip("p1"))
    a_clip("elsewhere")
    assert client.delete("/services/s1/clips/elsewhere").status_code == 404
    assert models.project_dir("elsewhere").is_dir()
    assert client.delete("/services/s1/clips/..").status_code in (404, 405)


def test_a_clip_being_made_stays(client, monkeypatch):
    a_service(a_clip("p1"))
    monkeypatch.setitem(main.rendering_now, "p1", "9x16")
    assert client.delete("/services/s1/clips/p1").status_code == 409
    assert models.project_dir("p1").is_dir()
