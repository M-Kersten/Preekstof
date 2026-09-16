"""Saving when Windows will not let you.

Windows refuses to rename onto a file that anything else has open, and a virus scanner
reading the file we have just written counts. The rename comes back as PermissionError
(WinError 5), which on a church laptop looked like this: looking for moments loaded for ever,
because the failure happened inside the handler that was writing down a different failure, so
the real error was thrown away and the service stayed "analyzing" on disk.

None of this can be reproduced on Linux by doing it, so os.replace is made to refuse instead.
"""

import os
import threading

import pytest
from fastapi.testclient import TestClient

from backend import main, models
from backend.models import write_atomic


class Refuses:
    """os.replace as Windows does it while something else has the file open."""

    def __init__(self, times: int):
        self.left = times
        self.tries = 0
        self.real = os.replace

    def __call__(self, src, dst):
        self.tries += 1
        if self.left > 0:
            self.left -= 1
            raise PermissionError(5, "Access is denied")
        return self.real(src, dst)


@pytest.fixture
def quick(monkeypatch):
    """The waiting between tries, without the waiting.

    The wait itself rather than time.sleep: models.time is the one time module everybody
    has, and a test that blunts it also blunts the waiting the test does for a thread.
    """
    monkeypatch.setattr(models, "REPLACE_WAIT", 0.0)


# --- writing through it -----------------------------------------------------------


def test_a_lock_that_lets_go_is_waited_out(tmp_path, monkeypatch, quick):
    refuses = Refuses(times=3)
    monkeypatch.setattr(models.os, "replace", refuses)
    write_atomic(tmp_path / "service.json", "de tekst")
    assert (tmp_path / "service.json").read_text(encoding="utf-8") == "de tekst"
    assert refuses.tries == 4, "it gave up too early or tried too often"


def test_a_lock_that_never_lets_go_is_written_over(tmp_path, monkeypatch, quick):
    """Losing the write and leaving the app stuck is worse than one unprotected write."""
    monkeypatch.setattr(models.os, "replace", Refuses(times=999))
    write_atomic(tmp_path / "service.json", "de tekst")
    assert (tmp_path / "service.json").read_text(encoding="utf-8") == "de tekst"


def test_nothing_is_left_lying_around_either_way(tmp_path, monkeypatch, quick):
    for times in (0, 3, 999):
        monkeypatch.setattr(models.os, "replace", Refuses(times=times))
        write_atomic(tmp_path / "service.json", f"poging {times}")
        assert [p.name for p in tmp_path.iterdir()] == ["service.json"]


def refuse_only(target, monkeypatch):
    """Let the temporary file be written and refuse the one write that lands on `target`."""
    real = models.Path.write_text

    def maybe(self, *args, **kwargs):
        if self == target:
            raise PermissionError(5, "Access is denied")
        return real(self, *args, **kwargs)

    monkeypatch.setattr(models.Path, "write_text", maybe)


def test_a_file_that_cannot_be_written_at_all_says_what_is_wrong(tmp_path, monkeypatch, quick):
    monkeypatch.setattr(models.os, "replace", Refuses(times=999))
    refuse_only(tmp_path / "service.json", monkeypatch)
    with pytest.raises(OSError) as stopped:
        write_atomic(tmp_path / "service.json", "de tekst")
    assert "vast" in str(stopped.value), "the message has to name the cause"


def test_two_threads_saving_the_same_file_do_not_fight_over_one_temporary(tmp_path):
    """The other half of it: a job thread and a request thread used to share one .tmp."""
    seen: list[str] = []
    real = models.os.replace

    def watch(src, dst):
        seen.append(os.path.basename(src))
        return real(src, dst)

    target = tmp_path / "service.json"
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(models.os, "replace", watch)
        threads = [threading.Thread(target=write_atomic, args=(target, f"schrijver {i}"))
                   for i in range(8)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()
    assert len(set(seen)) == len(seen), f"two writers shared a temporary file: {seen}"
    assert target.read_text(encoding="utf-8").startswith("schrijver")


# --- and what the page is told ----------------------------------------------------


@pytest.fixture
def client(tmp_path, monkeypatch):
    folder = tmp_path / "services"
    folder.mkdir()
    monkeypatch.setattr(models, "SERVICES_DIR", folder)
    with TestClient(main.app) as running:
        yield running


def a_service(status: str = "analyzing"):
    service = models.new_service()
    service.status = status  # type: ignore[assignment]
    models.save_service(service)
    return service


def test_a_service_that_says_busy_with_nothing_running_is_not_busy(client):
    """What the endless loading was: the file said analyzing, the job had already failed."""
    service = a_service("analyzing")
    job = main.jobs.get(service.id)
    job.status, job.error = "error", "De sleutel voor Claude ontbreekt"
    main.jobs._jobs[service.id] = job

    answer = client.get(f"/services/{service.id}/status").json()
    assert answer["status"] == "error"
    assert answer["error"] == "De sleutel voor Claude ontbreekt"
    assert answer["job"] is None


def test_a_job_that_was_stopped_puts_the_service_back_a_step(client):
    service = a_service("analyzing")
    job = main.jobs.get(service.id)
    job.status = "cancelled"
    main.jobs._jobs[service.id] = job
    assert client.get(f"/services/{service.id}/status").json()["status"] == "transcribed"


def test_a_job_that_has_not_started_yet_is_left_alone(client):
    """There is a moment between writing "analyzing" and the thread starting."""
    service = a_service("analyzing")
    assert client.get(f"/services/{service.id}/status").json()["status"] == "analyzing"


def test_a_running_job_is_reported_as_running(client):
    service = a_service("analyzing")
    job = main.jobs.get(service.id)
    job.status, job.message = "running", "Bezig"
    main.jobs._jobs[service.id] = job
    answer = client.get(f"/services/{service.id}/status").json()
    assert answer["status"] == "analyzing" and answer["job"]["status"] == "running"


def test_the_real_error_survives_a_status_that_cannot_be_written(client, monkeypatch, quick):
    """The bug itself: the handler fell over and took the error it was handling with it."""
    service = a_service("transcribed")

    def cross(*_a, **_k):
        raise RuntimeError("Er is geen Claude API-sleutel ingesteld")

    monkeypatch.setattr(main, "set_status", lambda *a, **k: (_ for _ in ()).throw(
        PermissionError(5, "Access is denied")))
    main.remember(service, "error", "Er is geen Claude API-sleutel ingesteld")  # must not raise


def test_a_failing_status_write_still_lets_the_job_record_the_failure(client, monkeypatch, quick):
    """Exactly what happened on the church laptop, with the lock never letting go."""
    service = a_service("transcribed")

    def work(job, service):
        # From here on the disk refuses, which is where the handler used to fall over.
        monkeypatch.setattr(models.os, "replace", Refuses(times=999))
        refuse_only(models.service_dir(service.id) / "service.json", monkeypatch)
        raise RuntimeError("Er is geen Claude API-sleutel ingesteld")

    main.run_service_job(service, "analyzing", "ready", work)
    for _ in range(200):
        if main.jobs.get(service.id).status != "running":
            break
        __import__("time").sleep(0.02)
    job = main.jobs.get(service.id)
    assert job.status == "error"
    assert "Claude API-sleutel" in (job.error or ""), f"the real error was lost: {job.error}"


def test_work_that_succeeded_is_not_called_a_failure_by_a_stuck_disk(client, monkeypatch, quick):
    """The likeliest reading of the report: the analysis was done and only the last write failed."""
    service = a_service("transcribed")
    done: list[str] = []

    def work(job, service):
        done.append(service.id)
        monkeypatch.setattr(models.os, "replace", Refuses(times=999))
        refuse_only(models.service_dir(service.id) / "service.json", monkeypatch)

    main.run_service_job(service, "analyzing", "ready", work)
    for _ in range(300):
        if main.jobs.get(service.id).status != "running":
            break
        threading.Event().wait(0.02)
    assert done, "the work never ran"
    assert main.jobs.get(service.id).status == "done", "a bookkeeping write turned it into a failure"
