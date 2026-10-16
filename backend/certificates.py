"""Which certificates say that kerkdienstgemist.nl really is kerkdienstgemist.nl.

Every https address the app opens with urllib (kerkdienstgemist, the update check, the
person model) is checked against a list of trusted certificate authorities. Python does
not bring that list itself: it asks OpenSSL, and OpenSSL looks in the folder it was told
about when it was built.

In the Mac app that folder is on the computer the app was built on. On a church laptop it
does not exist, so every check fails, and the app said "geen verbinding" while the site
was online and the browser beside it showed it fine. The Claude calls and the speech model
download did work, because those libraries bring their own list: certifi.

So the app points OpenSSL at certifi's list as well, before anything is opened:

    the Mac app      always, so what is tested on the build machine is what a church gets
    anything else    only when OpenSSL found no list of its own

Windows is left alone. Python reads the Windows certificate store there, which also knows
about whatever a church's network puts in between.
"""

import os
import ssl
import sys
from pathlib import Path

from . import places


def found_its_own() -> bool:
    """Whether OpenSSL has a list of authorities of its own on this computer."""
    paths = ssl.get_default_verify_paths()
    if paths.cafile:
        return True  # only filled in when the file is really there
    if paths.capath:
        try:
            return any(Path(paths.capath).iterdir())
        except OSError:
            return False
    return False


def certifi_list() -> str | None:
    try:
        import certifi
    except ImportError:
        return None
    where = certifi.where()
    return where if os.path.isfile(where) else None


def make_sure() -> str | None:
    """Point OpenSSL at certifi when it needs to be. Hands back the list now used, if it set one."""
    if sys.platform == "win32":
        return None
    if os.environ.get("SSL_CERT_FILE") or os.environ.get("SSL_CERT_DIR"):
        return None  # somebody chose; their network may need exactly that
    if not places.FROZEN and found_its_own():
        return None
    where = certifi_list()
    if where:
        os.environ["SSL_CERT_FILE"] = where
    return where


def trusted() -> int:
    """How many authorities an https connection would trust right now."""
    return ssl.create_default_context().cert_store_stats().get("x509_ca", 0)
