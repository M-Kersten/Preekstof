# Evaluation set

Prompt changes feel better and get worse all the time. This is the fixed set they are
measured on, so "better" is a number rather than an impression.

## Adding a service

Out of a service the app has already done, which is the short way:

```bash
.venv/bin/python -m tools.adopt service-a1b2c3d4 --as 2026-03-08-kruispunt
```

That copies the transcript across and takes the moments from the clips that were actually
made, which is the honest answer to "what did this church post". A service with no clips is
refused rather than adopted with an empty answer key. Fill in `church` and `permission`
afterwards; **ask first**, and see `TOESTEMMING.md` for the mail to send.

By hand, when the service is not in this installation:

One folder per service, named however you like:

```text
evaluation/2026-03-08-rust/
  service.json      what this is, and which moments were actually posted
  transcript.json   {"language": "nl", "segments": [{"start", "end", "text"}, ...]}
```

`service.json`:

```json
{
  "title": "Rust in een druk leven",
  "duration": 4500,
  "sermonTitle": "Rust in een druk leven",
  "series": "Onderweg",
  "posted": [
    {"start": 1820, "end": 1868, "note": "rust is geen zwakte"},
    {"start": 2410, "end": 2455, "note": "je hoeft dit niet alleen te dragen"}
  ]
}
```

`posted` is the ground truth: the moments the church actually put out. Rough boundaries are
fine, a proposal counts as a hit when it overlaps half of one.

The transcript is the one the app produced, so the run measures the analysis and not the
transcription. Export it from a service folder (`services/<id>/transcript.json`).

Real services are not in git: they are the church's own recordings and the transcripts hold
what people said. Keep them here locally, or in a private folder pointed at with
`--set`. `voorbeeld-dienst/` is a made-up service so the tool runs out of the box.

## Running it

```bash
.venv/bin/python -m tools.evaluate                # every service in evaluation/
.venv/bin/python -m tools.evaluate --dry-run      # what it would cost, without spending it
.venv/bin/python -m tools.evaluate --set ~/diensten --save baseline.json
.venv/bin/python -m tools.evaluate --compare baseline.json
```

Write down the baseline before changing a prompt, and compare after.

## What the pilot itself measured

The app writes down what each run took while it works, in `logs/runs.jsonl`. No church name,
no title, no word of anybody's transcript, so a pilot church can mail that file without
reading it first. It also rides along in the zip that **Melding opslaan** makes.

```bash
.venv/bin/python -m tools.pilot
.venv/bin/python -m tools.pilot --file ~/meldingen/kruispunt/runs.jsonl --json
```

The one to watch is *uit de top 5*: how many of the clips a church actually made were among
the five the app put first. That is the question the whole pilot is for, and it is the one
number no impression will ever give you.
