"""Starting the app: what has to be remade before the browser opens."""

import os
import subprocess

import pytest

import launcher


def build(tmp_path, source_age: float, build_age: float):
    """A frontend folder whose source and build have the given ages, in seconds ago."""
    frontend = tmp_path / "frontend"
    (frontend / "src" / "components").mkdir(parents=True)
    (frontend / "dist").mkdir()
    (frontend / "src" / "components" / "BrandPanel.tsx").write_text("code")
    (frontend / "index.html").write_text("<html>")
    built = frontend / "dist" / "index.html"
    built.write_text("<html>")
    now = built.stat().st_mtime
    for path in frontend.rglob("*"):
        if path.is_file():
            age = build_age if "dist" in path.parts else source_age
            os.utime(path, (now - age, now - age))
    return frontend


def test_a_build_newer_than_the_code_is_used_as_is(tmp_path, monkeypatch):
    build(tmp_path, source_age=100, build_age=0)
    monkeypatch.setattr(launcher, "ROOT", tmp_path)
    assert not launcher.frontend_is_stale()


def test_a_build_from_before_the_last_pull_is_remade(tmp_path, monkeypatch):
    """The build is committed, so a pull hands you new code beside an old interface."""
    build(tmp_path, source_age=0, build_age=100)
    monkeypatch.setattr(launcher, "ROOT", tmp_path)
    assert launcher.frontend_is_stale()


def test_no_build_at_all_is_stale(tmp_path, monkeypatch):
    frontend = build(tmp_path, source_age=0, build_age=0)
    (frontend / "dist" / "index.html").unlink()
    monkeypatch.setattr(launcher, "ROOT", tmp_path)
    assert launcher.frontend_is_stale()


def test_the_real_project_is_checked_against_its_own_source():
    """Guards the glob list: a typo would quietly stop looking at the code."""
    frontend = launcher.ROOT / "frontend"
    seen = {p for pattern in launcher.SOURCE_GLOBS for p in frontend.glob(pattern) if p.is_file()}
    assert frontend / "src" / "App.tsx" in seen
    assert frontend / "index.html" in seen
    assert frontend / "vite.config.ts" in seen


# --- Node old enough to build with ------------------------------------------------


def test_a_version_string_becomes_numbers():
    assert launcher.as_numbers("v20.11.1") == (20, 11, 1)
    assert launcher.as_numbers("22.12.0\n") == (22, 12, 0)
    assert launcher.as_numbers("v24") == (24, 0, 0)


def test_something_that_is_not_a_version_says_so():
    assert launcher.as_numbers("") is None
    assert launcher.as_numbers("nightly") is None


WANTED = "^20.19.0 || >=22.12.0"


def test_the_node_that_ships_on_a_mac_a_year_late_is_refused():
    """The real case: 20.11.1 is "Node 20" and still a minor version short."""
    assert launcher.fits((20, 11, 1), WANTED) is False


def test_a_new_enough_node_20_passes():
    assert launcher.fits((20, 19, 0), WANTED) is True
    assert launcher.fits((20, 19, 3), WANTED) is True


def test_an_odd_numbered_release_in_between_is_refused():
    assert launcher.fits((21, 7, 0), WANTED) is False


def test_node_22_is_only_good_from_the_version_it_says():
    assert launcher.fits((22, 11, 0), WANTED) is False
    assert launcher.fits((22, 12, 0), WANTED) is True
    assert launcher.fits((24, 3, 0), WANTED) is True


def test_a_range_written_in_a_way_this_does_not_know_blocks_nothing():
    """Refusing to start on a guess about a range would be worse than trying the build."""
    assert launcher.fits((20, 11, 1), "~20.11") is None
    assert launcher.fits((20, 11, 1), "18.x || 20.x") is None


def test_the_requirement_is_read_from_the_build_tool_itself(tmp_path):
    vite = tmp_path / "node_modules" / "vite"
    vite.mkdir(parents=True)
    (vite / "package.json").write_text('{"engines": {"node": ">=99.0.0"}}')
    assert launcher.node_wanted(tmp_path) == ">=99.0.0"


def test_without_the_build_tool_installed_the_written_down_requirement_stands(tmp_path):
    assert launcher.node_wanted(tmp_path) == launcher.NODE_NEEDED


def test_the_real_project_agrees_with_what_is_written_down():
    """If vite raises its requirement, the first-run message must move with it."""
    installed = launcher.ROOT / "frontend" / "node_modules" / "vite" / "package.json"
    if not installed.is_file():
        return
    assert launcher.node_wanted(launcher.ROOT / "frontend") == launcher.NODE_NEEDED


# --- a build that will not run ----------------------------------------------------


def test_a_failed_build_still_starts_the_app_with_the_interface_it_has(tmp_path, monkeypatch, capsys):
    """The build is committed, so a broken toolchain is a warning, not a dead end."""
    frontend = build(tmp_path, source_age=0, build_age=100)
    monkeypatch.setattr(launcher, "ROOT", tmp_path)
    monkeypatch.setattr(launcher.shutil, "which", lambda name: "/usr/local/bin/" + name)
    monkeypatch.setattr(launcher, "node_too_old", lambda _f: None)
    (frontend / "node_modules").mkdir()

    def refuse(*_args, **_kwargs):
        raise launcher.subprocess.CalledProcessError(1, "npm")

    monkeypatch.setattr(launcher.subprocess, "run", refuse)
    launcher.ensure_frontend()  # must not raise
    said = capsys.readouterr().out
    assert "Building the interface failed" in said
    assert "came with the repository" in said


def test_too_old_a_node_is_named_before_the_build_is_attempted(tmp_path, monkeypatch, capsys):
    build(tmp_path, source_age=0, build_age=100)
    monkeypatch.setattr(launcher, "ROOT", tmp_path)
    monkeypatch.setattr(launcher.shutil, "which", lambda name: "/usr/local/bin/" + name)
    monkeypatch.setattr(launcher, "node_too_old", lambda _f: "Node.js 20.11.1 is too old")

    def refuse(*_args, **_kwargs):
        raise AssertionError("the build must not be started with a Node that cannot run it")

    monkeypatch.setattr(launcher.subprocess, "run", refuse)
    launcher.ensure_frontend()
    assert "too old" in capsys.readouterr().out


def test_without_any_interface_at_all_it_stops_and_says_why(tmp_path, monkeypatch):
    frontend = build(tmp_path, source_age=0, build_age=100)
    (frontend / "dist" / "index.html").unlink()
    monkeypatch.setattr(launcher, "ROOT", tmp_path)
    monkeypatch.setattr(launcher.shutil, "which", lambda name: None)
    with pytest.raises(SystemExit) as stopped:
        launcher.ensure_frontend()
    assert "cannot start" in str(stopped.value)


def test_what_node_reports_decides_whether_the_build_runs(tmp_path, monkeypatch):
    """End to end over the version check, with `node --version` standing in for the machine."""
    monkeypatch.setattr(launcher.shutil, "which", lambda name: "/usr/local/bin/" + name)

    def answer(version):
        def run(command, **_kwargs):
            assert command[1] == "--version"
            return subprocess.CompletedProcess(command, 0, stdout=version, stderr="")
        return run

    monkeypatch.setattr(launcher.subprocess, "run", answer("v20.11.1\n"))
    assert "too old" in (launcher.node_too_old(tmp_path) or "")
    monkeypatch.setattr(launcher.subprocess, "run", answer("v22.20.0\n"))
    assert launcher.node_too_old(tmp_path) is None


# --- the graphics card ------------------------------------------------------------


@pytest.fixture
def machine(monkeypatch):
    """A machine with a card, the libraries missing, and pip standing by."""
    state = {"card": True, "ready": False, "installed": []}

    def pip(command, **_kwargs):
        assert command[1:3] == ["-m", "pip"]
        state["installed"] = command[4:]
        state["ready"] = True
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(launcher, "card_present", lambda: state["card"])
    monkeypatch.setattr(launcher, "cuda_libraries_ready", lambda: state["ready"])
    monkeypatch.setattr(launcher.subprocess, "run", pip)
    return state


def test_the_processor_is_the_default_and_downloads_nothing(machine, monkeypatch, capsys):
    """Almost every church runs on the processor and must not wait for a gigabyte."""
    monkeypatch.delenv("WHISPER_DEVICE", raising=False)
    launcher.ensure_cuda()
    assert machine["installed"] == []
    assert capsys.readouterr().out == ""


@pytest.mark.parametrize("setting", ["cuda", "auto", "CUDA", " cuda "])
def test_asking_for_the_card_fetches_what_it_needs(machine, monkeypatch, setting, capsys):
    monkeypatch.setenv("WHISPER_DEVICE", setting)
    launcher.ensure_cuda()
    assert machine["installed"] == list(launcher.CUDA_PACKAGES)
    assert "videokaart kan gebruikt worden" in capsys.readouterr().out


def test_libraries_that_are_already_there_are_not_fetched_again(machine, monkeypatch):
    machine["ready"] = True
    monkeypatch.setenv("WHISPER_DEVICE", "cuda")
    launcher.ensure_cuda()
    assert machine["installed"] == [], "every start would otherwise wait on pip"


def test_a_setting_that_asks_for_a_card_that_is_not_there_says_so(machine, monkeypatch, capsys):
    machine["card"] = False
    monkeypatch.setenv("WHISPER_DEVICE", "cuda")
    launcher.ensure_cuda()
    assert machine["installed"] == []
    assert "geen NVIDIA-kaart gevonden" in capsys.readouterr().out


def test_a_failed_download_is_not_a_reason_not_to_start(machine, monkeypatch, capsys):
    """The app writes out on the processor; that beats a church with no app on a Sunday."""
    monkeypatch.setenv("WHISPER_DEVICE", "cuda")

    def refuse(command, **_kwargs):
        return subprocess.CompletedProcess(command, 1)

    monkeypatch.setattr(launcher.subprocess, "run", refuse)
    launcher.ensure_cuda()  # must not raise
    said = capsys.readouterr().out
    assert "mislukt" in said and "processor" in said


def test_pip_that_will_not_even_run_is_survived(machine, monkeypatch, capsys):
    monkeypatch.setenv("WHISPER_DEVICE", "cuda")

    def explode(command, **_kwargs):
        raise OSError("pip is gone")

    monkeypatch.setattr(launcher.subprocess, "run", explode)
    launcher.ensure_cuda()
    assert "mislukt" in capsys.readouterr().out


def test_a_download_that_claims_success_but_installs_nothing_is_caught(machine, monkeypatch, capsys):
    monkeypatch.setenv("WHISPER_DEVICE", "cuda")
    monkeypatch.setattr(launcher, "cuda_libraries_ready", lambda: False)
    launcher.ensure_cuda()
    assert "mislukt" in capsys.readouterr().out


def test_no_card_is_reported_when_the_driver_is_not_installed(monkeypatch):
    monkeypatch.setattr(launcher.shutil, "which", lambda name: None)
    assert launcher.card_present() is False


def test_the_driver_being_there_is_what_says_a_card_is(monkeypatch):
    monkeypatch.setattr(launcher.shutil, "which", lambda name: "/usr/bin/" + name)
    monkeypatch.setattr(launcher.subprocess, "run",
                        lambda command, **_k: subprocess.CompletedProcess(command, 0, stdout="GPU 0: RTX 4070"))
    assert launcher.card_present() is True


def test_a_driver_that_answers_with_an_error_is_no_card(monkeypatch):
    monkeypatch.setattr(launcher.shutil, "which", lambda name: "/usr/bin/" + name)
    monkeypatch.setattr(launcher.subprocess, "run",
                        lambda command, **_k: subprocess.CompletedProcess(command, 9, stdout=""))
    assert launcher.card_present() is False


def test_the_check_and_the_fallback_look_in_the_same_place():
    """launcher asks gpu.py, so a folder the app cannot find is never called installed."""
    from backend import gpu

    assert launcher.cuda_libraries_ready() == bool(gpu.package_dirs())
