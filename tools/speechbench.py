"""Time the two speech engines against each other, on your own recording.

faster-whisper decodes on the processor. On an Apple laptop mlx-whisper decodes on the
graphics chip instead, which is a thing this machine has and the other one does not, so the
only honest comparison is the one you run yourself:

    .venv/bin/python -m tools.speechbench opnames/dienst.mp4
    .venv/bin/python -m tools.speechbench opnames/dienst.mp4 --minutes 10 --model medium

It writes out the same audio with both, prints how long each took and how much their words
differ, and leaves both transcripts next to each other so you can read them.
"""

import argparse
import difflib
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend import mac, transcription  # noqa: E402


def words_of(transcript) -> list[str]:
    return " ".join(s.text.strip() for s in transcript.segments).split()


def difference(a: list[str], b: list[str]) -> float:
    """How much two transcripts disagree, as a share of the longer one."""
    if not a and not b:
        return 0.0
    match = difflib.SequenceMatcher(None, a, b)
    same = sum(block.size for block in match.get_matching_blocks())
    return 1 - same / max(len(a), len(b))


def run(engine: str, source: Path, work: Path, seconds: float, how) -> tuple[float, object]:
    transcription.BACKEND = engine
    for leftover in ("partial.json", "audio.wav"):
        (work / leftover).unlink(missing_ok=True)
    began = time.time()
    heard = transcription.transcribe(source, work, duration=seconds, how=how)
    return time.time() - began, heard


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("recording", type=Path, help="a service or a clip, video or audio")
    parser.add_argument("--minutes", type=float, default=6.0, help="how much of it to use (default: 6)")
    parser.add_argument("--model", default=transcription.MODEL_SIZE,
                        help=f"tiny, base, small, medium, large-v3 (default: {transcription.MODEL_SIZE})")
    parser.add_argument("--beam", type=int, default=transcription.CLIP_BEAM,
                        help="how wide the processor engine searches; the Mac one has no such setting")
    parser.add_argument("--out", type=Path, default=ROOT / "speechbench",
                        help="where the two transcripts are left")
    args = parser.parse_args()

    if not args.recording.is_file():
        print(f"{args.recording} bestaat niet.")
        return 1

    seconds = args.minutes * 60
    how = transcription.Listening(args.model, args.beam, "bench")
    args.out.mkdir(parents=True, exist_ok=True)

    print(f"{args.recording.name}, de eerste {args.minutes:g} minuten, model {args.model}\n")
    if not mac.apple_silicon():
        print("Deze computer is geen Apple Silicon, dus er valt niets te vergelijken:")
        print("mlx draait alleen daarop. Draai dit op de MacBook zelf.\n")
    elif not mac.installed():
        print("mlx-whisper is niet geïnstalleerd. Installeer het eerst:")
        print("    .venv/bin/pip install -r backend/requirements-mac.txt\n")

    results = {}
    for engine in (transcription.CTRANSLATE, transcription.MLX):
        if engine == transcription.MLX and not mac.possible():
            continue
        print(f"  {engine} …", flush=True)
        try:
            took, heard = run(engine, args.recording, args.out / engine, seconds, how)
        except Exception as exc:  # noqa: BLE001  one engine failing is a result too
            print(f"    liep vast: {exc}\n")
            continue
        results[engine] = (took, heard)
        (args.out / f"{engine}.txt").write_text(
            "\n".join(f"{s.start:8.2f}  {s.text}" for s in heard.segments), encoding="utf-8")
        print(f"    {took:6.1f}s  {seconds / took:5.1f}x realtime  {len(heard.segments)} segmenten")

    if len(results) == 2:
        slow, quick = results[transcription.CTRANSLATE][0], results[transcription.MLX][0]
        apart = difference(words_of(results[transcription.CTRANSLATE][1]),
                           words_of(results[transcription.MLX][1]))
        print(f"\nDe grafische chip is {slow / quick:.2f}x zo snel als de processor.")
        print(f"Van de woorden is {apart:.1%} anders. Lees ze naast elkaar in {args.out}/.")
        print(f"\nOver een dienst van anderhalf uur: {slow * 5400 / seconds / 60:.0f} minuten "
              f"tegen {quick * 5400 / seconds / 60:.0f}.")
    elif results:
        engine, (took, _heard) = next(iter(results.items()))
        print(f"\nAlleen {engine} heeft gedraaid, dus er valt niets te vergelijken.")
        print(f"Over een dienst van anderhalf uur: {took * 5400 / seconds / 60:.0f} minuten.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
