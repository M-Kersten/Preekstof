"""Getting a CUDA card to work, and carrying on without one when it does not.

CTranslate2 ships without the CUDA libraries it links against. On Windows that shows up as

    Library cublas64_12.dll is not found or cannot be loaded

which means CTranslate2 loaded, found a card, and then could not find cuBLAS or cuDNN next
to it. The libraries do come with pip, under `nvidia/`, but nothing adds those folders to
the search path: on Windows a DLL is looked for beside the executable and in the folders
handed to `os.add_dll_directory`, and pip puts them neither place.

So two things happen here. The folders are pointed at before the model is built, which
fixes the common case in one line. And when it still fails, the processor takes over
instead of the app dying on a Sunday afternoon, because a transcription that is slow beats
a transcription that never starts.
"""

import os
import re
import site
import sys
from pathlib import Path

# The pip packages that carry what CTranslate2 needs, most important first.
NVIDIA_PACKAGES = ("cublas", "cudnn", "cuda_runtime")

# What the error looks like when a CUDA library is the thing that is missing. CTranslate2
# words it differently per platform and per version, so this matches the library name.
CUDA_TROUBLE = re.compile(
    r"cublas|cudnn|cudart|libcuda|cuda driver|no cuda|cuda_?runtime|cuda error|"
    r"no kernel image|unsupported device",
    re.IGNORECASE,
)


def package_dirs() -> list[Path]:
    """The folders inside the installed nvidia packages that hold the actual libraries."""
    roots = [Path(p) / "nvidia" for p in (*site.getsitepackages(), site.getusersitepackages())
             if p]
    found: list[Path] = []
    for root in roots:
        if not root.is_dir():
            continue
        for name in NVIDIA_PACKAGES:
            for holder in ("bin", "lib"):  # bin on Windows, lib everywhere else
                folder = root / name / holder
                if folder.is_dir() and folder not in found:
                    found.append(folder)
    return found


def make_findable() -> list[Path]:
    """Put the CUDA libraries somewhere CTranslate2 will look. Returns what was added.

    Safe to call when there is no GPU and no nvidia package: it then does nothing at all.
    """
    folders = package_dirs()
    for folder in folders:
        if sys.platform == "win32" and hasattr(os, "add_dll_directory"):
            try:
                os.add_dll_directory(str(folder))
            except OSError:  # a folder that disappeared between the check and here
                continue
        os.environ["PATH"] = f"{folder}{os.pathsep}{os.environ.get('PATH', '')}"
    return folders


def blames_cuda(exc: BaseException) -> bool:
    """Is this the graphics card's fault, or is something else wrong?"""
    return bool(CUDA_TROUBLE.search(f"{exc}"))


def advice(exc: BaseException) -> str:
    """What to tell someone whose GPU did not work out, in the language they installed in."""
    missing = re.search(r"([A-Za-z0-9_]*(?:cublas|cudnn|cudart)[A-Za-z0-9_.\-]*)", f"{exc}",
                        re.IGNORECASE)
    named = f" ({missing.group(1)})" if missing else ""
    return (f"De videokaart kon niet gebruikt worden{named}, dus het uitschrijven gebeurt op de "
            f"processor. Dat werkt, het duurt alleen langer. Wil je de kaart wel gebruiken, "
            f"installeer dan de CUDA-onderdelen met: "
            f'"{sys.executable}" -m pip install nvidia-cublas-cu12 nvidia-cudnn-cu12 '
            f"en start de app opnieuw. Of zet WHISPER_DEVICE=cpu in config.env, dan blijft deze "
            f"melding weg.")
