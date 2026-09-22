"""What a pilot actually did, out of logs/runs.jsonl.

Four numbers, per the roadmap, and every one of them measured rather than remembered:

    uitschrijven   how long a service takes to write out on this machine
    zoeken         what one search costs and how long it takes
    gekozen        how many of the offered moments got made into clips
    uit de top 5   how many of those were among the five the app put first

The last one is the whole question. If a church makes four clips and three of them were in
the app's top five, the ranking is doing its job. If they were all number nine, it is not,
and no impression of "het werkte wel aardig" would ever have told you.

    .venv/bin/python -m tools.pilot
    .venv/bin/python -m tools.pilot --file ~/meldingen/kruispunt/runs.jsonl --json

Nothing in that file names a church or holds a word of anybody's transcript, so a pilot
church can mail it without reading it first.
"""

import argparse
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend import journal  # noqa: E402


def numbers_of(events: list[dict], what: str, field: str) -> list[float]:
    return [e[field] for e in events
            if e.get("what") == what and isinstance(e.get(field), (int, float))]


def middle(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


def summarise(events: list[dict]) -> dict:
    """The four numbers, plus enough around them to know how much to trust them."""
    audio = numbers_of(events, "uitschrijven", "audio")
    writing = numbers_of(events, "uitschrijven", "seconds")
    per_second = [w / a for a, w in zip(audio, writing) if a > 0]

    offered = numbers_of(events, "clips", "offered")
    made = numbers_of(events, "clips", "made")
    top5 = numbers_of(events, "clips", "fromTop5")

    return {
        "diensten": len(numbers_of(events, "uitschrijven", "seconds")),
        "uitschrijvenMinutenPer90": round(middle(per_second) * 90, 1) if per_second else None,
        "zoekenSeconden": round(middle(numbers_of(events, "zoeken", "seconds")) or 0, 1) or None,
        "zoekenEuro": round(middle(numbers_of(events, "zoeken", "cost")) or 0, 3) or None,
        "zoekenMislukt": int(sum(numbers_of(events, "zoeken", "failed"))),
        "voorgesteld": int(sum(offered)),
        "gemaakt": int(sum(made)),
        "uitDeTop5": int(sum(top5)),
        "zelfGeknipt": int(sum(numbers_of(events, "clips", "ownCuts"))),
        "deelUitTop5": round(sum(top5) / sum(made), 2) if sum(made) else None,
    }


def said(summary: dict) -> str:
    if not summary["diensten"] and not summary["gemaakt"]:
        return ("Er staat nog niets in logs/runs.jsonl. Dat vult zich terwijl de app gebruikt "
                "wordt; kom terug na een paar diensten.")
    lines = [f"{summary['diensten']} diensten uitgeschreven", ""]
    if summary["uitschrijvenMinutenPer90"]:
        lines.append(f"  uitschrijven   {summary['uitschrijvenMinutenPer90']:.0f} minuten "
                     "voor een dienst van anderhalf uur")
    if summary["zoekenSeconden"]:
        lines.append(f"  zoeken         {summary['zoekenSeconden']:.0f} seconden, "
                     f"€ {summary['zoekenEuro']:.2f} per dienst")
    if summary["zoekenMislukt"]:
        lines.append(f"                 {summary['zoekenMislukt']} stukken liepen vast")
    if summary["gemaakt"]:
        lines.append(f"  gekozen        {summary['gemaakt']} van {summary['voorgesteld']} "
                     "voorstellen werden een clip")
        if summary["deelUitTop5"] is not None:
            lines.append(f"  uit de top 5   {summary['uitDeTop5']} van {summary['gemaakt']} "
                         f"({summary['deelUitTop5']:.0%})")
    if summary["zelfGeknipt"]:
        lines.append(f"  zelf geknipt   {summary['zelfGeknipt']} clips kwamen niet uit een voorstel")
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--file", type=Path, default=journal.KEPT, help="which runs.jsonl")
    parser.add_argument("--json", action="store_true", help="the numbers, for a spreadsheet")
    args = parser.parse_args()

    summary = summarise(journal.read(args.file))
    print(json.dumps(summary, indent=2, ensure_ascii=False) if args.json else said(summary))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
