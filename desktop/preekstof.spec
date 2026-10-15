# PyInstaller spec for the desktop app. Built by desktop/build.py, which fetches FFmpeg first:
#
#     python desktop/build.py
#
# One folder, not one file: a single .exe unpacks four hundred megabytes into a temporary
# folder on every start, which on a church laptop is twenty seconds of nothing happening.
# On a Mac the folder goes into Preekstof.app.
import os
import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_submodules

ROOT = Path(SPECPATH).resolve().parent  # noqa: F821  SPECPATH is set by PyInstaller
DESKTOP = ROOT / "desktop"
sys.path.insert(0, str(ROOT))

from backend import version  # noqa: E402
from tools import release  # noqa: E402

# What the backend reads from next to itself, taken from what git tracks, the same rule the
# zips follow. A developer's own church (templates/church.json, logos, the word list) is not
# tracked, so it never ends up in an app somebody else installs.
SHIPPED = ("frontend/dist/", "templates/", "vision/", "selftest/")
TOP = ("config.example.env", "LICENSE", "NOTICE", "PRIVACY.md", "CHANGELOG.md")
datas = []
for name in release.wanted(release.tracked()):
    if name.startswith(SHIPPED) or name in TOP:
        source = ROOT / name
        if source.is_file():
            datas.append((str(source), str(Path(name).parent)))

# The fingerprint of the code the interface was built against, which the packed app cannot
# work out itself: it has no source files to read (backend/version.py).
written = DESKTOP / "build" / version.WRITTEN_DOWN
written.parent.mkdir(parents=True, exist_ok=True)
written.write_text(version.fingerprint(ROOT / "backend"), encoding="utf-8")
datas.append((str(written), "backend"))

# FFmpeg and ffprobe, run as programs of their own, with the licence they come under.
binaries = []
ffmpeg = Path(os.environ.get("PREEKSTOF_FFMPEG_DIR", DESKTOP / "build" / "ffmpeg"))
for found in sorted(ffmpeg.glob("*")) if ffmpeg.is_dir() else []:
    if found.name.lower().startswith(("ffmpeg", "ffprobe")):
        binaries.append((str(found), "ffmpeg"))
    elif found.is_file():
        datas.append((str(found), "ffmpeg"))
if not any(Path(b[0]).name.lower().startswith("ffmpeg") for b in binaries):
    print(f"LET OP: geen FFmpeg in {ffmpeg}; de app zoekt het dan op de computer zelf.")

hiddenimports = collect_submodules("backend") + ["launcher"]
for package in ("faster_whisper", "ctranslate2"):
    package_datas, package_binaries, package_imports = collect_all(package)
    datas += package_datas
    binaries += package_binaries
    hiddenimports += package_imports

a = Analysis(  # noqa: F821
    [str(DESKTOP / "app.py")],
    # stubs/ first: its av is found before any real PyAV (see desktop/stubs/av).
    pathex=[str(DESKTOP / "stubs"), str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    excludes=["tkinter", "matplotlib", "pytest", "IPython", "PIL", "mlx", "mlx_whisper", "torch"],
    noarchive=False,
)
pyz = PYZ(a.pure)  # noqa: F821

icon = DESKTOP / "icons" / ("preekstof.icns" if sys.platform == "darwin" else "preekstof.ico")
exe = EXE(  # noqa: F821
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="Preekstof",
    console=False,  # a window of its own, no black one beside it
    icon=str(icon),
    upx=False,
    argv_emulation=False,
)
coll = COLLECT(exe, a.binaries, a.datas, name="Preekstof", upx=False)  # noqa: F821

if sys.platform == "darwin":
    app = BUNDLE(  # noqa: F821
        coll,
        name="Preekstof.app",
        icon=str(icon),
        bundle_identifier="nl.preekstof.app",
        version=version.VERSION,
        info_plist={
            "CFBundleDisplayName": "Preekstof",
            "CFBundleShortVersionString": version.VERSION,
            "CFBundleVersion": version.VERSION,
            # onnxruntime and PyAV build for the Apple chip from macOS 14 on (see release.yml)
            "LSMinimumSystemVersion": os.environ.get("PREEKSTOF_MACOS", "14.0"),
            "NSHighResolutionCapable": True,
            "LSApplicationCategoryType": "public.app-category.video",
            "NSHumanReadableCopyright": "Merijn Kersten. Gratis te gebruiken; zie NOTICE.",
        },
    )
