"""Turn a service this app has done into a case the evaluation set can measure.

Five real services turn tools/evaluate.py from a harness into an instrument, and they only
exist while a pilot is running. What the harness needs is the transcript and the moments
the church actually posted, and both of those already sit in a service folder. Copying them
across by hand means opening two JSON files and lining up timecodes, which is exactly the
sort of chore that ends with four services instead of five.

    .venv/bin/python -m tools.adopt service-a1b2c3d4
    .venv/bin/python -m tools.adopt service-a1b2c3d4 --as 2026-03-08-rust --set ~/diensten

Which moments count as posted: the clips that were actually made. A church that cut four
clips out of a service put those four out, and the suggestions they ignored are the ones
the app should learn it got wrong. Nothing is guessed; a service with no clips is refused
rather than adopted with an empty answer key.

Permission first. See evaluation/TOESTEMMING.md; a transcript is not the app's to keep.
"""

import argparse
import json
import shutil
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.models import SERVICES_DIR  # noqa: E402

DEFAULT_SET = ROOT / "evaluation"


def read(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def posted_from(service: dict) -> list[dict]:
    """The moments that were really put out: one per clip that was made.

    A clip carries the piece of the recording it was cut from, which is the honest answer to
    "what did this church post". A suggestion nobody turned into a clip is not an answer.
    """
    out = []
    for clip in service.get("clips") or []:
        start, end = clip.get("start"), clip.get("end")
        if not isinstance(start, (int, float)) or not isinstance(end, (int, float)) or end <= start:
            continue
        out.append({"start": round(float(start), 1), "end": round(float(end), 1),
                    "note": (clip.get("title") or "").strip()})
    out.sort(key=lambda m: m["start"])
    return out


def adopt(service_id: str, into: Path, name: str | None = None) -> Path:
    folder = SERVICES_DIR / service_id
    meta_path, transcript_path = folder / "service.json", folder / "transcript.json"
    if not meta_path.is_file():
        raise SystemExit(f"{service_id} bestaat niet in {SERVICES_DIR}.")
    if not transcript_path.is_file():
        raise SystemExit(f"{service_id} is nog niet uitgeschreven; er valt niets te meten.")

    service = read(meta_path)
    posted = posted_from(service)
    if not posted:
        raise SystemExit(
            f"{service_id} heeft geen gemaakte clips, dus er is geen antwoordblad. Maak eerst "
            "de clips die de kerk ook echt gepost heeft, en probeer het dan opnieuw.")

    target = into / (name or service_id)
    target.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(transcript_path, target / "transcript.json")
    duration = (service.get("sourceInfo") or {}).get("duration")
    (target / "service.json").write_text(json.dumps({
        "title": service.get("title") or service_id,
        "duration": duration,
        "sermonTitle": service.get("sermonTitle") or "",
        "series": service.get("series") or "",
        "preacher": service.get("preacher") or "",
        # Filled in by hand: which church, and that they said yes. The harness ignores both;
        # they are here because a transcript without them should not be in this folder.
        "church": "VUL IN",
        "permission": "VUL IN: wie gaf toestemming, wanneer, en waarvoor",
        "posted": posted,
    }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return target


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("service", help="the id of a service, as services/<id>")
    parser.add_argument("--as", dest="name", default=None, help="what to call the case")
    parser.add_argument("--set", type=Path, default=DEFAULT_SET, help="where the cases live")
    args = parser.parse_args()

    target = adopt(args.service, args.set, args.name)
    said = read(target / "service.json")
    print(f"{target}")
    print(f"  {len(said['posted'])} geposte momenten, uit de clips die gemaakt zijn:")
    for moment in said["posted"]:
        print(f"    {moment['start']:7.0f}s – {moment['end']:7.0f}s  {moment['note']}")
    print()
    print("Vul in service.json nog 'church' en 'permission' in. Zonder toestemming op papier")
    print("hoort een uitgeschreven dienst hier niet te staan; zie evaluation/TOESTEMMING.md.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
