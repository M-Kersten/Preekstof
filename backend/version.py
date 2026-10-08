"""One version number, written once and read everywhere.

Every support call starts with "which version are you running", and until now nobody could
answer it: not the volunteer looking at the screen, not the log, not the person reading the
mail. So this sits in one file, and the interface, the black window and every diagnostic
read it from here rather than each carrying their own idea of it.

Bumping it is a deliberate act: change this line, write what changed in CHANGELOG.md in
words a volunteer can read, and tag the commit with the same number.
"""

import hashlib
from pathlib import Path

VERSION = "0.11.0"

# What to call this stretch of the road. A pilot at churches nobody here can see is not the
# same thing as a finished product, and the number says so before anybody has to ask.
STAGE = "pilot"


# Between two releases the number stays the same while the code does not. An interface that
# expects a field the running server has never heard of then breaks with a message nobody
# can act on. So the files that decide what the server answers are fingerprinted as well:
# here when the server starts, and in frontend/vite.config.ts when the interface is built.
# Line endings are evened out first, or a Windows checkout would never match.
API_FILES = ("models.py", "main.py")


def fingerprint(folder: Path = Path(__file__).parent) -> str:
    digest = hashlib.sha256()
    try:
        for name in API_FILES:
            digest.update((folder / name).read_bytes().replace(b"\r\n", b"\n"))
    except OSError:
        return ""
    return digest.hexdigest()[:12]


BUILD = fingerprint()  # what this process started with, whatever is on disk later


def full() -> str:
    """The version as it should appear to a person: "0.10.0 (pilot)"."""
    return f"{VERSION} ({STAGE})" if STAGE else VERSION
