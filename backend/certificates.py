"""Whether kerkdienstgemist.nl really is kerkdienstgemist.nl.

Every https address the app opens (kerkdienstgemist, the update check, the person model,
Claude) is checked against trusted certificate authorities before anything is sent. On a
Mac the app now asks macOS to do that check, the way Safari does, instead of OpenSSL.

It took two releases to get here. The Mac app's OpenSSL looked for its list of
authorities in a folder on the computer it was built on, so on a church laptop every
check failed and kerkdienstgemist said "geen verbinding" while the site was up. Pointing
OpenSSL at certifi's list (0.13.2) was not enough: the check still failed with "unable to
get local issuer certificate", which is OpenSSL saying it was shown a certificate without
the one that vouches for it. Safari did not mind, and neither does macOS: it fetches a
missing link of the chain itself, and it knows the certificate a school or company
network puts in between, which no list that ships with an app can.

    Mac        macOS checks (truststore), wherever the app runs
    elsewhere  OpenSSL with the system's list, or certifi's when there is none

Windows reads the Windows certificate store and has always worked; it is left alone.
"""

import os
import socket
import ssl
import sys
from pathlib import Path

from . import places

# Asked over https in the release check, because this is the address that failed.
PROBE = "api.kerkdienstgemist.nl"

done: str | None = None


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


def by_macos() -> bool:
    """Let macOS check every https connection from here on. False when that cannot be."""
    try:
        import truststore

        truststore.inject_into_ssl()
        return True
    except Exception as exc:  # noqa: BLE001  an older macOS or a missing package: fall back
        print(f"[certificaten] macOS kan de controle niet doen ({type(exc).__name__}: {exc})")
        return False


def make_sure() -> str | None:
    """Set up who checks certificates, once. Hands back who does, when this changed it."""
    global done
    if done is not None:
        return done or None
    done = ""
    if sys.platform == "win32":
        return None
    if os.environ.get("SSL_CERT_FILE") or os.environ.get("SSL_CERT_DIR"):
        return None  # somebody chose; their network may need exactly that
    if sys.platform == "darwin" and by_macos():
        done = "macOS"
        return done
    if not places.FROZEN and found_its_own():
        return None
    where = certifi_list()
    if where:
        os.environ["SSL_CERT_FILE"] = where
        done = where
    return where


def check(host: str = PROBE, timeout: float = 15) -> str | None:
    """Open one https connection. None when the certificate checked out, else why not.

    Only a failed check counts as failing. No network at all is something else, and not
    what this is for, so that comes back as None with a word in the log.
    """
    context = ssl.create_default_context()
    try:
        with socket.create_connection((host, 443), timeout=timeout) as raw:
            with context.wrap_socket(raw, server_hostname=host):
                return None
    except ssl.SSLError as exc:
        return f"{type(exc).__name__}: {exc}"
    except OSError as exc:
        print(f"[certificaten] {host} niet bereikt, de controle is overgeslagen ({exc})")
        return None
