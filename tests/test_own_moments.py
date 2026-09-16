"""Cutting your own moment out of the transcript while the search is still running.

Two things write to the same list: somebody reading the transcript, and a search that
started a minute ago and holds the service as it was then. Neither may throw the other away.
"""

import time
from datetime import datetime, timezone

import pytest
from fastapi.testclient import TestClient

from backend import discovery, main, models
from backend.models import ClipCandidate, Service, VideoInfo


@pytest.fixture
def client(tmp_path, monkeypatch):
    folder = tmp_path / "services"
    folder.mkdir()
    monkeypatch.setattr(models, "SERVICES_DIR", folder)
    monkeypatch.setattr(main, "SERVICES_DIR", folder)
    with TestClient(main.app) as running:
        yield running


@pytest.fixture
def service(client):
    sid = "service-1"
    models.service_dir(sid).mkdir(parents=True, exist_ok=True)
    s = Service(id=sid, createdAt=datetime.now(timezone.utc).isoformat(timespec="seconds"),
                status="transcribed", sourceVideo="source.mp4")
    s.sourceInfo = VideoInfo(width=1280, height=720, duration=3600, fps=25, videoCodec="h264",
                             hasAudio=True, audioCodec="aac", audioSampleRate=48000, audioChannels=2)
    (models.service_dir(sid) / "source.mp4").write_bytes(b"x")
    models.save_service(s)
    return s


def found(cid: str, start: float = 100.0) -> dict:
    return ClipCandidate(id=cid, start=start, end=start + 40, title=f"Gevonden {cid}").model_dump()


def finished(service_id: str, seconds: float = 5.0) -> None:
    """Wait for the background job to be over, without guessing how long it takes."""
    until = time.monotonic() + seconds
    while time.monotonic() < until:
        if main.jobs.get(service_id).status in ("done", "error", "cancelled"):
            return
        time.sleep(0.01)
    raise AssertionError("de analyse is nooit klaar gekomen")


def cut(start: float = 500.0, title: str = "Zelf geknipt") -> dict:
    """What the browser sends for a fragment somebody cut out of the transcript: no id yet."""
    return ClipCandidate(id="", start=start, end=start + 60, title=title, source="self",
                         selected=True).model_dump()


# --- what the browser sends ---------------------------------------------------------

def test_a_fragment_cut_by_hand_gets_a_name_of_its_own(client, service):
    back = client.put(f"/services/{service.id}/candidates", json=[cut()]).json()
    assert len(back) == 1
    assert back[0]["id"] == "eigen-01"
    assert back[0]["source"] == "self"


def test_two_fragments_cut_in_a_row_do_not_collide(client, service):
    client.put(f"/services/{service.id}/candidates", json=[cut(500)])
    back = client.put(f"/services/{service.id}/candidates",
                      json=[ClipCandidate(id="eigen-01", start=500, end=560, title="a", source="self").model_dump(),
                            cut(900, "b")]).json()
    assert [c["id"] for c in back] == ["eigen-01", "eigen-02"]


def test_a_name_that_is_already_taken_is_stepped_over(client, service):
    """Two tabs on the same service must not both end up calling theirs eigen-01."""
    client.put(f"/services/{service.id}/candidates", json=[cut(500)])
    back = client.put(f"/services/{service.id}/candidates",
                      json=[ClipCandidate(id="eigen-01", start=500, end=560, title="a", source="self").model_dump(),
                            cut(900), cut(1500)]).json()
    assert sorted(c["id"] for c in back) == ["eigen-01", "eigen-02", "eigen-03"]


def test_the_same_name_twice_is_refused(client, service):
    twice = [found("candidate-01"), found("candidate-01", 300)]
    assert client.put(f"/services/{service.id}/candidates", json=twice).status_code == 400


def test_an_impossible_range_is_still_refused(client, service):
    bad = ClipCandidate(id="", start=90, end=40, title="achterstevoren", source="self").model_dump()
    answer = client.put(f"/services/{service.id}/candidates", json=[bad])
    assert answer.status_code == 400
    assert "achterstevoren" in answer.json()["detail"]


# --- the two lists not overwriting each other ------------------------------------------

def test_a_save_from_before_the_search_came_back_keeps_what_it_found(client, service):
    """The browser sends the list it knew. The search landed since. Both survive."""
    service.candidates = [ClipCandidate(id="candidate-01", start=100, end=140, title="Gevonden")]
    models.save_service(service)

    stale = client.put(f"/services/{service.id}/candidates", json=[cut(500)]).json()
    assert [c["id"] for c in stale] == ["eigen-01", "candidate-01"]
    assert [c["source"] for c in stale] == ["self", "found"]


def test_removing_your_own_fragment_actually_removes_it(client, service):
    client.put(f"/services/{service.id}/candidates", json=[cut(500), cut(900)])
    left = client.put(f"/services/{service.id}/candidates",
                      json=[ClipCandidate(id="eigen-01", start=500, end=560, title="a",
                                          source="self").model_dump()]).json()
    assert [c["id"] for c in left] == ["eigen-01"], "the one that was let go stays gone"


def test_the_search_leaves_a_hand_cut_fragment_alone(client, service, monkeypatch):
    """The run started before the fragment existed and must not write over it."""
    models.save_service_transcript(service, models.Transcript(language="nl", segments=[
        models.Segment(start=0, end=5, text="Een zin uit de dienst.")]))

    def search(*_args, **_kwargs):
        # While the model is thinking, somebody cuts a fragment out of the transcript.
        client.put(f"/services/{service.id}/candidates", json=[cut(500)])
        return discovery.Result(candidates=[ClipCandidate(id="candidate-01", start=100, end=140,
                                                          title="Gevonden")])

    monkeypatch.setattr(discovery, "discover", search)
    monkeypatch.setattr(discovery, "check_provider", lambda: None)
    client.post(f"/services/{service.id}/analyze")
    finished(service.id)
    after = models.load_service(service.id).candidates
    assert [c.id for c in after] == ["eigen-01", "candidate-01"]
    assert after[0].title == "Zelf geknipt", "and unchanged"


def test_looking_again_never_costs_you_your_own_fragments(client, service, monkeypatch):
    service.candidates = [ClipCandidate(id="eigen-01", start=500, end=560, title="Mijn moment",
                                        source="self", selected=True)]
    models.save_service(service)
    kept = main.keep_own(service.id, [ClipCandidate(id="candidate-01", start=100, end=140, title="Nieuw")])
    assert [c.id for c in kept] == ["eigen-01", "candidate-01"]
    assert kept[0].selected is True


def test_a_hand_cut_fragment_comes_first(client, service):
    """A ranking it was never part of should not push it down the page."""
    kept = main.keep_own(service.id, [])
    assert kept == []
    service.candidates = [ClipCandidate(id="eigen-01", start=3000, end=3060, title="Laat in de dienst",
                                        source="self")]
    models.save_service(service)
    kept = main.keep_own(service.id, [ClipCandidate(id="candidate-01", start=100, end=140, title="Vroeg")])
    assert [c.id for c in kept] == ["eigen-01", "candidate-01"]


# --- when it may be saved ---------------------------------------------------------------

def test_saving_while_the_search_runs_is_allowed(client, service):
    """The whole point: those minutes are for reading the transcript and cutting your own."""
    service.status = "analyzing"
    models.save_service(service)
    assert client.put(f"/services/{service.id}/candidates", json=[cut(500)]).status_code == 200


def test_saving_while_the_clips_are_being_made_is_not(client, service):
    """process_selected walks the list as it goes; changing it underneath would lose a clip."""
    service.status = "processing"
    models.save_service(service)
    assert client.put(f"/services/{service.id}/candidates", json=[cut(500)]).status_code == 409


def test_an_old_service_has_no_hand_cut_moments_in_it(client, service):
    """Everything written before this existed was found by the search."""
    service.candidates = [ClipCandidate(id="candidate-01", start=100, end=140, title="Van vorige week")]
    models.save_service(service)
    assert models.load_service(service.id).candidates[0].source == "found"
