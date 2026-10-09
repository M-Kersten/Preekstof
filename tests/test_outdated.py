"""The interface and the server say which code they come from, so a stale window is caught."""

from pathlib import Path

from backend import health, version

DIST = Path(__file__).resolve().parent.parent / "frontend" / "dist" / "assets"


def test_the_built_interface_belongs_to_this_server_code():
    """Change models.py or main.py and the interface has to be built again, or every user sees the banner."""
    built = "".join(p.read_text(encoding="utf-8") for p in DIST.glob("*.js"))
    assert version.fingerprint() in built, "run npm run build in frontend/ and commit frontend/dist"


def test_a_windows_checkout_has_the_same_fingerprint(tmp_path):
    for name in version.API_FILES:
        text = (Path(version.__file__).parent / name).read_bytes()
        (tmp_path / name).write_bytes(text.replace(b"\n", b"\r\n"))
    assert version.fingerprint(tmp_path) == version.fingerprint()


def test_the_running_code_is_reported():
    assert health.report()["build"] == version.BUILD != ""


def test_the_built_interface_carries_this_version():
    """Bumping version.py without building gives a release the workflow refuses to make."""
    from backend import version

    built = Path(__file__).resolve().parent.parent / "frontend" / "dist" / "assets"
    assert any(version.VERSION in js.read_text(encoding="utf-8") for js in built.glob("*.js")), \
        "bouw de interface opnieuw: cd frontend && npm run build"
