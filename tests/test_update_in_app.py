"""Bijwerken from the readiness panel: the right download, fetched, checked and put ready."""

import hashlib
import json
import zipfile
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend import lifecycle, main, updates
from backend.updates import Asset, Release


def a_download(folder: Path, version: str = "9.9.9", extra: dict | None = None) -> Path:
    """A release zip the way tools/release.py writes one: everything under one folder."""
    archive = folder / f"preekstof-{version}.zip"
    with zipfile.ZipFile(archive, "w") as zipped:
        files = {"launcher.py": "# new", "start.command": "#!/bin/bash\n", "backend/version.py": f'VERSION = "{version}"'}
        files.update(extra or {})
        for name, text in files.items():
            info = zipfile.ZipInfo(f"preekstof-{version}/{name}")
            info.external_attr = (0o755 if name.endswith(".command") else 0o644) << 16
            zipped.writestr(info, text)
    return archive


def a_release(archive: Path, name: str | None = None, digest: str | None = None) -> Release:
    data = archive.read_bytes()
    return Release(version="9.9.9", url="https://github.com/x", assets=[Asset(
        name=name or archive.name, url=archive.as_uri(), size=len(data),
        digest=digest if digest is not None else "sha256:" + hashlib.sha256(data).hexdigest())])


@pytest.fixture
def plain_app(tmp_path, monkeypatch):
    app = tmp_path / "app"
    app.mkdir()
    monkeypatch.setattr(updates, "ROOT", app)
    monkeypatch.setattr(updates, "STAGE", app / ".update")
    monkeypatch.setattr(updates, "DOWNLOADS", tmp_path / "data" / "updates")
    return app


def test_what_kind_of_install_this_is(tmp_path):
    assert updates.kind(tmp_path) == "plain"
    (tmp_path / "bundle.json").write_text(json.dumps({"kind": "mac-arm64"}))
    assert updates.kind(tmp_path) == "mac-arm64"
    (tmp_path / ".git").mkdir()
    assert updates.kind(tmp_path) == "git"


def test_each_install_gets_its_own_download():
    release = Release("1.2.0", "u", assets=[Asset(n, "https://x/" + n) for n in
                                            ("preekstof-1.2.0.zip", "Preekstof-Windows.zip", "Preekstof-Mac.zip")])
    assert updates.asset_for(release, "plain").name == "preekstof-1.2.0.zip"
    assert updates.asset_for(release, "windows-x64").name == "Preekstof-Windows.zip"
    assert updates.asset_for(release, "mac-arm64").name == "Preekstof-Mac.zip"
    assert updates.asset_for(release, "mac-x64") is None, "no Intel download in this release"
    assert updates.asset_for(release, "git") is None


def test_a_git_checkout_is_told_to_pull(tmp_path):
    (tmp_path / ".git").mkdir()
    assert "git pull" in updates.why_not(Release("1.0.0", "u"), tmp_path)


def test_a_new_version_is_put_ready_without_its_outer_folder(plain_app, tmp_path):
    release = a_release(a_download(tmp_path))
    assert updates.stage(release) == "9.9.9"
    new = plain_app / ".update" / "new"
    assert (new / "launcher.py").read_text() == "# new"
    assert (new / "backend" / "version.py").is_file()
    assert (new / "start.command").stat().st_mode & 0o111, "what may run, still may"
    assert updates.staged(plain_app / ".update") == "9.9.9"
    assert not any((tmp_path / "data" / "updates").glob("*.zip")), "the download is cleared away"


def test_a_download_that_does_not_match_its_checksum_is_not_used(plain_app, tmp_path):
    release = a_release(a_download(tmp_path), digest="sha256:" + "0" * 64)
    with pytest.raises(updates.UpdateError, match="klopt niet"):
        updates.stage(release)
    assert updates.staged(plain_app / ".update") is None


def test_a_zip_that_reaches_outside_the_app_is_refused(plain_app, tmp_path):
    archive = tmp_path / "preekstof-9.9.9.zip"
    with zipfile.ZipFile(archive, "w") as zipped:
        zipped.writestr("launcher.py", "x")
        zipped.writestr("../../buiten.txt", "x")
    with pytest.raises(updates.UpdateError, match="buiten"):
        updates.stage(a_release(archive))


def test_something_that_is_not_preekstof_is_not_put_ready(plain_app, tmp_path):
    archive = tmp_path / "preekstof-9.9.9.zip"
    with zipfile.ZipFile(archive, "w") as zipped:
        zipped.writestr("iets/anders.txt", "x")
    with pytest.raises(updates.UpdateError, match="niet uit als Preekstof"):
        updates.stage(a_release(archive))
    assert not (plain_app / ".update").exists()


def test_the_panel_hears_what_there_is(monkeypatch):
    monkeypatch.setattr(updates, "known", lambda max_age=600: Release("99.0.0", "https://x", "## Wat\nNieuw spul"))
    monkeypatch.setattr(updates, "why_not", lambda release, root=None: "")
    said = TestClient(main.app).get("/update").json()
    assert said["newer"] is True and said["latest"]["version"] == "99.0.0"
    assert said["latest"]["headline"] == "Nieuw spul"


def test_restarting_without_a_launcher_says_what_to_do(monkeypatch):
    monkeypatch.setattr(updates, "staged", lambda stage=None: "99.0.0")
    monkeypatch.setattr(lifecycle, "_stop", None)
    answer = TestClient(main.app).post("/update/restart")
    assert answer.status_code == 400 and "zwarte venster" in answer.json()["detail"]


def test_restarting_stops_the_server_after_answering(monkeypatch):
    stopped = []
    monkeypatch.setattr(updates, "staged", lambda stage=None: "99.0.0")
    monkeypatch.setattr(lifecycle, "_stop", lambda: stopped.append(True))
    monkeypatch.setattr(lifecycle, "wanted", False)
    answer = TestClient(main.app).post("/update/restart")
    assert answer.json() == {"restarting": True}
    assert stopped == [True] and lifecycle.wanted is True
