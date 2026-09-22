"""Bringing a service in from a link instead of a file.

Most churches already publish the service somewhere: YouTube, Vimeo, a church-stream
platform, or a plain mp4 on their own website. Uploading the same recording a second time
means finding it on disk first and then waiting out a two-gigabyte copy, so pasting the
address it already lives at is the shorter way in.

The downloading itself is yt-dlp's job. It knows well over a thousand sites, and for a page
it does not know it still reads the page for an embedded player, an og:video tag or a
playlist. What this module adds is the part yt-dlp has no opinion about: which links are
worth trying, how far along a download is, stopping halfway, and saying in Dutch what went
wrong when a link cannot be used.
"""

import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

from . import kerkdienstgemist
from .jobs import Cancelled

ProgressCallback = Callable[[float, str], None]

# Suffixes that mean the link points straight at a video rather than at a page about one.
MEDIA_SUFFIXES = {".mp4", ".m4v", ".mov", ".mkv", ".webm", ".m3u8", ".mpd", ".ts"}

# What a download is allowed to weigh, so a mistyped link cannot fill the disk.
MAX_GB = 12.0

# What to say when a site hands its video only to its own player. For Kerkdienstgemist the
# resolver below normally gets there anyway; this is what is left when it does not.
SITE_ADVICE = {
    "kerkdienstgemist.nl": (
        "Deze dienst is niet op te halen: hij is afgeschermd, of Kerkdienstgemist heeft zijn "
        "speler veranderd. Open de dienst daar, klik in de speler op Downloaden, en plak die "
        "link hier. Of download het bestand en sleep het hierboven naar binnen."
    ),
    "kerkomroep.nl": (
        "Kerkomroep geeft de video pas aan zijn eigen speler. Download de dienst daar en "
        "sleep het bestand hierboven naar binnen."
    ),
}

# Sites whose page holds no video, but whose own player can be asked where it is.
RESOLVERS = (kerkdienstgemist,)


def resolve(url: str) -> kerkdienstgemist.Recording | None:
    """What a site's own player knows about this page: where the video is, and the rest.

    The rest is worth having. A church that fills in who preached, and a platform that
    keeps a still of every service, are handing over two things the file itself does not
    carry and nobody wants to type again.
    """
    for site in RESOLVERS:
        if site.handles(url):
            found = site.resolve(url)
            if found:
                return found
    return None


@dataclass
class Grabbed:
    """A recording that came in, and whatever the place it came from knew about it."""

    file: Path
    title: str
    preacher: str = ""
    poster: Path | None = None  # a still, already on disk next to the recording


# A still is a picture off a church's own page, so there is a ceiling on it and a check on
# what came back. Anything larger or of another kind is dropped rather than written down.
POSTER_MAX_BYTES = 4 * 1024 * 1024
POSTER_TYPES = {"image/jpeg": ".jpg", "image/png": ".png", "image/webp": ".webp"}


def save_poster(url: str, folder: Path, timeout: float = 20.0) -> Path | None:
    """Keep our own copy of the still, because the platform's link is signed and expires.

    Never fatal. A service with no picture is a service; a fetch that fell over on one
    would be a fetch nobody could explain.
    """
    # urlopen speaks file:// and ftp:// as readily as http, and this address comes off a
    # platform's answer rather than out of this app. Two schemes, and no others.
    if urlparse(url).scheme not in {"http", "https"}:
        return None
    try:
        with urllib.request.urlopen(url, timeout=timeout) as answer:
            kind = (answer.headers.get("Content-Type") or "").split(";")[0].strip().lower()
            if kind not in POSTER_TYPES:
                return None
            said = answer.headers.get("Content-Length")
            if said and said.isdigit() and int(said) > POSTER_MAX_BYTES:
                return None
            data = answer.read(POSTER_MAX_BYTES + 1)
    except (urllib.error.URLError, OSError, ValueError):
        return None
    if not data or len(data) > POSTER_MAX_BYTES:
        return None
    for old in folder.glob("poster.*"):
        old.unlink(missing_ok=True)
    target = folder / f"poster{POSTER_TYPES[kind]}"
    target.write_bytes(data)
    return target


class LinkNotUsable(RuntimeError):
    """The link cannot be turned into a recording, with a reason a volunteer can act on."""


def tidy(text: str) -> str:
    """What someone pastes is not always only the address."""
    url = text.strip().strip('<>"\'')
    if url and "://" not in url and re.match(r"^[\w.-]+\.[a-z]{2,}(/|$)", url, re.I):
        url = "https://" + url  # people paste "youtube.com/watch?v=..." without the scheme
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        raise LinkNotUsable("Dat is geen webadres. Plak de link zoals hij in de adresbalk van "
                            "je browser staat, beginnend met https://")
    return url


def host(url: str) -> str:
    return urlparse(url).netloc.lower().removeprefix("www.")


def advice_for(url: str) -> str | None:
    """The site-specific note, if we have one for this host or a parent of it."""
    name = host(url)
    for site, said in SITE_ADVICE.items():
        if name == site or name.endswith("." + site):
            return said
    return None


def is_direct_media(url: str) -> bool:
    return Path(urlparse(url).path).suffix.lower() in MEDIA_SUFFIXES


def safe_title(name: str) -> str:
    """A recording's own name, trimmed to something that reads well in the interface."""
    name = re.sub(r"\s+", " ", (name or "").strip())
    return name[:80] or "Dienst"


class Hush:
    """yt-dlp writes its complaints to the console; here they belong in the message instead."""

    def debug(self, message: str) -> None: ...
    def info(self, message: str) -> None: ...
    def warning(self, message: str) -> None: ...
    def error(self, message: str) -> None: ...


def options(folder: Path, hook) -> dict:
    """How to ask for a recording: one video, with sound, as mp4 where the site allows it."""
    return {
        "outtmpl": str(folder / "source.%(ext)s"),
        # Prefer a single mp4 with sound; fall back to merging the best video and audio.
        "format": "bv*[ext=mp4]+ba[ext=m4a]/b[ext=mp4]/bv*+ba/b",
        "merge_output_format": "mp4",
        "noplaylist": True,  # a link into a playlist means that one service, not the series
        "restrictfilenames": True,
        "overwrites": True,
        "quiet": True,
        "no_warnings": True,
        "noprogress": True,
        "consoletitle": False,
        "retries": 3,
        "fragment_retries": 5,
        "progress_hooks": [hook],
        "max_filesize": int(MAX_GB * 1024 ** 3),
        "logger": Hush(),
    }


def readable(message: str, url: str) -> str:
    """Turn yt-dlp's English complaint into something worth reading."""
    said = re.sub(r"^ERROR:\s*", "", message.strip())
    said = re.sub(r"\s*;\s*please report this issue.*$", "", said, flags=re.I | re.S)
    low = said.lower()
    note = advice_for(url)
    if "unsupported url" in low or "no video" in low or "unable to extract" in low:
        if note:
            return note
        return (f"Op {host(url)} is via deze link geen video te vinden. Staat de dienst op YouTube "
                "of Vimeo, plak dan die link. Anders: download het bestand en sleep het hierboven "
                "naar binnen.")
    if "private" in low or "login" in low or "sign in" in low or "members-only" in low:
        return ("Deze video is niet openbaar, dus de app komt er niet bij. Zet hem op verborgen "
                "in plaats van privé, of download het bestand en sleep het hierboven naar binnen.")
    if "geo" in low and "block" in low:
        return "Deze video is in Nederland niet beschikbaar."
    if "max-filesize" in low or "larger than" in low:
        return f"Deze opname is groter dan {MAX_GB:.0f} GB. Download hem zelf en knip hem eerst korter."
    if "404" in said or "not found" in low:
        return "Op dit adres staat niets (meer). Controleer de link."
    return f"De opname kon niet opgehaald worden: {said[:300]}"


def sweep(folder: Path) -> None:
    """Half-downloaded pieces are of no use to anyone; they only take up room."""
    for leftover in folder.glob("source.*"):
        if leftover.suffix in {".part", ".ytdl"} or ".part-" in leftover.name:
            leftover.unlink(missing_ok=True)


def fetch(url: str, folder: Path, on_progress: ProgressCallback | None = None,
          should_stop: Callable[[], None] | None = None) -> Grabbed:
    """Download what `url` points at into `folder`, with what the source knew about it."""
    url = tidy(url)
    # A page whose player knows better than the page does. Failing here is not fatal: the
    # link goes on to the ordinary route, which ends in the note for that site.
    asked = url  # what was pasted, which is what any message should be about
    known = resolve(url)
    named = ""
    if known:
        url, named = known.url, known.title

    try:
        import yt_dlp
    except ImportError as exc:
        raise LinkNotUsable(
            "Het onderdeel dat video's van een link haalt ontbreekt. Sluit de app en start "
            "opnieuw met start.bat of start.command; het wordt dan geïnstalleerd."
        ) from exc

    folder.mkdir(parents=True, exist_ok=True)
    for old in folder.glob("source.*"):
        old.unlink(missing_ok=True)

    stopped = False

    def hook(state: dict) -> None:
        nonlocal stopped
        if should_stop:
            try:
                should_stop()
            except Cancelled:
                stopped = True
                raise yt_dlp.utils.DownloadCancelled from None
        if not on_progress:
            return
        if state.get("status") == "downloading":
            total = state.get("total_bytes") or state.get("total_bytes_estimate") or 0
            done = state.get("downloaded_bytes") or 0
            share = min(0.99, done / total) if total else 0.0
            on_progress(share, f"Opname wordt opgehaald · {int(share * 100)}%")
        elif state.get("status") == "finished":
            on_progress(0.99, "Opname wordt klaargezet")

    with yt_dlp.YoutubeDL(options(folder, hook)) as ydl:
        try:
            info = ydl.extract_info(url, download=True)
        except yt_dlp.utils.DownloadCancelled as exc:
            sweep(folder)
            raise Cancelled() from exc
        except yt_dlp.utils.DownloadError as exc:
            sweep(folder)
            if stopped:
                raise Cancelled() from exc
            raise LinkNotUsable(readable(str(exc), asked)) from exc
        except Cancelled:
            sweep(folder)
            raise
        except Exception as exc:  # noqa: BLE001  any other failure is still just a bad link
            sweep(folder)
            raise LinkNotUsable(readable(str(exc), asked)) from exc

    sweep(folder)  # the bookkeeping files a finished download leaves behind
    written = sorted(folder.glob("source.*"), key=lambda p: p.stat().st_size, reverse=True)
    if not written:
        raise LinkNotUsable("De opname is niet binnengekomen. Probeer het opnieuw, of download "
                            "het bestand en sleep het hierboven naar binnen.")
    # A resolved recording brings the name the church gave it; a signed S3 link does not.
    heard = (info or {}).get("title", "") if isinstance(info, dict) else ""
    return Grabbed(
        file=written[0],
        title=safe_title(named or heard),
        preacher=known.preacher if known else "",
        poster=save_poster(known.poster, folder) if known and known.poster else None,
    )
