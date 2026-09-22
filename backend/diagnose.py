"""One zip a volunteer can attach to a mail, and nothing sent anywhere by the app.

The bargain this makes is the reason a church council says yes: there is no telemetry, so
nothing about a service leaves the building unless a person decides to attach it. What a
person attaches, they can first read. Hence one file that opens on the cause and one that
holds the evidence, rather than an opaque blob.

What goes in, in the order somebody reading the mail wants it:

    melding.txt       the version, this machine, and what went wrong
    gereedheid.json   the readiness checks, which name half the causes on their own
    logboek.txt       the last few hundred lines the black window said
    instellingen.txt  config.env with the key struck out
    dienst.json       the service that failed, when one was named

The key is struck out twice over: once by the logbook on the way into the file, and again
here on the way into the zip. Neither pass is trusted on its own.
"""

import io
import json
import platform
import shutil
import sys
import zipfile
from datetime import datetime
from pathlib import Path

from . import health, journal, logbook, selftest, settings, version
from .models import ROOT, SERVICES_DIR

CONFIG = ROOT / "config.env"
LOG_LINES = 400

# Settings worth seeing in a report and safe to read out loud. Anything not on this list is
# left out rather than judged, because a list of what is safe stays right as the app grows
# and a list of what is secret does not.
TELLING = ("LLM_PROVIDER", "LLM_MODEL", "LLM_EFFORT", "LLM_PASSAGE_MINUTES", "LLM_TIMEOUT",
           "LLM_MAX_TOKENS", "WHISPER_DEVICE", "WHISPER_MODEL", "WHISPER_COMPUTE",
           "KEEP_WEEKS", "PORT", "HOST", "ALLOWED_ORIGINS", "OLLAMA_URL")


def about_this_machine() -> dict:
    free = shutil.disk_usage(ROOT).free / 1e9
    return {
        "versie": version.full(),
        "besturingssysteem": f"{platform.system()} {platform.release()}",
        "machine": platform.machine(),
        "python": sys.version.split()[0],
        "vrijeSchijfruimteGb": round(free, 1),
        "opgemaakt": datetime.now().isoformat(timespec="seconds"),
    }


def settings_as_text() -> str:
    """config.env as it stands, with the key struck out and comments kept.

    Comments are kept on purpose: a line somebody edited badly is usually visible from what
    they left around it, and that line is often the whole answer.
    """
    try:
        raw = CONFIG.read_text(encoding="utf-8")
    except OSError:
        raw = "(geen config.env gevonden)"
    lines = [logbook.without_secrets(line) for line in raw.splitlines()]
    lines.append("")
    lines.append("--- wat de app hiervan gemaakt heeft ---")
    for name in TELLING:
        said = settings.text(name)
        lines.append(f"{name}={said}" if said else f"{name}= (niet ingevuld)")
    return "\n".join(lines)


def service_as_json(service_id: str) -> str | None:
    """The service that failed, as it sits on disk.

    The written-out text is left out. It is the largest thing in the folder and the most
    personal, and a failure is nearly always visible from the state around it.
    """
    path = SERVICES_DIR / service_id / "service.json"
    try:
        said = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return None
    said.pop("transcript", None)
    said["_let op"] = ("De uitgeschreven tekst zit hier niet bij. Stuur die alleen mee als "
                       "erom gevraagd wordt, en alleen als je kerk daarmee akkoord is.")
    return json.dumps(said, indent=2, ensure_ascii=False)


def first_page(trouble: str, service_id: str | None) -> str:
    """What the reader sees first: the cause, then the machine it happened on."""
    said = [f"Preekstof {version.full()} — melding", ""]
    said.append(trouble.strip() or "Er is geen foutmelding meegegeven; de gebruiker meldde "
                                  "dit vanuit het gereedheidspaneel.")
    said.append("")
    if service_id:
        said.append(f"Ging mis bij dienst: {service_id}")
        said.append("")
    said.append("--- deze computer ---")
    for name, value in about_this_machine().items():
        said.append(f"{name}: {value}")
    said.append("")
    said.append("--- deed deze computer het werk ooit ---")
    proof = selftest.last()
    if not proof:
        said.append("De proef is hier nooit gedraaid. Vraag erom: die zegt binnen een minuut "
                    "welke stap het begeeft, en hij staat onderin het gereedheidspaneel.")
    else:
        when = str(proof.get("at", ""))[:16].replace("T", " ")
        for step in proof.get("steps", []):
            mark = "ok  " if step.get("ok") else "FOUT"
            said.append(f"{mark} {step.get('name', '?')}: {step.get('detail', '')}")
        said.append(f"(de proef liep op {when})")
    said.append("")
    said.append("--- wat er niet klaarstond ---")
    report = health.report()
    missing = [c for c in report["checks"] if not c["ok"]]
    if missing:
        for check in missing:
            said.append(f"{check['name']}: {check['detail']}")
    else:
        said.append("Niets. Alle controles stonden op groen toen dit werd opgemaakt.")
    said.append("")
    said.append("In dit bestand en in de rest van deze zip is de API-sleutel weggelaten.")
    return logbook.without_secrets("\n".join(said))


def name_for(service_id: str | None = None) -> str:
    when = datetime.now().strftime("%Y%m%d-%H%M")
    return f"preekstof-melding-{when}.zip" if not service_id else \
        f"preekstof-melding-{when}-{service_id}.zip"


def build(trouble: str = "", service_id: str | None = None) -> bytes:
    """The whole report, as the bytes of a zip. Nothing is written outside this call."""
    kept = io.BytesIO()
    with zipfile.ZipFile(kept, "w", zipfile.ZIP_DEFLATED) as out:
        out.writestr("melding.txt", first_page(trouble, service_id))
        out.writestr("gereedheid.json", json.dumps(health.report(), indent=2, ensure_ascii=False))
        # Whether this machine ever did the work, as opposed to whether the files are there.
        # It answers the first question a support mail raises and nobody thinks to ask.
        proof = selftest.last()
        if proof:
            out.writestr("proef.json", json.dumps(proof, indent=2, ensure_ascii=False))
        out.writestr("logboek.txt", logbook.without_secrets(logbook.tail(LOG_LINES))
                     or "(er is deze keer niets opgeschreven)")
        out.writestr("instellingen.txt", settings_as_text())
        # What this machine has really done. No church name, no title, no word of anybody's
        # transcript, so it can travel without being read first. It is the whole of what a
        # pilot ever learns in numbers.
        if journal.KEPT.is_file():
            try:
                out.write(journal.KEPT, "runs.jsonl")
            except OSError:
                pass
        if service_id:
            said = service_as_json(service_id)
            if said:
                out.writestr("dienst.json", logbook.without_secrets(said))
    return kept.getvalue()


def write(folder: Path, trouble: str = "", service_id: str | None = None) -> Path:
    """The same report, dropped in a folder. Used by the tests and by hand."""
    target = folder / name_for(service_id)
    target.write_bytes(build(trouble, service_id))
    return target
