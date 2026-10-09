"""Is there a newer one, and what changed in it.

A church that installed this once will otherwise run that version until somebody visits.
So the launcher asks GitHub, once, on start, and says in the black window what is there
and where to get it.

What this deliberately is not: an update that installs itself. A church rebuilding
unattended at ten to ten on a Sunday morning is a worse outcome than a church running last
month's version, and the person who would have to fix it is not in the building. Somebody
presses Bijwerken in the readiness panel; then the right download for this computer is
fetched and put next to the app (stage), and start.bat or start.command swap it in when the
app starts again. The church's own work lives elsewhere (places.py) and is never touched.

Failing is the ordinary case, not the exception. No internet, GitHub down, a proxy in the
way, a rate limit: all of those mean the app starts without saying anything about updates.
"""

import hashlib
import json
import os
import re
import shutil
import time
import urllib.error
import urllib.request
import zipfile
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from . import places, version

RELEASES = "https://api.github.com/repos/M-Kersten/Preekstof/releases/latest"
TIMEOUT = 6.0  # a start that waits on GitHub is a start nobody trusts
NUMBER = re.compile(r"(\d+)\.(\d+)\.(\d+)")


@dataclass
class Asset:
    name: str
    url: str
    size: int = 0
    digest: str = ""  # "sha256:…" when GitHub knows it


@dataclass
class Release:
    version: str
    url: str
    notes: str = ""
    assets: list[Asset] = field(default_factory=list)

    def headline(self) -> str:
        """The first thing worth reading out of the release notes, if there is one.

        Headings are skipped. "## Wat er verandert" is what every set of notes starts
        with and it tells a volunteer nothing; the line under it is the one to show.
        """
        for line in self.notes.splitlines():
            said = line.strip()
            if not said or said.startswith(("#", "<", "---", "===")):
                continue
            said = said.lstrip("*-·+ ").strip()
            if said:
                return said[:160]
        return ""


def as_numbers(said: str) -> tuple[int, int, int] | None:
    found = NUMBER.search(said or "")
    return (int(found.group(1)), int(found.group(2)), int(found.group(3))) if found else None


def newer(there: str, here: str = version.VERSION) -> bool:
    """Is `there` a later version than `here`? An unreadable number is never newer."""
    theirs, ours = as_numbers(there), as_numbers(here)
    return bool(theirs and ours and theirs > ours)


def latest(url: str = RELEASES, timeout: float = TIMEOUT) -> Release | None:
    """What GitHub says the newest release is, or nothing at all."""
    try:
        request = urllib.request.Request(url, headers={
            "Accept": "application/vnd.github+json",
            "User-Agent": version.USER_AGENT,
        })
        with urllib.request.urlopen(request, timeout=timeout) as answer:
            said = json.loads(answer.read(1_000_000).decode("utf-8"))
    except (urllib.error.URLError, OSError, ValueError, json.JSONDecodeError):
        return None
    tag = said.get("tag_name") or said.get("name") or ""
    if not isinstance(tag, str) or not as_numbers(tag):
        return None
    where = said.get("html_url")
    assets = []
    for item in said.get("assets") or []:
        if not isinstance(item, dict):
            continue
        link = item.get("browser_download_url")
        if isinstance(item.get("name"), str) and isinstance(link, str) and link.startswith("https://"):
            assets.append(Asset(name=item["name"], url=link, size=int(item.get("size") or 0),
                                digest=item.get("digest") if isinstance(item.get("digest"), str) else ""))
    return Release(
        version=tag.lstrip("vV"),
        url=where if isinstance(where, str) and where.startswith("https://") else
            "https://github.com/M-Kersten/Preekstof/releases/latest",
        notes=said.get("body") if isinstance(said.get("body"), str) else "",
        assets=assets,
    )


def note() -> str:
    """What to say in the black window, or nothing when there is nothing to say."""
    there = latest()
    if there is None or not newer(there.version):
        return ""
    said = [f"Er is een nieuwere versie: {there.version} (je draait {version.VERSION})."]
    headline = there.headline()
    if headline:
        said.append(f"Wat er verandert: {headline}")
    said.append(f"Ophalen: {there.url}")
    said.append("De app draait gewoon door; bijwerken doe je wanneer het jou uitkomt.")
    return "\n".join(said)


# --- bijwerken vanuit de app -----------------------------------------------------------

ROOT = places.ROOT
STAGE = ROOT / ".update"  # start.bat and start.command look here when they start
DOWNLOADS = places.DATA / "updates"
# The downloads with everything in them, by what this computer is. Written into the
# download as bundle.json by the release build; the plain zip has none.
BUNDLES = {"windows-x64": "Preekstof-Windows.zip", "mac-arm64": "Preekstof-Mac.zip",
           "mac-x64": "Preekstof-Mac-Intel.zip"}


class UpdateError(RuntimeError):
    """Why this install cannot update itself, in words for the readiness panel."""


def kind(root: Path | None = None) -> str:
    """What this install is: one of the downloads, the plain zip, or a git checkout."""
    root = root or ROOT
    if (root / ".git").exists():
        return "git"
    try:
        said = json.loads((root / "bundle.json").read_text(encoding="utf-8")).get("kind")
    except (OSError, ValueError, AttributeError):
        said = None
    return said if said in BUNDLES else "plain"


def asset_for(release: Release, how: str | None = None) -> Asset | None:
    how = how or kind()
    if how == "git":
        return None
    wanted = BUNDLES.get(how) or f"preekstof-{release.version}.zip"
    return next((a for a in release.assets if a.name == wanted), None)


def why_not(release: Release, root: Path | None = None) -> str:
    """The reason the button cannot do it, or nothing when it can."""
    root = root or ROOT
    if kind(root) == "git":
        return "Deze app komt uit git. Werk hem bij met git pull en start opnieuw."
    if asset_for(release, kind(root)) is None:
        return "Bij die versie staat geen download voor deze computer. Haal hem op via de link."
    if not os.access(root, os.W_OK):
        return "De map van de app is niet beschrijfbaar. Haal de nieuwe versie op via de link."
    return ""


_known: tuple[float, Release | None] = (0.0, None)


def known(max_age: float = 600.0) -> Release | None:
    """latest(), asked at most every ten minutes: the panel polls, GitHub rations."""
    global _known
    when, release = _known
    if time.monotonic() - when > max_age or when == 0.0:
        release = latest()
        _known = (time.monotonic(), release)
    return release


def staged(stage: Path | None = None) -> str | None:
    """The version that is ready to go in at the next start, if there is one."""
    stage = stage or STAGE
    try:
        ready = (stage / "ready").read_text(encoding="utf-8").strip()
    except OSError:
        return None
    return ready if (stage / "new" / "launcher.py").is_file() else None


def unpack(archive: Path, target: Path) -> None:
    """Unpack a release zip into `target`, without its outer folder, keeping what may run."""
    with zipfile.ZipFile(archive) as zipped:
        names = [n for n in zipped.namelist() if n and not n.endswith("/")]
        tops = {n.split("/", 1)[0] for n in names}
        strip = len(tops) == 1 and all("/" in n for n in names)
        base = target.resolve()
        for info in zipped.infolist():
            if info.is_dir():
                continue
            name = info.filename.split("/", 1)[1] if strip else info.filename
            out = (target / name).resolve()
            if not out.is_relative_to(base):
                raise UpdateError("De download bevat een pad buiten de app. Hij wordt niet gebruikt.")
            out.parent.mkdir(parents=True, exist_ok=True)
            with zipped.open(info) as source, out.open("wb") as written:
                shutil.copyfileobj(source, written)
            mode = info.external_attr >> 16
            if mode & 0o111:
                out.chmod(out.stat().st_mode | 0o755)


def fetch(asset: Asset, target: Path, on_progress: Callable[[float, str], None] | None,
          should_stop: Callable[[], None] | None) -> None:
    part = target.with_suffix(target.suffix + ".part")
    digest = hashlib.sha256()
    got = 0
    request = urllib.request.Request(asset.url, headers={"User-Agent": version.USER_AGENT})
    with urllib.request.urlopen(request, timeout=60) as answer, part.open("wb") as out:
        total = asset.size or int(answer.headers.get("content-length") or 0)
        while chunk := answer.read(1024 * 512):
            if should_stop:
                should_stop()
            out.write(chunk)
            digest.update(chunk)
            got += len(chunk)
            if on_progress and total:
                on_progress(0.9 * got / total, f"De nieuwe versie wordt opgehaald · "
                                               f"{got // 1_000_000} van {total // 1_000_000} MB")
    if asset.size and got != asset.size:
        part.unlink(missing_ok=True)
        raise UpdateError("De download kwam maar half binnen. Probeer het opnieuw.")
    if asset.digest.startswith("sha256:") and digest.hexdigest() != asset.digest.split(":", 1)[1]:
        part.unlink(missing_ok=True)
        raise UpdateError("De download klopt niet met wat GitHub zegt dat hij is. Hij wordt niet gebruikt.")
    part.replace(target)


def stage(release: Release, on_progress: Callable[[float, str], None] | None = None,
          should_stop: Callable[[], None] | None = None, stage_dir: Path | None = None) -> str:
    """Fetch the download for this computer and put it ready next to the app.

    Nothing of the running app changes here. The next start puts it in place.
    """
    stage_dir = stage_dir or STAGE
    reason = why_not(release)
    if reason:
        raise UpdateError(reason)
    asset = asset_for(release)
    DOWNLOADS.mkdir(parents=True, exist_ok=True)
    archive = DOWNLOADS / asset.name
    try:
        fetch(asset, archive, on_progress, should_stop)
    except (urllib.error.URLError, OSError) as exc:
        raise UpdateError(f"De nieuwe versie kon niet opgehaald worden ({exc}). Probeer het later opnieuw.") from exc
    if on_progress:
        on_progress(0.92, "De nieuwe versie wordt klaargezet")
    shutil.rmtree(stage_dir, ignore_errors=True)
    try:
        unpack(archive, stage_dir / "new")
    except zipfile.BadZipFile as exc:
        shutil.rmtree(stage_dir, ignore_errors=True)
        raise UpdateError("De download is beschadigd. Probeer het opnieuw.") from exc
    finally:
        archive.unlink(missing_ok=True)
    if not (stage_dir / "new" / "launcher.py").is_file():
        shutil.rmtree(stage_dir, ignore_errors=True)
        raise UpdateError("De download ziet er niet uit als Preekstof. Hij wordt niet gebruikt.")
    (stage_dir / "ready").write_text(release.version, encoding="utf-8")
    if on_progress:
        on_progress(1.0, "Klaar om opnieuw te starten")
    return release.version
