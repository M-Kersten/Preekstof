"""A graphics card that is asked for and does not answer must not take the app down."""

import sys

import pytest

from backend import gpu, transcription


class Built:
    """Stands in for faster_whisper.WhisperModel, remembering how it was asked for."""

    def __init__(self, size, device="cpu", compute_type="int8"):
        self.size, self.device, self.compute_type = size, device, compute_type


@pytest.fixture
def whisper(monkeypatch):
    """faster-whisper replaced by a stub that fails on the card unless told otherwise."""
    import faster_whisper

    asked: list[tuple[str, str]] = []
    trouble = {"on_cuda": None}

    def build(size, device="cpu", compute_type="int8"):
        asked.append((device, compute_type))
        if device == "cuda" and trouble["on_cuda"]:
            raise trouble["on_cuda"]
        return Built(size, device, compute_type)

    monkeypatch.setattr(faster_whisper, "WhisperModel", build)
    monkeypatch.setattr(gpu, "make_findable", lambda: [])
    monkeypatch.setattr(transcription, "DEVICE_NOTE", None)
    return {"asked": asked, "trouble": trouble}


CUBLAS = RuntimeError("Library cublas64_12.dll is not found or cannot be loaded")


# --- reading the error ----------------------------------------------------------

@pytest.mark.parametrize("message", [
    "Library cublas64_12.dll is not found or cannot be loaded",
    "Unable to load any of {libcudnn_ops.so.9.1.0, libcudnn_ops.so.9.1}",
    "libcublas.so.12: cannot open shared object file: No such file or directory",
    "CUDA driver version is insufficient for CUDA runtime version",
    "no kernel image is available for execution on the device",
])
def test_these_are_the_card_being_unusable(message):
    assert gpu.blames_cuda(RuntimeError(message))


@pytest.mark.parametrize("message", [
    "No space left on device",
    "Connection reset by peer while downloading the model",
    "unable to open file 'model.bin'",
])
def test_these_are_something_else_and_must_not_be_swallowed(message):
    assert not gpu.blames_cuda(RuntimeError(message))


def test_the_advice_names_the_library_that_was_missing():
    said = gpu.advice(CUBLAS)
    assert "cublas64_12.dll" in said
    assert "nvidia-cublas-cu12" in said and "nvidia-cudnn-cu12" in said
    assert "processor" in said, "in Dutch, and about what happens now rather than what broke"


# --- choosing a device ----------------------------------------------------------

def test_the_processor_is_used_as_it_always_was(monkeypatch, whisper):
    monkeypatch.setattr(transcription, "DEVICE", "cpu")
    model = transcription.load_whisper("small")
    assert (model.device, model.compute_type) == ("cpu", "int8")
    assert whisper["asked"] == [("cpu", "int8")]


def test_a_card_that_works_is_used(monkeypatch, whisper):
    monkeypatch.setattr(transcription, "DEVICE", "cuda")
    model = transcription.load_whisper("small")
    assert (model.device, model.compute_type) == ("cuda", "float16")
    assert transcription.DEVICE_NOTE is None


def test_a_missing_cublas_falls_back_to_the_processor(monkeypatch, whisper):
    """The failure the church actually hit, on a Sunday, with nobody to install CUDA."""
    monkeypatch.setattr(transcription, "DEVICE", "cuda")
    whisper["trouble"]["on_cuda"] = CUBLAS
    model = transcription.load_whisper("small")
    assert (model.device, model.compute_type) == ("cpu", "int8")
    assert whisper["asked"] == [("cuda", "float16"), ("cpu", "int8")]
    assert "cublas64_12.dll" in (transcription.DEVICE_NOTE or "")


def test_the_fallback_ignores_a_compute_type_meant_for_the_card(monkeypatch, whisper):
    monkeypatch.setattr(transcription, "DEVICE", "cuda")
    monkeypatch.setattr(transcription, "COMPUTE_TYPE", "float16")
    whisper["trouble"]["on_cuda"] = CUBLAS
    model = transcription.load_whisper("small")
    assert model.compute_type == "int8", "the processor cannot decode in float16 either"


def test_auto_takes_the_card_when_it_works(monkeypatch, whisper):
    monkeypatch.setattr(transcription, "DEVICE", "auto")
    assert transcription.load_whisper("small").device == "cuda"


def test_auto_takes_the_processor_when_it_does_not(monkeypatch, whisper):
    monkeypatch.setattr(transcription, "DEVICE", "auto")
    whisper["trouble"]["on_cuda"] = CUBLAS
    assert transcription.load_whisper("small").device == "cpu"


def test_a_failure_that_is_not_the_card_is_still_a_failure(monkeypatch, whisper):
    """A full disk must not quietly become "the GPU did not work out"."""
    monkeypatch.setattr(transcription, "DEVICE", "cuda")
    whisper["trouble"]["on_cuda"] = RuntimeError("No space left on device")
    with pytest.raises(RuntimeError, match="No space left"):
        transcription.load_whisper("small")
    assert transcription.DEVICE_NOTE is None


def test_the_reason_still_reaches_the_user_when_the_model_will_not_load(monkeypatch, whisper):
    monkeypatch.setattr(transcription, "DEVICE", "cpu")
    whisper["trouble"]["on_cuda"] = None

    def refuse(size, device="cpu", compute_type="int8"):
        raise RuntimeError("model.bin is corrupt")

    import faster_whisper

    monkeypatch.setattr(faster_whisper, "WhisperModel", refuse)
    monkeypatch.setattr(transcription, "_models", {})
    with pytest.raises(RuntimeError, match="kon niet geladen worden"):
        transcription.get_model("small")


# --- finding the libraries --------------------------------------------------------

def test_pointing_at_libraries_that_are_not_installed_does_nothing():
    """Every machine without a GPU runs this line on the way to the processor."""
    assert isinstance(gpu.make_findable(), list)


def test_the_folders_looked_in_are_the_ones_pip_writes_to(tmp_path, monkeypatch):
    site_packages = tmp_path / "site-packages"
    for name, holder in (("cublas", "bin"), ("cudnn", "lib")):
        (site_packages / "nvidia" / name / holder).mkdir(parents=True)
    monkeypatch.setattr(gpu.site, "getsitepackages", lambda: [str(site_packages)])
    monkeypatch.setattr(gpu.site, "getusersitepackages", lambda: "")
    found = gpu.package_dirs()
    assert site_packages / "nvidia" / "cublas" / "bin" in found
    assert site_packages / "nvidia" / "cudnn" / "lib" in found


def test_the_folders_end_up_on_the_search_path(tmp_path, monkeypatch):
    folder = tmp_path / "site-packages" / "nvidia" / "cublas" / "bin"
    folder.mkdir(parents=True)
    monkeypatch.setattr(gpu.site, "getsitepackages", lambda: [str(tmp_path / "site-packages")])
    monkeypatch.setattr(gpu.site, "getusersitepackages", lambda: "")
    monkeypatch.setattr(gpu.os, "environ", {"PATH": "/usr/bin"})
    assert gpu.make_findable() == [folder]
    assert str(folder) in gpu.os.environ["PATH"]


@pytest.mark.skipif(sys.platform == "win32", reason="add_dll_directory is the point on Windows")
def test_nothing_windows_specific_runs_anywhere_else(tmp_path, monkeypatch):
    monkeypatch.setattr(gpu.site, "getsitepackages", lambda: [str(tmp_path)])
    monkeypatch.setattr(gpu.site, "getusersitepackages", lambda: "")
    assert gpu.make_findable() == []
