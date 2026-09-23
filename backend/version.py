"""One version number, written once and read everywhere.

Every support call starts with "which version are you running", and until now nobody could
answer it: not the volunteer looking at the screen, not the log, not the person reading the
mail. So this sits in one file, and the interface, the black window and every diagnostic
read it from here rather than each carrying their own idea of it.

Bumping it is a deliberate act: change this line, write what changed in CHANGELOG.md in
words a volunteer can read, and tag the commit with the same number.
"""

VERSION = "0.10.0"

# What to call this stretch of the road. A pilot at churches nobody here can see is not the
# same thing as a finished product, and the number says so before anybody has to ask.
STAGE = "pilot"


def full() -> str:
    """The version as it should appear to a person: "0.10.0 (pilot)"."""
    return f"{VERSION} ({STAGE})" if STAGE else VERSION
