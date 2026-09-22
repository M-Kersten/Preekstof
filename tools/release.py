"""Build the zip a church downloads, out of what git already tracks.

Nobody at a pilot church is going to install git. So a release is one file they unpack
wherever they like and double-click, holding exactly what `git clone` would have given
them: the code, the fonts, the face model, start.bat and start.command.

    .venv/bin/python -m tools.release
    .venv/bin/python -m tools.release --out dist --version 0.9.1

What is deliberately not in it: everything the app fetches on the machine that runs it.
FFmpeg, the speech models and the person model are downloaded on first use, which keeps the
zip small and keeps the AGPL-licensed person model out of anything that gets handed on.
"""

import argparse
import subprocess
import sys
import zipfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend import version  # noqa: E402

# Kept out of the zip even though git tracks them: nothing a church runs needs them, and
# every megabyte is a download somebody is waiting on.
LEAVE_OUT = ("docs/", "evaluation/", "tests/", ".github/", "tools/evaluate.py",
             "tools/speechbench.py", "tools/release.py", ".gitignore", ".gitattributes")


def tracked() -> list[str]:
    """What git has, which is the only honest definition of what a clone would give."""
    said = subprocess.run(["git", "-C", str(ROOT), "ls-files"],
                          capture_output=True, text=True, check=True)
    return [line for line in said.stdout.splitlines() if line.strip()]


def wanted(paths: list[str]) -> list[str]:
    return [p for p in paths if not p.startswith(LEAVE_OUT) and p not in LEAVE_OUT]


# Every file in the zip gets the same date, and the built interface gets a later one.
# The launcher rebuilds the interface when its source looks newer than the build, and on a
# machine with no Node that ends in a warning nobody can act on. Whatever the working tree's
# timestamps happen to say, in the zip the build is always the younger of the two.
STAMPED = (1980, 1, 1, 0, 0, 0)
BUILT = (1980, 1, 2, 0, 0, 0)
IS_BUILD = "frontend/dist/"


def build(out: Path, number: str) -> Path:
    """Write the zip and hand back where it landed."""
    out.mkdir(parents=True, exist_ok=True)
    target = out / f"preekstof-{number}.zip"
    inside = f"preekstof-{number}"
    files = wanted(tracked())
    if not files:
        raise SystemExit("git ls-files gaf niets terug; draait dit wel in de repository?")
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as zip_file:
        for name in files:
            source = ROOT / name
            if not source.is_file():
                continue  # a submodule or a link git knows about and the disk does not
            entry = zipfile.ZipInfo(f"{inside}/{name}")
            entry.date_time = BUILT if name.startswith(IS_BUILD) else STAMPED
            entry.compress_type = zipfile.ZIP_DEFLATED
            entry.external_attr = (0o755 if name.endswith((".sh", ".command")) else 0o644) << 16
            zip_file.writestr(entry, source.read_bytes())
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--out", type=Path, default=ROOT / "dist", help="where to write it")
    parser.add_argument("--version", default=version.VERSION, help="the number in the filename")
    args = parser.parse_args()

    built = build(args.out, args.version)
    size = built.stat().st_size / 1e6
    with zipfile.ZipFile(built) as zip_file:
        count = len(zip_file.namelist())
    print(f"{built}  ({size:.1f} MB, {count} bestanden)")
    print("Uitpakken en start.bat of start.command aanklikken. Verder is er niets nodig.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
