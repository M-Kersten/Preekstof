"""Shared fixtures. Tests import the backend package, so the repo root must be importable."""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

FIXTURES = Path(__file__).parent / "fixtures"


import time  # noqa: E402

import pytest  # noqa: E402


@pytest.fixture(autouse=True)
def jobs_finish_inside_their_test(monkeypatch):
    """Wait for background work a test started, before its folders are put back.

    A test that starts a job and checks only the answer returns while the job runs on. Once
    the folders it pointed at are put back, the job saved its service into the next test's
    folder, or into the real services/ folder. Asking for monkeypatch makes this run first
    on the way out, while the test's folders are still in place.
    """
    yield
    main = sys.modules.get("backend.main")
    if main is None:
        return
    for _ in range(250):
        if not any(job.status == "running" for job in list(main.jobs._jobs.values())):
            return
        time.sleep(0.02)
