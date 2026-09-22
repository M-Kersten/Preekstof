"""Measure how good the moment-finding actually is, on services whose answers are known.

Prompt changes feel like improvements. This is the only way to find out whether they are:
run the pipeline over services where somebody already decided what was worth posting, and
count how many of those it puts in front of you.

    .venv/bin/python -m tools.evaluate                 # every service in evaluation/
    .venv/bin/python -m tools.evaluate --dry-run       # what it would cost, unspent
    .venv/bin/python -m tools.evaluate --save baseline.json
    .venv/bin/python -m tools.evaluate --compare baseline.json
"""

import argparse
import json
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend import discovery, structure  # noqa: E402
from backend.models import ClipCandidate, Transcript  # noqa: E402

DEFAULT_SET = ROOT / "evaluation"
HIT = 0.5  # a proposal counts when it covers half of a moment that was posted


@dataclass
class Posted:
    start: float
    end: float
    note: str = ""


@dataclass
class Case:
    """One service, and the moments its church actually put out."""

    name: str
    title: str
    transcript: Transcript
    posted: list[Posted]
    duration: float | None = None
    about: str = ""

    @property
    def sermon_minutes(self) -> float:
        shape = structure.blocks(self.transcript.segments, self.duration)
        return sum(b.seconds for b in shape if b.part == "preek") / 60


@dataclass
class Score:
    """How one service went."""

    name: str
    posted: int
    found: int
    shortlisted: int
    hits_at_5: int = 0
    hits_total: int = 0
    seconds: float = 0.0
    cost: float = 0.0
    windows: int = 0  # passages sent to the model
    skipped_minutes: int = 0
    misses: list[str] = field(default_factory=list)

    @property
    def precision_at_5(self) -> float:
        return self.hits_at_5 / min(5, max(1, self.shortlisted))

    @property
    def recall(self) -> float:
        return self.hits_total / max(1, self.posted)

    def as_dict(self) -> dict:
        return {"name": self.name, "posted": self.posted, "found": self.found,
                "shortlisted": self.shortlisted, "hitsAt5": self.hits_at_5,
                "hitsTotal": self.hits_total, "precisionAt5": round(self.precision_at_5, 3),
                "recall": round(self.recall, 3), "seconds": round(self.seconds, 1),
                "cost": round(self.cost, 3), "windows": self.windows, "skippedMinutes": self.skipped_minutes,
                "misses": self.misses}


def overlap(a: Posted, b: ClipCandidate) -> float:
    """How much of the posted moment a proposal covers."""
    shared = min(a.end, b.end) - max(a.start, b.start)
    return max(0.0, shared) / max(1e-6, a.end - a.start)


def load_cases(folder: Path) -> list[Case]:
    cases = []
    for meta_path in sorted(folder.glob("*/service.json")):
        meta = json.loads(meta_path.read_text(encoding="utf-8"))
        transcript_path = meta_path.parent / "transcript.json"
        if not transcript_path.is_file():
            print(f"  ! {meta_path.parent.name} heeft geen transcript.json, overgeslagen")
            continue
        transcript = Transcript.model_validate_json(transcript_path.read_text(encoding="utf-8"))
        about = []
        if meta.get("sermonTitle"):
            about.append(f"De preek van deze dienst heet: {meta['sermonTitle']}.")
        if meta.get("series"):
            about.append(f"Hij hoort bij de serie: {meta['series']}.")
        cases.append(Case(
            name=meta_path.parent.name,
            title=meta.get("title", meta_path.parent.name),
            transcript=transcript,
            posted=[Posted(**p) for p in meta.get("posted", [])],
            duration=meta.get("duration"),
            about=" ".join(about),
        ))
    return cases


def run_case(case: Case) -> Score: 
    started = time.monotonic()
    result = discovery.discover(case.transcript, duration=case.duration, about=case.about)
    elapsed = time.monotonic() - started

    chosen = [c for c in result.candidates if c.shortlisted]
    score = Score(name=case.name, posted=len(case.posted), found=len(result.candidates),
                  shortlisted=len(chosen), seconds=elapsed, windows=result.windows,
                  skipped_minutes=result.skippedMinutes)
    for moment in case.posted:
        best = max((overlap(moment, c) for c in chosen), default=0.0)
        top5 = max((overlap(moment, c) for c in chosen[:5]), default=0.0)
        score.hits_total += 1 if best >= HIT else 0
        score.hits_at_5 += 1 if top5 >= HIT else 0
        if best < HIT:
            score.misses.append(moment.note or f"{moment.start:.0f}-{moment.end:.0f}s")
    score.cost = discovery.estimate(case.transcript, case.duration)["costEur"]
    return score


def table(scores: list[Score]) -> str:
    head = f"{'dienst':24s} {'gepost':>6s} {'gekozen':>7s} {'top5':>5s} {'p@5':>5s} {'recall':>6s} {'euro':>6s} {'sec':>5s}"
    lines = [head, "-" * len(head)]
    for s in scores:
        lines.append(f"{s.name[:24]:24s} {s.posted:6d} {s.shortlisted:7d} {s.hits_at_5:5d} "
                     f"{s.precision_at_5:5.2f} {s.recall:6.2f} {s.cost:6.2f} {s.seconds:5.0f}")
    if scores:
        lines.append("-" * len(head))
        posted = sum(s.posted for s in scores)
        lines.append(f"{'samen':24s} {posted:6d} {sum(s.shortlisted for s in scores):7d} "
                     f"{sum(s.hits_at_5 for s in scores):5d} "
                     f"{sum(s.precision_at_5 for s in scores) / len(scores):5.2f} "
                     f"{sum(s.hits_total for s in scores) / max(1, posted):6.2f} "
                     f"{sum(s.cost for s in scores):6.2f} {sum(s.seconds for s in scores):5.0f}")
    return "\n".join(lines)


def dry_run(cases: list[Case]) -> str:
    head = f"{'dienst':24s} {'minuten':>7s} {'preek':>6s} {'stukken':>7s} {'thuis':>6s} {'euro':>6s}"
    lines = [head, "-" * len(head)]
    total = 0.0
    for case in cases:
        guess = discovery.estimate(case.transcript, case.duration)
        minutes = (case.duration or (case.transcript.segments[-1].end if case.transcript.segments else 0)) / 60
        total += guess["costEur"]
        lines.append(f"{case.name[:24]:24s} {minutes:7.0f} {case.sermon_minutes:6.0f} "
                     f"{guess['windows']:7d} {guess['skippedMinutes']:6d} {guess['costEur']:6.2f}")
    lines += ["-" * len(head), f"{'samen':24s} {'':7s} {'':6s} {'':7s} {'':6s} {total:6.2f}"]
    return "\n".join(lines)


def compare(now: list[Score], before: dict) -> str:
    was = {row["name"]: row for row in before.get("services", [])}
    lines = [f"{'dienst':24s} {'p@5':>13s} {'recall':>13s} {'$':>13s}", "-" * 66]
    for score in now:
        old = was.get(score.name)
        if old is None:
            lines.append(f"{score.name[:24]:24s} {'nieuw':>13s}")
            continue
        lines.append(f"{score.name[:24]:24s} "
                     f"{shift(old['precisionAt5'], score.precision_at_5):>13s} "
                     f"{shift(old['recall'], score.recall):>13s} "
                     f"{shift(old['cost'], score.cost, lower_is_better=True):>13s}")
    return "\n".join(lines)


def shift(before: float, after: float, lower_is_better: bool = False) -> str:
    change = after - before
    if abs(change) < 0.005:
        return f"{after:.2f} ="
    better = change < 0 if lower_is_better else change > 0
    return f"{before:.2f}→{after:.2f} {'+' if better else '-'}"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--set", type=Path, default=DEFAULT_SET, help="folder of services (default: evaluation/)")
    parser.add_argument("--dry-run", action="store_true", help="what a run would send and cost, without sending it")
    parser.add_argument("--save", type=Path, help="write the results here, as a baseline to compare against")
    parser.add_argument("--compare", type=Path, help="compare with an earlier saved run")
    args = parser.parse_args()

    cases = load_cases(args.set)
    if not cases:
        print(f"Geen diensten gevonden in {args.set}. Zie evaluation/README.md.")
        return 1

    if args.dry_run:
        print(dry_run(cases))
        return 0

    scores = []
    for case in cases:
        print(f"  {case.name} …", flush=True)
        scores.append(run_case(case))
    print()
    print(table(scores))

    if args.compare:
        print()
        print(f"vergeleken met {args.compare.name}:")
        print(compare(scores, json.loads(args.compare.read_text(encoding="utf-8"))))

    if args.save:
        args.save.write_text(json.dumps({
            "when": time.strftime("%Y-%m-%d %H:%M"),
            "provider": discovery.LLM_PROVIDER,
            "model": discovery.LLM_MODEL or "",
            "services": [s.as_dict() for s in scores],
        }, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        print(f"\nopgeslagen als {args.save}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
