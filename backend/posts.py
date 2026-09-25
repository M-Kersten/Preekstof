"""The text that goes under a clip when it is posted.

Making the video was never the whole job. Somebody still has to sit down and write a few
lines to go with it, three times over, because Instagram, Facebook and a WhatsApp group each
want something different. That is the step where a volunteer on a Monday evening gives up
and posts the clip with only its title under it.

The model knows the clip by now, so it writes those lines. What it writes is only the body.
Everything that has to be exactly right is added by the app afterwards, from what the
church set once: the link to the whole service, the hashtags every post carries, the Bible
passage. A model that writes a link can write a wrong one, and a wrong link under a church's
post is worse than none.

What it does write is checked where it can be:

    a quote has to stand in the clip word for word, or that text is not used,
    a Bible passage has to be named in the clip or in what the church said about the
    service, book and numbers both, or it is dropped,
    and hashtags and links it put in anyway are taken out again.

Without a key, or when the model cannot be reached, the texts are built from the clip's
title and summary instead. Less good, and the window says which one it is showing.
"""

import json
import re
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal
from urllib.parse import urlparse

from pydantic import BaseModel

from . import brands, settings
from .models import (Project, ShareSettings, Transcript, load_service, load_transcript, project_dir,
                     write_atomic)

ON = settings.text("WRITE_POSTS", "1").strip().lower() not in ("0", "false", "nee", "off")
EFFORT = settings.choice("POST_EFFORT", ("low", "medium", "high", "xhigh", "max"), "low")

Platform = Literal["instagram", "facebook", "whatsapp"]
PLATFORMS: tuple[Platform, ...] = ("instagram", "facebook", "whatsapp")

TOPICAL_TAGS = 4  # hashtags of the clip's own, on top of the church's
INSTAGRAM_TAGS = 6  # all of them together, which is where Instagram stops rewarding more
FACEBOOK_TAGS = 3  # the church's own only; on Facebook a row of tags reads as spam
QUOTE_WORDS = 3  # shorter than this between quotation marks is an expression, not a quote
DEFAULT_CHURCH = "Example Church"  # what an install that was never set up is called


class PostDraft(BaseModel):
    """What the model wrote, before the church's own lines are added under it."""

    instagram: str = ""
    facebook: str = ""
    whatsapp: str = ""
    hashtags: list[str] = []
    bible: str = ""  # "Efeziërs 2:8", only when the clip names it


class Post(BaseModel):
    draft: PostDraft = PostDraft()
    by: Literal["model", "template"] = "template"
    note: str = ""  # why the model did not write it, when it did not
    written: str = ""
    own: dict[str, str] = {}  # what somebody rewrote by hand, per platform; wins over the draft


class LlmPost(BaseModel):
    instagram: str
    facebook: str
    whatsapp: str
    hashtags: list[str]
    bijbeltekst: str


SYSTEM = """Je schrijft de tekst die een kerk onder een korte video op social media zet. De \
video is een fragment uit een kerkdienst, meestal uit de preek. Je krijgt wat er in het \
fragment gezegd wordt en wat de kerk over de dienst weet.

Schrijf drie teksten, elk voor een andere plek:
- instagram: twee tot vier korte zinnen. De eerste zin laat iemand die voorbij scrolt stoppen, \
zonder te overdrijven. Je mag eindigen met een vraag aan de lezer.
- facebook: drie tot vijf zinnen, met iets meer context: uit welke dienst, wie er sprak, \
waar het over ging. Hier lezen vooral mensen uit de eigen gemeente en hun omgeving.
- whatsapp: een of twee zinnen, zoals je het doorstuurt naar iemand die je kent.

Zet in geen van de drie een hashtag, een link, een oproep om de hele dienst te kijken of de \
bijbeltekst als losse regel. Die regels zet de kerk er zelf onder.

Geef daarnaast:
- hashtags: twee tot vier onderwerpen van dit fragment, elk als een los woord zonder hekje, in \
kleine letters, bijvoorbeeld genade of vergeving. Geen algemene woorden als kerk, geloof of \
preek.
- bijbeltekst: het bijbelgedeelte dat in het fragment genoemd of voorgelezen wordt, als "Boek \
hoofdstuk:vers", bijvoorbeeld Efeziërs 2:8 of Psalm 23. Noemt het fragment alleen het boek, \
geef dan alleen het boek. Wordt er geen gedeelte genoemd, laat dit leeg. Leid het nooit af \
uit de inhoud.

Regels, en hier mag je niet van afwijken:
- Schrijf alleen wat in het fragment staat. Verzin geen gebeurtenissen, namen, getallen of \
beloftes.
- Citeer alleen letterlijk. Wat tussen aanhalingstekens staat, staat woord voor woord in het \
fragment. Twijfel je, citeer dan niet.
- Noem de spreker alleen zoals de kerk die aankondigt, en neem geen hij of zij aan: een \
voorletter en een achternaam zeggen niets over wie er stond. Schrijf de naam of "de spreker".
- Noem geen dag of datum. De post kan later in de week geplaatst worden.
- {address}
- Schrijf gewoon Nederlands, warm en rustig. Geen uitroeptekens, geen emoji, geen clichés als \
"in een wereld waarin". Vermijd de vorm "niet dit, maar dat" en vermijd opsommingen van drie."""

ADDRESS = {
    "je": "Spreek de lezer aan met je en jij.",
    "u": "Spreek de lezer aan met u. Schrijf voornaamwoorden die naar God verwijzen met een "
         "hoofdletter, zoals Hij en Zijn.",
}


# --- where the whole service can be watched ------------------------------------------


def link_for(project: Project, share: ShareSettings, station: str = "") -> tuple[str, str]:
    """Where somebody who liked the clip can watch the whole service, and where that came from.

    A link the church typed itself wins: it chose where people should go. After that the page
    this recording was fetched from, which is this very service. After that the church's
    page on Kerkdienstgemist, which at least has the service on it somewhere.
    """
    if share.link.strip():
        return share.link.strip(), "merk"
    if project.origin is not None:
        service = load_service(project.origin.serviceId)
        if service is not None and service.link:
            return service.link, "dienst"
    if station.strip():
        from . import kerkdienstgemist

        return kerkdienstgemist.station_url(station.strip()), "station"
    return "", ""


def tidy_link(text: str) -> str:
    """A web address as somebody pasted it, or empty. Raises ValueError for what is not one."""
    link = text.strip().strip('<>"\'')
    if not link:
        return ""
    if "://" not in link:
        link = "https://" + link
    parsed = urlparse(link)
    if parsed.scheme not in ("http", "https") or "." not in parsed.netloc or " " in link:
        raise ValueError("Dat is geen webadres. Plak het adres zoals het bovenin de browser staat.")
    return link


def tag(word: str) -> str:
    """One hashtag, the way Instagram reads it: no spaces, no punctuation, lower case."""
    cleaned = re.sub(r"[\W_]+", "", word.strip().lstrip("#").lower())
    return f"#{cleaned}" if cleaned and not cleaned.isdigit() else ""


def tags(words: list[str], most: int) -> list[str]:
    seen: list[str] = []
    for word in words:
        made = tag(word)
        if made and made not in seen:
            seen.append(made)
    return seen[:most]


def tidy_share(share: ShareSettings) -> ShareSettings:
    """The settings as they are kept: known shapes, real hashtags, a usable link."""
    from . import formats

    return ShareSettings(shapes=formats.extras(share.shapes), address=share.address,
                         hashtags=tags(share.hashtags, 12), link=tidy_link(share.link))


# --- checking what came back ------------------------------------------------------------


def fold(text: str) -> str:
    """Lower case, no accents, no punctuation: what is left to compare two texts on."""
    plain = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode().lower()
    return " ".join(re.sub(r"[^a-z0-9]+", " ", plain).split())


QUOTED = re.compile(r"[\"“”„«»]([^\"“”„«»]+)[\"“”„«»]|(?<!\w)['‘’]([^'‘’]+)['‘’](?!\w)")


def quotes(text: str) -> list[str]:
    """Everything between quotation marks that is long enough to count as a quote."""
    found = []
    for match in QUOTED.finditer(text):
        said = (match.group(1) or match.group(2) or "").strip()
        if len(said.split()) >= QUOTE_WORDS:
            found.append(said)
    return found


def honest(body: str, spoken: str) -> bool:
    """Whether every quote in the text was really said, word for word."""
    heard = f" {fold(spoken)} "
    return all(f" {fold(said)} " in heard for said in quotes(body))


def clean(body: str) -> str:
    """The text without the hashtags and links it was told to leave out."""
    body = re.sub(r"https?://\S+|www\.\S+", "", body)
    body = re.sub(r"(?<!\w)#\w+", "", body)
    lines = [" ".join(line.split()) for line in body.strip().splitlines()]
    return "\n".join(lines).strip()


# The books by the names Dutch Bibles give them, with the other spellings in use.
BOOKS = [
    ["Genesis"], ["Exodus"], ["Leviticus"], ["Numeri"], ["Deuteronomium"], ["Jozua"],
    ["Rechters", "Richteren"], ["Ruth"], ["Samuel"], ["Koningen"], ["Kronieken"], ["Ezra"],
    ["Nehemia"], ["Ester", "Esther"], ["Job"], ["Psalm", "Psalmen"], ["Spreuken"], ["Prediker"],
    ["Hooglied"], ["Jesaja"], ["Jeremia"], ["Klaagliederen"], ["Ezechiël"], ["Daniël"],
    ["Hosea"], ["Joël"], ["Amos"], ["Obadja"], ["Jona"], ["Micha"], ["Nahum"], ["Habakuk"],
    ["Sefanja"], ["Haggai"], ["Zacharia"], ["Maleachi"],
    ["Matteüs", "Mattheüs"], ["Marcus", "Markus"], ["Lucas", "Lukas"], ["Johannes"],
    ["Handelingen"], ["Romeinen"], ["Korintiërs", "Korinthiërs", "Korinte"], ["Galaten"],
    ["Efeziërs", "Efeze"], ["Filippenzen", "Filippi"], ["Kolossenzen", "Kolosse"],
    ["Tessalonicenzen", "Thessalonicenzen", "Tessalonica", "Thessalonica"],
    ["Timoteüs", "Timotheüs"], ["Titus"], ["Filemon"], ["Hebreeën"], ["Jakobus"], ["Petrus"],
    ["Judas"], ["Openbaring"],
]

UNITS = ["nul", "een", "twee", "drie", "vier", "vijf", "zes", "zeven", "acht", "negen", "tien",
         "elf", "twaalf", "dertien", "veertien", "vijftien", "zestien", "zeventien", "achttien",
         "negentien"]
TENS = {2: "twintig", 3: "dertig", 4: "veertig", 5: "vijftig", 6: "zestig", 7: "zeventig",
        8: "tachtig", 9: "negentig"}

REFERENCE = re.compile(r"^\s*(?:(?P<nth>[1-3])\s*)?(?P<book>[^\d:]+?)\s*"
                       r"(?:(?P<chapter>\d{1,3})(?:\s*[:,]\s*(?P<verses>\d{1,3}(?:\s*[-–]\s*\d{1,3})?))?)?\s*$")


def in_words(number: int) -> str:
    """A number the way a preacher says it and a speech model may write it down."""
    if number < 20:
        return UNITS[number]
    if number < 100:
        tens, unit = divmod(number, 10)
        if not unit:
            return TENS[tens]
        word = UNITS[unit]
        return word + ("ën" if word.endswith("e") else "en") + TENS[tens]
    hundreds, rest = divmod(number, 100)
    head = "honderd" if hundreds == 1 else UNITS[hundreds] + "honderd"
    return head + (in_words(rest) if rest else "")


def said_number(number: int, words: set[str]) -> bool:
    return str(number) in words or fold(in_words(number)) in words


def book_of(name: str) -> list[str] | None:
    wanted = fold(name)
    for spellings in BOOKS:
        if wanted in {fold(s) for s in spellings}:
            return spellings
    return None


def checked_passage(reference: str, spoken: str) -> str:
    """The passage as the clip names it, or as much of it as can be found there.

    The book has to be named, in any of its spellings. The chapter and verses have to be said
    as well, as a number or as a word, or they are left off: "Efeziërs" is true, "Efeziërs 2:9"
    when the preacher read 2:8 is a mistake under the church's name.
    """
    found = REFERENCE.match(reference.strip()) if reference else None
    if not found:
        return ""
    spellings = book_of(found.group("book"))
    if spellings is None:
        return ""
    words = set(fold(spoken).split())
    if not words & {fold(s) for s in spellings}:
        return ""
    name = f"{found.group('nth')} {spellings[0]}" if found.group("nth") else spellings[0]
    chapter = found.group("chapter")
    if not chapter or not said_number(int(chapter), words):
        return name
    verses = found.group("verses")
    numbers = [int(n) for n in re.findall(r"\d+", verses or "")]
    if numbers and all(said_number(n, words) for n in numbers):
        return f"{name} {chapter}:{'-'.join(str(n) for n in numbers)}"
    return f"{name} {chapter}"


# --- writing ---------------------------------------------------------------------------


class Facts(BaseModel):
    """What there is to go on for one clip."""

    church: str = ""
    title: str = ""
    summary: str = ""
    spoken: str = ""  # the words of the clip itself
    about: str = ""  # what the church said about the service: title, series, speaker
    known: str = ""  # everything a passage may be checked against


def facts_for(project: Project, church: str) -> Facts:
    from .discovery import sermon_context  # the same words the finding of moments was given

    transcript = load_transcript(project) or Transcript()
    spoken = " ".join(s.text.strip() for s in transcript.segments if s.text.strip())
    summary, about, service_words = "", "", ""
    if project.origin is not None:
        service = load_service(project.origin.serviceId)
        if service is not None:
            about = sermon_context(service)
            service_words = f"{service.sermonTitle} {service.series}"
            for candidate in service.candidates:
                if candidate.id == project.origin.candidateId:
                    summary = candidate.summary
    return Facts(church="" if church == DEFAULT_CHURCH else church, title=project.title or "",
                 summary=summary, spoken=spoken, about=about, known=f"{spoken} {service_words}")


def question(facts: Facts) -> str:
    parts = []
    if facts.church:
        parts.append(f"Kerk: {facts.church}")
    if facts.about:
        parts.append(facts.about)
    if facts.title:
        parts.append(f"Titel van het fragment: {facts.title}")
    if facts.summary:
        parts.append(f"Samenvatting: {facts.summary}")
    parts.append(f"Wat er in het fragment gezegd wordt:\n{facts.spoken}")
    return "\n\n".join(parts)


def template(facts: Facts) -> PostDraft:
    """Texts built from what the clip already has, for when the model cannot write them."""
    title = facts.title.strip().rstrip(".")
    lead = f"{title}." if title else ""
    body = " ".join(part for part in (lead, facts.summary.strip()) if part)
    where = f" uit de dienst bij {facts.church}" if facts.church else " uit de dienst"
    whatsapp = f"Een moment{where}: {title}." if title else f"Een moment{where}."
    return PostDraft(instagram=body, facebook=body, whatsapp=whatsapp)


def from_model(answer: LlmPost, facts: Facts) -> PostDraft:
    """What the model wrote, with everything it was not allowed to write taken out again."""
    fallback = template(facts)
    texts = {}
    for platform in PLATFORMS:
        body = clean(getattr(answer, platform, "") or "")
        # A made-up quote under somebody's face is the one mistake a church cannot take back,
        # so a text with one is not used, however good the rest of it is.
        texts[platform] = body if body and honest(body, facts.spoken) else getattr(fallback, platform)
    return PostDraft(**texts, hashtags=[t.lstrip("#") for t in tags(answer.hashtags, TOPICAL_TAGS)],
                     bible=checked_passage(answer.bijbeltekst, facts.known))


def ask_model(facts: Facts, address: str) -> PostDraft:
    from . import discovery

    discovery.check_provider()
    system = SYSTEM.replace("{address}", ADDRESS.get(address, ADDRESS["je"]))
    return from_model(discovery.ask(question(facts), system, LlmPost, EFFORT), facts)


def why_not(exc: Exception) -> str:
    """What the window says when the texts are the plain ones, in a line."""
    from . import discovery

    if isinstance(exc, discovery.NoMoney):
        return "Het Claude-account heeft geen tegoed meer, dus dit is de eenvoudige versie."
    if "API-sleutel" in str(exc):
        return "Er is geen Claude-sleutel ingesteld, dus dit is de eenvoudige versie."
    return "Claude kon de tekst nu niet schrijven, dus dit is de eenvoudige versie."


def write(project_id: str) -> Post:
    """Write the texts for this clip and keep them. Never a reason for anything to fail."""
    from .models import load_project

    project = load_project(project_id)
    if project is None:
        raise ValueError("Clip niet gevonden")
    brand = brands.active()
    facts = facts_for(project, brand.church.churchName)
    post = Post(written=datetime.now(timezone.utc).isoformat(timespec="seconds"))
    if not ON:
        post.draft, post.note = template(facts), "Het schrijven staat uit in config.env (WRITE_POSTS)."
    elif not facts.spoken:
        post.draft, post.note = template(facts), "Deze clip heeft nog geen ondertitels om over te schrijven."
    else:
        try:
            post.draft, post.by = ask_model(facts, brand.share.address), "model"
        except Exception as exc:  # noqa: BLE001  the clip is done; the text can be typed
            print(f"[posttekst] {project_id}: {exc}")
            post.draft, post.note = template(facts), why_not(exc)
    save(project_id, post)
    return post


# --- keeping and showing -----------------------------------------------------------------


def post_file(project_id: str) -> Path:
    return project_dir(project_id) / "post.json"


def load(project_id: str) -> Post | None:
    path = post_file(project_id)
    if not path.is_file():
        return None
    try:
        return Post.model_validate_json(path.read_text(encoding="utf-8"))
    except ValueError:
        return None


def save(project_id: str, post: Post) -> None:
    write_atomic(post_file(project_id), json.dumps(post.model_dump(), indent=2, ensure_ascii=False))


def assemble(draft: PostDraft, platform: str, share: ShareSettings, link: str) -> str:
    """One finished text: the body, and under it the lines that are the church's own."""
    body = getattr(draft, platform, "").strip()
    passage = f"Bijbelgedeelte: {draft.bible}" if any(ch.isdigit() for ch in draft.bible) else ""
    if platform == "whatsapp":
        return f"{body}\n{link}".strip() if link else body
    if platform == "instagram":
        tail = "De hele dienst terugkijken? De link staat in onze bio." if link else ""
        row = " ".join(tags(share.hashtags + draft.hashtags, INSTAGRAM_TAGS))
    else:
        tail = f"De hele dienst terugkijken: {link}" if link else ""
        row = " ".join(tags(share.hashtags, FACEBOOK_TAGS))
    return "\n\n".join(part for part in (body, passage, tail, row) if part)


def view(project: Project, post: Post | None = None) -> dict | None:
    """The texts as the delivery window shows them."""
    post = post or load(project.id)
    if post is None:
        return None
    brand = brands.active()
    link, where = link_for(project, brand.share, brand.church.kerkdienstgemistStation)
    texts = {p: post.own.get(p) or assemble(post.draft, p, brand.share, link) for p in PLATFORMS}
    return {"texts": texts, "own": sorted(post.own), "bible": post.draft.bible, "by": post.by,
            "note": post.note, "written": post.written, "link": link, "linkFrom": where}


def edit(project: Project, platform: str, text: str) -> dict | None:
    """Keep what somebody changed by hand. Putting it back the way it was undoes the edit."""
    if platform not in PLATFORMS:
        raise ValueError(f"Onbekende plek: {platform}")
    post = load(project.id) or Post()
    brand = brands.active()
    link, _where = link_for(project, brand.share, brand.church.kerkdienstgemistStation)
    if not text.strip() or text.strip() == assemble(post.draft, platform, brand.share, link).strip():
        post.own.pop(platform, None)
    else:
        post.own[platform] = text
    save(project.id, post)
    return view(project, post)
