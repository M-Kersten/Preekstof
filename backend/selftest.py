"""Ten seconds through the whole chain, so nobody finds out on a Sunday.

Every check in the readiness panel asks whether a file is where it should be. None of them
asks whether the work runs. Those are different questions, and the gap between them is
where a pilot church loses its first afternoon: FFmpeg is present but was built without
libass, the speech model is in the cache but the card it wants to decode on cannot be used,
onnxruntime imports and then falls over on the first frame.

So this does the work. Four steps, the same code paths a real service takes, over a sentence
that ships with the app:

    geluid        pull the audio out, which is FFmpeg and ffprobe
    uitschrijven  load the model and read the sentence back
    volgen        look through the frames for a face, which is onnxruntime and the models
    clip          render 9:16 with a caption burned in, which is libass, x264 and AAC

Each step says whether it ran and how long it took. A step that fails stops the ones that
need it and lets the others go on, because "everything is broken" and "the render is broken"
are answers of very different worth to somebody reading a support mail.

Nothing here is a measurement of quality. It is a measurement of whether the machine can do
the work at all, which is the thing nobody currently knows until twenty minutes in.
"""

import shutil
import subprocess
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

from . import renderer, subtitles, tracking, transcription, vision
from .models import ROOT, Output, Style, Transcript

SAMPLE = ROOT / "selftest" / "proef.opus"
SECONDS = 8.7

# Beside the log, because that is where the things somebody may have to send from live, and
# it is already swept and already out of git. Nothing in here is worth keeping.
WORK = ROOT / "logs" / "zelftest"
KEPT = ROOT / "logs" / "zelftest.json"

# Words out of the spoken sentence that survive a rough machine voice. Not the whole
# sentence: whisper mishears a synthetic voice the way it mishears a bad microphone, and a
# test that wants every word back fails on a machine that works perfectly well.
ANCHORS = ("dit", "is", "een", "zin", "deze", "computer", "uitschrijven", "app")
ENOUGH = 0.5  # this share of them back means the model really read it

Report = Callable[[float, str], None]


@dataclass
class Outcome:
    step: str
    name: str
    ok: bool
    detail: str
    seconds: float = 0.0
    skipped: bool = False

    def as_dict(self) -> dict:
        return {"step": self.step, "name": self.name, "ok": self.ok, "detail": self.detail,
                "seconds": round(self.seconds, 1), "skipped": self.skipped}


@dataclass
class Result:
    outcomes: list[Outcome] = field(default_factory=list)
    clip: Path | None = None
    heard: str = ""

    @property
    def ok(self) -> bool:
        return all(o.ok for o in self.outcomes)

    def as_dict(self) -> dict:
        return {"ok": self.ok, "heard": self.heard,
                "steps": [o.as_dict() for o in self.outcomes]}


def remember(result: "Result") -> None:
    """Keep the outcome, so the report can say whether this machine ever did the work."""
    import json
    from datetime import datetime, timezone

    said = result.as_dict() | {"at": datetime.now(timezone.utc).isoformat(timespec="seconds")}
    try:
        KEPT.parent.mkdir(parents=True, exist_ok=True)
        KEPT.write_text(json.dumps(said, indent=2, ensure_ascii=False), encoding="utf-8")
    except OSError:
        pass


def last() -> dict | None:
    """What the last run said, or nothing when it has never been run here."""
    import json

    try:
        said = json.loads(KEPT.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    return said if isinstance(said, dict) else None


def ffmpeg() -> str:
    """The FFmpeg this app would use, whether it is on PATH or the one it downloaded."""
    found = shutil.which("ffmpeg")
    if found:
        return found
    tools = ROOT / "tools" / "ffmpeg"
    for candidate in (tools / "ffmpeg.exe", tools / "ffmpeg"):
        if candidate.is_file():
            return str(candidate)
    raise RuntimeError("FFmpeg is niet gevonden. Sluit de app en start opnieuw met start.bat "
                       "of start.command; FFmpeg wordt dan opgehaald.")


def make_video(work: Path) -> Path:
    """A little video with the sentence under it, made on the spot rather than shipped.

    Landscape, because that is what comes off a church's camera and what the crop has to
    work from. The picture is a test pattern: what the next steps need from it is frames to
    read, and a photograph of somebody would be a photograph of somebody.
    """
    target = work / "proef.mp4"
    subprocess.run(
        [ffmpeg(), "-y", "-loglevel", "error",
         "-f", "lavfi", "-i", f"testsrc=size=1280x720:rate=25:duration={SECONDS:.1f}",
         "-i", str(SAMPLE),
         "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
         "-c:a", "aac", "-b:a", "64k", "-shortest", str(target)],
        check=True, capture_output=True, timeout=180)
    return target


def said_back(heard: Transcript) -> tuple[int, str]:
    """How many of the words we know are in there came back, and what was read."""
    text = " ".join(s.text for s in heard.segments).strip()
    lowered = text.lower()
    return sum(1 for word in ANCHORS if word in lowered), text


def step_geluid(work: Path) -> tuple[Outcome, Path | None]:
    began = time.monotonic()
    try:
        video = make_video(work)
        info = renderer.probe(video)
        wav = work / "proef.wav"
        transcription.extract_audio(video, wav, duration=SECONDS)
        if not wav.is_file() or wav.stat().st_size < 1000:
            raise RuntimeError("Het geluid kwam er niet uit.")
    except subprocess.CalledProcessError as exc:
        said = (exc.stderr or b"").decode("utf-8", "replace")[-300:]
        return Outcome("geluid", "Geluid", False,
                       f"FFmpeg kon geen testvideo maken. {said}", time.monotonic() - began), None
    except Exception as exc:  # noqa: BLE001
        return Outcome("geluid", "Geluid", False, str(exc), time.monotonic() - began), None
    if not info.hasAudio:
        return Outcome("geluid", "Geluid", False, "De testvideo kwam zonder geluid terug.",
                       time.monotonic() - began), None
    return Outcome("geluid", "Geluid", True,
                   f"{info.width}×{info.height}, geluid eruit gehaald", time.monotonic() - began), video


def step_uitschrijven(work: Path, report: Report | None = None) -> tuple[Outcome, str]:
    """Read the sentence back. On a machine that has never done this, a 460 MB download
    happens in here, and it says so; this is the likeliest place for it to happen at all."""
    began = time.monotonic()
    said = report or (lambda _f, _m: None)
    try:
        heard = transcription.transcribe(work / "proef.wav", work / "tekst",
                                         duration=SECONDS, how=transcription.scanning(),
                                         on_progress=lambda f, phase: said(0.15 + 0.45 * f, phase))
    except Exception as exc:  # noqa: BLE001
        return Outcome("uitschrijven", "Uitschrijven", False, str(exc),
                       time.monotonic() - began), ""
    took = time.monotonic() - began
    back, text = said_back(heard)
    where = "op de grafische chip" if transcription.engine() == transcription.MLX else "op de processor"
    if back < len(ANCHORS) * ENOUGH:
        return Outcome("uitschrijven", "Uitschrijven", False,
                       f"Het model draaide {where}, maar las er iets anders in: “{text}”. "
                       "Dat wijst op geluid dat niet aankwam of een model dat half gedownload is.",
                       took), text
    note = f" {transcription.DEVICE_NOTE}" if transcription.DEVICE_NOTE else ""
    return Outcome("uitschrijven", "Uitschrijven", True,
                   f"{back} van de {len(ANCHORS)} woorden terug, {where}.{note}", took), text


def step_volgen(work: Path, video: Path) -> Outcome:
    began = time.monotonic()
    try:
        vision.ensure_models()
        info = renderer.probe(video)
        found = tracking.build(video, info, Output(),
                               renderer.default_crop(info, Output()), length=SECONDS)
    except Exception as exc:  # noqa: BLE001
        return Outcome("volgen", "Spreker volgen", False, str(exc), time.monotonic() - began)
    took = time.monotonic() - began
    # The test picture has no face in it, and that is the answer we expect. What this proves
    # is that the models load and the detector runs over every frame without falling over.
    both = "Gezichten en personen" if vision.PERSON_MODEL.is_file() else "Alleen gezichten"
    return Outcome("volgen", "Spreker volgen", True,
                   f"{both} nagekeken, {len(found.x)} punten over {SECONDS:.0f} seconden. Het "
                   "testbeeld heeft geen gezicht, dus er valt niets te volgen; het gaat erom "
                   "dat de modellen laadden en over elk beeld liepen.",
                   took)


def step_clip(work: Path, video: Path, heard: str) -> tuple[Outcome, Path | None]:
    began = time.monotonic()
    target = work / "proefclip.mp4"
    try:
        info = renderer.probe(video)
        words = Transcript(language="nl", segments=[])
        from .models import Segment

        words.segments = [Segment(start=0.2, end=SECONDS - 0.2,
                                  text=heard[:60] or "Preekstof werkt op deze computer")]
        ass = subtitles.write_ass(words, Style(), Output(), work / "proef.ass")
        renderer.render_video(video, info, ass, Output(), target)
    except Exception as exc:  # noqa: BLE001
        return Outcome("clip", "Clip maken", False, str(exc), time.monotonic() - began), None
    took = time.monotonic() - began
    if not target.is_file() or target.stat().st_size < 10_000:
        return Outcome("clip", "Clip maken", False,
                       "De clip kwam leeg terug. Dat is meestal een FFmpeg zonder libass.",
                       took), None
    size = target.stat().st_size / 1e6
    return Outcome("clip", "Clip maken", True,
                   f"1080×1920 met ondertitel, {size:.1f} MB", took), target


def run(work: Path, on_progress: Report | None = None) -> Result:
    """The four steps, in order, over a folder this call owns."""
    report = on_progress or (lambda _f, _m: None)
    work.mkdir(parents=True, exist_ok=True)
    result = Result()

    report(0.02, "Testvideo wordt gemaakt")
    geluid, video = step_geluid(work)
    result.outcomes.append(geluid)
    if video is None:
        for step, name in (("uitschrijven", "Uitschrijven"), ("volgen", "Spreker volgen"),
                           ("clip", "Clip maken")):
            result.outcomes.append(Outcome(step, name, False,
                                           "Overgeslagen: er was geen testvideo om mee te werken.",
                                           skipped=True))
        return result

    report(0.15, "Het spraakmodel leest de zin terug")
    uitschrijven, heard = step_uitschrijven(work, report)
    result.outcomes.append(uitschrijven)
    result.heard = heard

    report(0.6, "De beelden worden nagekeken op een gezicht")
    result.outcomes.append(step_volgen(work, video))

    report(0.8, "Er wordt een clip van gemaakt")
    clip, made = step_clip(work, video, heard)
    result.outcomes.append(clip)
    result.clip = made

    report(1.0, "Klaar")
    return result


def clip_path() -> Path | None:
    """The clip the last run left behind, when it is still there."""
    made = WORK / "proefclip.mp4"
    return made if made.is_file() else None
