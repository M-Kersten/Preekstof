"""Project data model and on-disk storage.

Layout of a project directory (projects/<id>/):
    project.json      project metadata (this model)
    source.<ext>      the uploaded clip, never modified
    transcript.json   editable subtitle segments
    work/             derived files (audio.wav, subtitles.ass)
    output/final.mp4  the rendered reel
"""

import json
import os
import threading
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

ROOT = Path(__file__).resolve().parent.parent
PROJECTS_DIR = ROOT / "projects"
TEMPLATES_DIR = ROOT / "templates"
FONTS_DIR = TEMPLATES_DIR / "fonts"

FontWeight = Literal["regular", "medium", "semibold", "bold", "extrabold"]
CropStrategy = Literal["static", "tracked"]  # "tracked": the crop follows the speaker


Corner = Literal["topLeft", "topRight", "bottomLeft", "bottomRight"]


class Watermark(BaseModel):
    """A logo in a corner of the clip. Files live in templates/logos."""

    file: str = ""  # empty means no logo
    corner: Corner = "topRight"
    width: float = Field(default=0.18, ge=0.04, le=0.5)  # share of the video width
    opacity: float = Field(default=0.85, ge=0.05, le=1.0)
    margin: int = Field(default=60, ge=0, le=300)  # pixels from the edges


class MusicSettings(BaseModel):
    """Background music under the clip. Files live in templates/music."""

    file: str = ""  # empty means no music
    volume: float = Field(default=0.15, ge=0.0, le=1.0)
    duck: bool = True  # turn the music down while someone is speaking
    fadeOut: float = Field(default=2.0, ge=0.0, le=10.0)


SubtitleAnimation = Literal["none", "fade", "pop", "slide"]


class Style(BaseModel):
    font: str = "Montserrat"
    fontSize: int = Field(default=64, ge=24, le=200)
    fontWeight: FontWeight = "bold"
    color: str = "#FFFFFF"
    outline: int = Field(default=4, ge=0, le=12)
    outlineColor: str = "#000000"
    background: bool = False
    animation: SubtitleAnimation = "fade"  # how a line appears
    animationSpeed: int = Field(default=180, ge=60, le=600)  # milliseconds
    # Light up each word as it is said. Half of social video is watched muted, and a caption
    # that keeps time with the voice is what tells a viewer there is a voice worth unmuting.
    highlight: bool = False
    highlightColor: str = "#C9971C"


class Output(BaseModel):
    width: int = 1080
    height: int = 1920
    fps: int = 30


class Spoken(BaseModel):
    """One word and when it was said, for lighting it up as it is spoken."""

    start: float
    end: float
    word: str


class Segment(BaseModel):
    start: float
    end: float
    text: str
    # Whisper hands back a time per word. Kept, because a caption that lights up word by word
    # is what the format asks for. Editing the text can leave these out of step with it, so
    # nothing may trust them without checking: see subtitles.word_times.
    words: list[Spoken] = []


class Transcript(BaseModel):
    language: str = "nl"
    segments: list[Segment] = []


class VideoInfo(BaseModel):
    width: int
    height: int
    duration: float
    fps: float
    videoCodec: str | None = None
    hasAudio: bool = False
    audioCodec: str | None = None
    audioSampleRate: int | None = None
    audioChannels: int | None = None


class ClipOrigin(BaseModel):
    """Where a clip project was cut from (set by the service discovery layer)."""

    serviceId: str
    candidateId: str | None = None
    start: float
    end: float


class Track(BaseModel):
    """A path for the crop window to walk, one x per sample, evenly spaced from the start.

    x is the centre of the frame as a fraction of the scaled source, the same units as
    CropWindow.x, so a track and a static window are read the same way. The renderer and
    the preview both interpolate between samples; frontend/src/track.ts is the copy.
    """

    fps: float = 12.5
    x: list[float] = []
    coverage: float = 0.0  # how much of the clip the speaker was actually found in
    subject: str = ""  # "face" or "person": what it mostly had to go on
    # A speaker who is small in a wide shot is worth cropping in on, and cropping in makes
    # the vertical position matter. Both are a starting point the user is free to move;
    # neither changes while the clip plays.
    zoom: float | None = None
    y: float | None = None
    cuts: list[float] = []  # seconds where the camera changed
    # Samples the frame jumped to rather than glided into. Nothing may interpolate across
    # one, or a cut turns back into the fast pan across the room it was meant to replace.
    jumps: list[int] = []
    enough: bool = False  # False: found too little to be worth offering


class CropWindow(BaseModel):
    """Where the 9:16 output frame sits on the source.

    x, y: centre of the frame as a fraction of the scaled source (0.5 = centred).
    zoom: relative to the scale that exactly fills the frame; 1.0 fills it, smaller values
          letterbox the source, larger values crop in further. Part 2 can animate these.
    """

    x: float = Field(default=0.5, ge=0.0, le=1.0)
    y: float = Field(default=0.5, ge=0.0, le=1.0)
    zoom: float = Field(default=1.0, gt=0.0, le=4.0)


class Project(BaseModel):
    id: str
    createdAt: str
    title: str | None = None  # names the downloaded file; the text under a post is in post.json
    origin: ClipOrigin | None = None
    # A clip either owns its footage (a file in the project directory) or points into the
    # service recording it was cut from. Pointing avoids a second encode of every clip;
    # materialise() in clips.py turns a pointer into a file when the recording has to go.
    sourceVideo: str | None = None  # file name inside the project directory
    sourceInfo: VideoInfo | None = None
    transcript: str | None = None  # "transcript.json" once a transcript exists
    style: Style = Style()
    output: Output = Output()
    outro: str = "templates/outro.mp4"  # relative to the repository root
    music: MusicSettings = MusicSettings()
    watermark: Watermark = Watermark()
    cropStrategy: CropStrategy = "static"
    crop: CropWindow | None = None  # None = default framing for the source (see renderer.default_crop)
    track: Track | None = None  # the path the crop walks when cropStrategy is "tracked"


class ProjectDetail(Project):
    """Project plus its transcript, as returned by GET /projects/{id}."""

    transcriptData: Transcript | None = None
    # Seconds into /projects/{id}/source where this clip begins. Zero when the clip owns
    # its own file; the offset into the recording when it points at a service.
    sourceStart: float = 0.0
    hasFootage: bool = True


class Vocabulary(BaseModel):
    """The words this church uses that a speech model would not guess.

    Names cost the most: a wrong preacher name in a clip that goes out in public is the
    error nobody forgives, and it is the one the model repeats every single week.
    """

    preachers: list[str] = []  # who preaches here
    series: list[str] = []  # the series a sermon belongs to, when the church runs them
    songbooks: list[str] = []  # Opwekking, Psalmen voor Nu, the hymnal they sing from
    places: list[str] = []  # locations, neighbourhoods, buildings
    extra: list[str] = []  # anything else worth spelling out for the model
    corrections: dict[str, str] = {}  # what it keeps hearing -> what was said

    def words(self) -> list[str]:
        """Everything, in one list, for the prompt that goes in front of the audio."""
        return [w for group in (self.preachers, self.series, self.songbooks, self.places, self.extra)
                for w in group if w.strip()]


class ChurchInfo(BaseModel):
    churchName: str = "Example Church"
    serviceTimes: list[str] = ["09:30", "11:30"]
    instagram: str = "@examplechurch"
    # The number in the address of this church's page on kerkdienstgemist.nl. With it, the
    # services can be listed and fetched without leaving the app.
    kerkdienstgemistStation: str = ""


Address = Literal["je", "u"]


class ShareSettings(BaseModel):
    """How this church puts its clips out. Set once, and used for every clip after that."""

    # Shapes made every time next to the upright one ("4x5", "1x1"). Each one is another
    # render, so this starts empty and a church adds what it actually posts.
    shapes: list[str] = []
    # How a post speaks to its reader. Churches differ on this more than on almost anything
    # else a stranger would notice, and a post in the wrong one reads as somebody else's.
    address: Address = "je"
    hashtags: list[str] = []  # under every post, before the ones that belong to the clip
    link: str = ""  # where the whole service can be watched; empty: the page it came from


# --- storage -----------------------------------------------------------------


# Windows refuses to rename onto a file that anything else has open, and "anything else"
# includes the virus scanner reading the file we just finished writing. It lets go within a
# moment, so this waits rather than gives up: ten tries over about a second and a half.
REPLACE_TRIES = 10
REPLACE_WAIT = 0.03

_writing: dict[str, threading.Lock] = {}
_writing_guard = threading.Lock()


def _writer_for(path: Path) -> threading.Lock:
    """One writer at a time per file, so two threads here never race for the same name."""
    with _writing_guard:
        return _writing.setdefault(str(path), threading.Lock())


def write_atomic(path: Path, text: str) -> None:
    """Write through a temporary file, so a crash never leaves a half-written file behind.

    The temporary name carries the process and the thread, because a job thread and a request
    thread saving the same service at the same moment used to fight over one ".tmp" and, on
    Windows, lose: the rename came back as "Access is denied" and the status never got written
    down. What that looked like was a page waiting for work that had already stopped.

    A rename that keeps failing is followed by writing straight over the file. That gives up
    the crash-safety for the length of one write, which beats losing what was written.
    """
    with _writer_for(path):
        # The process because another copy of the app may be running, and a fresh random tail
        # because thread ids are handed out again once a thread is done with them.
        tmp = path.with_name(f"{path.name}.{os.getpid()}.{uuid.uuid4().hex[:8]}.tmp")
        try:
            tmp.write_text(text, encoding="utf-8")
            for attempt in range(REPLACE_TRIES):
                try:
                    os.replace(tmp, path)
                    return
                except PermissionError:
                    if attempt == REPLACE_TRIES - 1:
                        break
                    time.sleep(REPLACE_WAIT * (attempt + 1))
            try:
                path.write_text(text, encoding="utf-8")
            except OSError as exc:
                raise OSError(
                    f"{path.name} kon niet opgeslagen worden: een ander programma houdt het "
                    f"bestand vast. Een virusscanner of een geopende map doet dat soms. ({exc})"
                ) from exc
        finally:
            tmp.unlink(missing_ok=True)


def project_dir(project_id: str) -> Path:
    return PROJECTS_DIR / project_id


def new_project() -> Project:
    project = Project(
        id="project-" + uuid.uuid4().hex[:8],
        createdAt=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )
    (project_dir(project.id) / "work").mkdir(parents=True)
    (project_dir(project.id) / "output").mkdir()
    save_project(project)
    return project


def load_project(project_id: str) -> Project | None:
    path = project_dir(project_id) / "project.json"
    if not path.is_file():
        return None
    return Project.model_validate_json(path.read_text(encoding="utf-8"))


def save_project(project: Project) -> None:
    write_atomic(project_dir(project.id) / "project.json", project.model_dump_json(indent=2))


def load_transcript(project: Project) -> Transcript | None:
    if not project.transcript:
        return None
    path = project_dir(project.id) / project.transcript
    if not path.is_file():
        return None
    return Transcript.model_validate_json(path.read_text(encoding="utf-8"))


def save_transcript(project: Project, transcript: Transcript) -> None:
    project.transcript = "transcript.json"
    write_atomic(project_dir(project.id) / project.transcript,
                 json.dumps(transcript.model_dump(), indent=2, ensure_ascii=False))
    save_project(project)


def load_church_info() -> ChurchInfo:
    path = TEMPLATES_DIR / "church.json"
    if path.is_file():
        return ChurchInfo.model_validate_json(path.read_text(encoding="utf-8"))
    return ChurchInfo()


class OutroBackground(BaseModel):
    type: Literal["solid", "gradient", "image"] = "gradient"
    color: str = "#4B1E78"  # used when type is "solid"
    colors: list[str] = ["#C8801B", "#9B1B3A", "#5B1B6E"]  # used when type is "gradient", 2 to 8 colours
    angle: float = 115  # gradient direction in degrees; 0 = left to right, 90 = top to bottom
    image: str = ""  # file name in templates/, used when type is "image"
    darken: float = Field(default=0.35, ge=0.0, le=1.0)  # black veil over the image, for readable text


class OutroLogo(BaseModel):
    file: str = ""  # png (transparency supported) in templates/
    width: int = 420
    y: int = 600  # centre of the logo, in pixels from the top of the 1080x1920 frame


class OutroLine(BaseModel):
    text: str
    y: int = 960  # centre of the line, in pixels from the top
    align: Literal["left", "center", "right"] = "center"
    size: int = 56
    weight: FontWeight = "bold"
    color: str = "#FFFFFF"
    font: str = ""  # empty = the config's main font
    spacing: float = 0  # extra letter spacing in pixels
    uppercase: bool = False
    delay: float = 0.0  # seconds before this line appears


OutroMotion = Literal["none", "in", "out", "up"]


class OutroConfig(BaseModel):
    generate: bool = True  # false: never touch outro.mp4 (you supply your own video)
    duration: float = Field(default=5.0, ge=1.0, le=30.0)
    motion: OutroMotion = "none"  # a slow dolly, so the end screen is not a still image
    font: str = "Poppins"  # Inter, Montserrat, Poppins or Arial
    fade: float = Field(default=0.4, ge=0.0, le=3.0)  # fade in and out, in seconds
    background: OutroBackground = OutroBackground()
    logo: OutroLogo = OutroLogo()
    lines: list[OutroLine] = [
        OutroLine(text="Welkom", y=760, size=34, weight="bold", color="#F0C862", spacing=8, uppercase=True),
        OutroLine(text="{churchName}", y=860, size=92, weight="extrabold", delay=0.1),
        OutroLine(text="Elke zondag {serviceTimes}", y=1000, size=46, weight="medium", color="#E7DEF2", delay=0.25),
        OutroLine(text="{instagram}", y=1180, size=52, weight="bold", delay=0.4),
    ]



# --- full-service discovery -------------------------------------------------
#
# A Service is a complete recording. Discovery produces ClipCandidates (the AI
# thinks this range could work); processing a candidate creates a regular
# Project through backend/clips.py and is recorded as a ProcessedClip.

SERVICES_DIR = ROOT / "services"

ServiceStatus = Literal[
    "created", "fetching", "uploaded", "transcribing", "transcribed", "analyzing", "ready",
    "processing", "complete", "error"
]


class TimeRange(BaseModel):
    start: float
    end: float


# Where a moment came from. "self" is one somebody cut out of the transcript themselves,
# which the search may never touch: it was a deliberate act, and a run that came back after
# it must not be able to throw it away.
CandidateSource = Literal["found", "self"]


class ClipCandidate(BaseModel):
    id: str
    start: float
    end: float
    title: str
    summary: str = ""
    reason: str = ""
    confidence: float = 0.5
    selected: bool = False
    score: float = 0.0  # internal sort key, not shown as a number in the UI
    alternateBoundaries: list[TimeRange] = []
    # Filled in by the second pass, which weighs every proposal against all the others.
    shortlisted: bool = True  # False: found, but another moment was judged better
    verdict: str = ""  # why it was picked, or why it was passed over
    part: str = ""  # which part of the service it comes from
    source: CandidateSource = "found"  # older services have no hand-cut moments in them


class ProcessedClip(BaseModel):
    candidateId: str
    projectId: str
    title: str
    start: float
    end: float
    createdAt: str


class Service(BaseModel):
    id: str
    createdAt: str
    title: str = "Service"
    sourceVideo: str | None = None
    sourceInfo: VideoInfo | None = None
    transcript: str | None = None
    status: ServiceStatus = "created"
    error: str | None = None
    warning: str | None = None  # analysis finished, but not every part of the text worked
    accurate: bool = False  # hear the clips of this recording with the slower, better model
    sermonTitle: str = ""  # what the preaching was about, when the church knows it beforehand
    series: str = ""  # the series it belongs to, if there is one
    preacher: str = ""  # who spoke, as the church wrote it on its own page
    poster: str | None = None  # our own copy of the platform's still, next to the recording
    link: str = ""  # the page it was fetched from, where anybody can watch the whole service
    shape: list[dict] = []  # the parts of the service: welcome, songs, sermon, notices...
    candidates: list[ClipCandidate] = []
    clips: list[ProcessedClip] = []


class ServiceDetail(Service):
    posterUrl: str | None = None  # where the browser gets the still; `poster` is the file
    transcriptData: Transcript | None = None
    analysis: dict | None = None  # what an analysis run would send and cost
    job: dict | None = None


def service_dir(service_id: str) -> Path:
    return SERVICES_DIR / service_id


def new_service() -> Service:
    service = Service(
        id="service-" + uuid.uuid4().hex[:8],
        createdAt=datetime.now(timezone.utc).isoformat(timespec="seconds"),
    )
    (service_dir(service.id) / "work").mkdir(parents=True)
    save_service(service)
    return service


def load_service(service_id: str) -> Service | None:
    path = service_dir(service_id) / "service.json"
    if not path.is_file():
        return None
    return Service.model_validate_json(path.read_text(encoding="utf-8"))


def save_service(service: Service) -> None:
    write_atomic(service_dir(service.id) / "service.json", service.model_dump_json(indent=2))


def load_service_transcript(service: Service) -> Transcript | None:
    if not service.transcript:
        return None
    path = service_dir(service.id) / service.transcript
    if not path.is_file():
        return None
    return Transcript.model_validate_json(path.read_text(encoding="utf-8"))


def save_service_transcript(service: Service, transcript: Transcript) -> None:
    service.transcript = "transcript.json"
    write_atomic(service_dir(service.id) / service.transcript,
                 json.dumps(transcript.model_dump(), indent=2, ensure_ascii=False))
    save_service(service)


# Where an interrupted step leaves the service, and what to tell the user about carrying on.
# The work done so far is on disk, so pressing the same button again continues it.
RESUME_AFTER = {
    "transcribing": ("uploaded",
                     "De app is gestopt tijdens het uitschrijven. Klik op Uitschrijven om verder "
                     "te gaan; wat al uitgeschreven was blijft staan."),
    "analyzing": ("transcribed",
                  "De app is gestopt tijdens het zoeken. Klik op Beste momenten zoeken om verder "
                  "te gaan; de stukken die al gelukt waren worden overgeslagen."),
    "processing": ("ready",
                   "De app is gestopt tijdens het klaarzetten van de fragmenten. Klik opnieuw op "
                   "Gekozen fragmenten verwerken."),
}


def recover_services() -> list[str]:
    """After a restart no job is running any more. Put each interrupted service back on the
    step before, with a note saying it can be continued."""
    stopped = []
    if not SERVICES_DIR.is_dir():
        return stopped
    for path in SERVICES_DIR.glob("*/service.json"):
        try:
            service = Service.model_validate_json(path.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001  a damaged file should not stop the app from starting
            continue
        if service.status in RESUME_AFTER:
            service.status, service.warning = RESUME_AFTER[service.status]
            save_service(service)
            stopped.append(service.id)
    return stopped
