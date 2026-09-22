# Preekstof

Turns a short Dutch church-service clip into a finished vertical video (1080×1920, H.264 + AAC, 30 fps) for Instagram Reels and YouTube Shorts. Everything runs locally.

Not open source. See [LICENSE](LICENSE) for what a pilot church and Donkey Mobile may do with
it, and [NOTICE](NOTICE) for whose work it is built on. What changes per version is in
[CHANGELOG.md](CHANGELOG.md); the version you are running sits at the bottom of the readiness
panel in the app bar.

```text
Upload video → Transcribe Dutch speech → Edit subtitles → Choose subtitle style
→ Preview 9:16 crop → Add church outro → Render final MP4
```

Part 1 uses a **static** centre crop. Person tracking and animated camera movement are reserved for Part 2 (see "Part 2 hooks" below).

There are two entry points on the page:

- **Full service**: bring in a complete recording (60–120 minutes) by pasting the link the church already publishes it at or by uploading the file, let the AI suggest clip-worthy moments, review and adjust them, and send the ones you pick into the clip editor. See "Full service clip discovery" below.
- **Clip**: the single-clip editor described above.

## Quick start (no technical knowledge needed)

1. Download the newest release: **Releases** on GitHub → `preekstof-<versie>.zip`, and unzip it
   wherever you like. That zip holds everything the app needs to run, so no git and no Node.
   (The green **Code** button works too, and so does a clone.)
2. Start it:
   - **Windows**: double-click `start.bat`. Without Python on the machine it installs one
     and carries on in the same window. The `-windows` zip carries its own Python and needs
     nothing at all (not yet tested on a real machine without Python; the plain zip is the
     safe one until it has been).
   - **macOS**: double-click `start.command`. If macOS says the file cannot be opened, right-click it, choose **Open**, and confirm once.
3. The first start takes a few minutes: it installs Python packages and downloads FFmpeg into `tools/`. After an update, the next start installs any new packages by itself. Python itself is installed automatically on Windows (through winget) and through Homebrew on macOS when available; otherwise the window tells you where to get it.
4. The browser opens at http://localhost:8000. Close the black window to stop the app.

The first time the app opens it walks through what it needs: a Claude API key, the name of
the church, and the church's number on kerkdienstgemist.nl. The key is tried against the API
before it is written down, so a mis-pasted one says so on the spot rather than twenty minutes
into the first run, and it takes effect without a restart. Everything asked there stays
editable under **Merk instellen**, and **Instellen opnieuw** walks through it again.

Settings live in `config.env` next to `start.bat` (created on first start). The welcome writes
the key there; `LLM_PROVIDER=ollama` keeps everything on the machine for a church that will not
send transcript text anywhere. What goes where, in one page a church council can read, is
`PRIVACY.md`; the short version sits in the app next to the cost estimate. The speech model (about 460 MB) is downloaded on the first
transcription.

The built web interface is committed in `frontend/dist`, so Node.js is not needed to run the app. Developers who change the frontend run `npm run build` in `frontend/` and commit the result.

On every start the app asks GitHub once whether there is a newer release, and says so in the
black window with one line about what changed and where to get it. It never installs anything
by itself: a church rebuilding unattended at ten to ten on a Sunday morning is a worse outcome
than a church running last month's version. No internet, or GitHub not answering, means the
app starts without mentioning updates at all.

Making a release, for whoever maintains this: bump `backend/version.py`, write what changed in
`CHANGELOG.md`, commit, then `git tag v0.9.1 && git push origin v0.9.1`. The tag builds the zip
and opens a draft release. It refuses the tag if the number does not match `version.py`, or if
the committed `frontend/dist` is not what the code in that commit builds.

## Requirements

- Python 3.11+
- Node.js 20.19+ or 22.12+ (what Vite 8 asks for; version 22 is the safe choice). Only the build
  needs it: `frontend/dist` is committed, so a machine without Node still runs the app.
- FFmpeg with libass, libx264 and AAC (`ffmpeg` and `ffprobe` on `PATH`)
  - macOS: `brew install ffmpeg`
  - Ubuntu/Debian: `sudo apt install ffmpeg`
  - Windows: a full build from https://www.gyan.dev/ffmpeg/builds/ (added to `PATH`)

The first transcription downloads the faster-whisper model (default `small`, roughly 460 MB) into the Hugging Face cache, and says so while it happens: *Spraakmodel wordt opgehaald · 147 van 484 MB · dit gebeurt één keer*. After that no network access is needed.

### How long a service takes, measured

Transcription is the long pole, and the most common way a pilot fails is a computer that is
too slow and an expectation nobody set. So the readiness panel states a number for the machine
it is running on, before the first upload. The table it falls back to holds only machines that
were really timed, with the `small` model on a real Dutch service:

| Machine | Engine | Seconds of work per second of audio | A service of 90 minutes |
| --- | --- | ---: | ---: |
| 4-core x86_64 (a container, 493 s of preaching) | faster-whisper, processor | 0.20 | 18 minutes |
| Apple Silicon, processor | faster-whisper | not measured | — |
| Apple Silicon, graphics chip | mlx-whisper | not measured | — |
| NVIDIA card | faster-whisper, CUDA | not measured | — |

The rows that say *not measured* say that on purpose. A guessed row is worse than no row,
because it is the number a church plans its Sunday around. Filling one in: run a real service,
open `templates/speed.json`, and add the number to `MEASURED` in `backend/speed.py` with the
processor as `platform.processor()` reports it.

Until a machine has written out one service, the panel quotes the table as a range and says it
is an indication. From the second service onwards it quotes the median of what this computer
has really done, which cannot be argued with. Over two hours for one service is not green:
that is not slow, it is unusable, and the panel says so.

Dutch church words are fed to the speech model through `templates/woordenlijst.json`, shared by
every church; `templates/woordenlijst.example.json` is the shipped copy, with the reasoning at the
top of the file.

**The prompt has a hard limit and it is smaller than it looks.** Whisper reads the *last* 223
tokens of an `initial_prompt` and drops the rest without a word
(`previous_tokens[-(max_length // 2 - 1):]` in faster-whisper's `get_prompt`). That is about 510
characters of Dutch church vocabulary. A longer list is not a better one: past the limit it is the
head that disappears, so a 1300-token list of everything leaves the model with whatever happened to
land at the end.

**There is a second budget of the same size.** The same `get_prompt` takes `hotwords` and gives it
its own 223 tokens next to the prompt rather than a share of it, so the two together carry roughly
twice what either can. It is cut off at the *other* end (`hotwords_tokens[:max_length // 2 - 1]`),
which is why the two lists in `templates/woordenlijst.json` run in opposite orders: `words` is
droppable-first because the prompt keeps its tail, `hotwords` is precious-first because this keeps
its head.

Whatever the prompt has no room for goes there by itself, and with the shipped list that is thirty
of the seventy words, every Bible book among them. Measured with the `small` model at the settings
the scan really uses (`WHISPER_SCAN_BEAM=1`), on two spoken sentences, counting the church words
that came back:

| | zin 1 (8 woorden) | zin 2 (12 woorden) |
| --- | ---: | ---: |
| no prompt at all | 0 | 7 |
| `initial_prompt` only (up to 0.9.0) | 0 | 7 |
| prompt plus `hotwords` | 4 | 11 |

Two sentences of synthetic speech, so the size of the gain is not measured, only its direction.
What is certain without measuring anything is that thirty words which reached the model nowhere
at all now reach it. Worth reading twice: on sentence 1 the prompt on its own scored the same as
no prompt, which is what a list looks like once everything in it has fallen off the front.

On a Mac with mlx-whisper there is no second budget: mlx takes `initial_prompt` and nothing else,
so that path keeps only what fits in the prompt.

So the file holds `words` in groups, ordered from droppable to precious inside each group and
between them, and `initial_prompt()` trims from the front until what is left fits. Words the model
already gets right earn nothing and are left out; what is in there is what it gets wrong. A church's
own names (preachers, series, locations, set under **Merk en afsluiter**) go last and are never
trimmed, because a preacher's name is the one thing the model cannot guess.

Whatever does not fit goes in `corrections` instead, applied to the finished text, where nothing
limits the length. A correction only goes in when the misheard form is not itself a Dutch word, or
when it is purely a matter of capitals: "heerder" → "herder" is safe, "heller" → "herder" is not,
because *heller* is a word.

Measured on ninety seconds of preaching about a shepherd, counting how often "herder" came out
right:

| prompt | right | wrong |
| --- | --- | --- |
| no prompt at all | 2 | 3 |
| the old list | 0 | 5 |
| the list now | 2 | 3, all of them "heerder" |
| the list now, after `corrections` | 5 | 0 |

The old list was worse than no prompt, because it spent the budget on words the model already knew
and never mentioned a shepherd.

On top of it, each brand keeps **its own words**, edited under **Merk en afsluiter**: who preaches here, the series that are running, the hymnals they sing from, the locations. Those go into the prompt in front of the audio, which is where names are won or lost.

And the app learns. When you correct a subtitle line, it compares your version with the machine's and works out which words actually changed. A word that sounds like what it replaced ("brie" for "Bree") or that only gained a capital in the middle of a line ("heilige geest" for "Heilige Geest") is offered back: **Zal ik dit onthouden?** Say yes and it goes in the church's list, so next Sunday it comes out right. A rewritten sentence, an added or dropped word, and sentence case at the start of a line are all left alone, because none of them teaches the model to hear.

Filling in **waar gaat het over** and **serie** on a service before transcribing helps twice: the speech model gets the words, and both analysis passes know what the preaching is about.

## Developer setup

```bash
# backend
python -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r backend/requirements.txt

# frontend
cd frontend && npm install && cd ..
```

## Run

Development, two processes:

```bash
uvicorn backend.main:app --reload --port 8000     # from the repository root
cd frontend && npm run dev                        # http://localhost:5173
```

Single process, after building the frontend:

```bash
cd frontend && npm run build && cd ..
uvicorn backend.main:app --port 8000              # http://localhost:8000
```

Environment variables for transcription:

| Variable | Default | Notes |
| --- | --- | --- |
| `WHISPER_MODEL` | `small` | `tiny`, `base`, `small`, `medium`, `large-v3`. `small` is a good CPU trade-off. |
| `WHISPER_MODEL_ACCURATE` | `medium` | Used for the clips of a service with **Nauwkeuriger uitschrijven** ticked. |
| `WHISPER_SCAN_BEAM` | `1` | Decoder beam for the scan of a whole service. Put it back to `5` to listen as carefully as the clips do. |
| `WHISPER_CLIP_BEAM` | `5` | Decoder beam for the clips people actually read. |
| `WHISPER_BACKEND` | `auto` | `mlx` on an Apple Silicon Mac that has it installed, `faster-whisper` everywhere else. Name one to settle it yourself. See [On a Mac](#on-a-mac-the-graphics-chip-instead-of-the-processor). |
| `WHISPER_DEVICE` | `cpu` | `cuda` for an NVIDIA card, or `auto` to take the card when it works and the processor when it does not. Not used by the `mlx` backend. See [When the graphics card will not cooperate](#when-the-graphics-card-will-not-cooperate). |
| `WHISPER_COMPUTE_TYPE` | `int8` on CPU, `float16` on GPU | |
| `WHISPER_BATCH_SIZE` | twice the core count, at most 8 | How many 30-second windows are decoded together. |
| `HF_TOKEN` | none | Optional [Hugging Face token](https://huggingface.co/settings/tokens). The speech model is public and downloads without one; a token only lifts the rate limit and makes the first download quicker. Without one their client prints "you are sending unauthenticated requests" on every run, which the app keeps out of the window because nothing is wrong. |

Transcription runs through faster-whisper's batched pipeline: windows go through the encoder
together instead of one after another. Measured on four cores with the `small` model over eight
minutes of Dutch speech, with identical output either way:

| batch | wall clock | speed |
| --- | --- | --- |
| one at a time | 139 s | 3.6× realtime |
| 2 | 72 s | 6.8× |
| 4 | 60 s | 8.3× |
| 8 | 58 s | 8.6× |
| 16 | 66 s | 7.5× (the cores are oversubscribed) |

That puts a 90-minute service at roughly ten minutes instead of twenty-five. The interface says
which phase it is in (pulling the audio out, loading the model, writing the text out) and, once it
has measured the speed of the current phase, how long is left. Batched decoding hands back several
minutes of text at a time, so the bar is carried forward at the measured rate between readings
rather than standing still and then jumping.

### Two passes: scanning a service, writing out a clip

Reading a whole service to find what is worth posting and writing out the words a viewer will read
are two different jobs, and only the second one is read by anybody. Three or four minutes of an
hour and a half ever become clips, so listening carefully to the other eighty-six is a wait nobody
is paid back for.

So the service is **scanned** once with the decoder running greedily (`beam_size=1`), and every
clip the user picks is **written out** again over its own half-minute at the careful setting, in
the step that cuts the clips, where a bar is already running. Measured on ninety seconds of Dutch
preaching with the church word list, `small` on four cores:

| | wall clock | words different |
| --- | --- | --- |
| careful (`beam_size=5`) | 24.1 s | — |
| scan (`beam_size=1`) | 14.0 s | 6% |
| one clip of 35 s, written out | 10.5 s | |

The waiting before the suggestions appear drops by **1.7×**; a clip costs about ten seconds more in
a step that was already running. Of those 6% different words, nearly all are a full stop that
became a comma. `base` and `tiny` were tried for the scan as well and dropped: at 35% and 48%
different they mangle names ("Wat die Jesus luikbaar wel ziet"), and the LLM reads this text to
decide what the preaching is about.

The clips come out better than before, not worse, because **Nauwkeuriger uitschrijven** now points
`medium` at the minutes that become clips rather than at the whole service. It used to cost several
times the whole transcription; it now costs seconds.

What this does to the *suggestions* has not been measured. `tools/evaluate.py` scores them against
services a church has actually posted from, and the only service in `evaluation/` is invented, with
a transcript that never went through a speech model. If the moments get worse, `WHISPER_SCAN_BEAM=5`
in `config.env` puts the scan back exactly where it was.

### On a Mac: the graphics chip instead of the processor

faster-whisper decodes through CTranslate2, which has a CUDA backend and no Metal one. On an
Apple laptop that means the whole transcription runs on the processor while the graphics chip sits
there doing nothing. MLX is Apple's own array library, and `mlx-whisper` runs the same Whisper
weights on that chip.

It is not part of the normal install, because `mlx` only exists for Apple Silicon and pulls in a
couple of gigabytes nobody else can use. On a MacBook:

```bash
.venv/bin/pip install -r backend/requirements-mac.txt
```

After that the app picks it up by itself; `WHISPER_BACKEND` in `config.env` overrules that in
either direction, and the readiness check in the app bar says which chip is doing the work. The
same `WHISPER_MODEL` names are used, resolved to the converted weights (`small` →
`mlx-community/whisper-small-mlx`), so a church that set `medium` gets the medium one here too.

MLX will not hand back a sentence at a time: it takes the audio, thinks, and answers when it is
finished. Over an hour and a half that would mean a bar that does not move, a **Stoppen** button
that does nothing and a closed laptop costing the lot, so `backend/mac.py` cuts the audio into
five-minute pieces and feeds them one at a time. Each cut goes looking for the quietest moment
within twenty seconds of where it wanted to land, so it does not fall in the middle of a word.
Progress, stopping and resuming then work exactly as they do on the other engine.

**How much quicker it is has not been measured here**, and no number is quoted for it: this
repository is developed on Linux, where `mlx` cannot even be installed. Measure it on your own
machine, on your own recording:

```bash
.venv/bin/python -m tools.speechbench opnames/dienst.mp4 --minutes 10
```

That runs both engines over the same audio, prints what each took and how much their words differ,
and leaves both transcripts side by side to read.

### When the graphics card will not cooperate

On Windows with an NVIDIA card, `WHISPER_DEVICE=cuda` can come back with

```text
Library cublas64_12.dll is not found or cannot be loaded
```

The card was found; cuBLAS was not. CTranslate2 links against the CUDA libraries without shipping
them, and pip installs them under `nvidia/` in a folder Windows does not search.

Two things now stop that being your problem. `start.bat` checks it at every start: when `config.env`
asks for the card (`WHISPER_DEVICE=cuda` or `auto`) and `nvidia-smi` reports one, the launcher
fetches `nvidia-cublas-cu12` and `nvidia-cudnn-cu12` if they are missing. That is about a gigabyte,
once. And `backend/gpu.py` adds those folders to the DLL search path before the model is built,
because pip alone leaves them somewhere Windows does not look.

On the default `WHISPER_DEVICE=cpu` none of that runs and nothing is downloaded, so a church on the
processor never waits for a gigabyte it has no use for. Ask for a card that is not there and the
launcher says so and carries on.

When it still fails, the processor takes over and the service says why, instead of the run ending
in a traceback. Transcription is then slower, and it happens. To install it by hand:

```bash
.venv\Scripts\python -m pip install nvidia-cublas-cu12 nvidia-cudnn-cu12
```

`WHISPER_DEVICE=auto` tries the card and drops to the processor by itself, which is the setting for
a machine you are not sure about. `WHISPER_DEVICE=cpu` never tries, and never mentions it.

## Using the app

1. Drop a clip on the page. The original is stored under `projects/<id>/` and its metadata (size, duration, frame rate, audio) is read with ffprobe. The 9:16 preview appears right away.
2. Click **Transcribe**. Audio is extracted with FFmpeg and transcribed with faster-whisper, language forced to `nl`. Words are grouped into short caption-sized segments. This runs as a background job with a progress bar, so you can keep working and even reload the page while it runs.
3. Correct the subtitles. Each segment has editable start/end times (`mm:ss.s`) and text, plus **Split**, **Merge ↓** and delete. Click ▶ on a segment to jump the preview there. Edits are saved automatically.
4. Set the framing. The **Beeldkader** panel shows the whole source with the 9:16 output frame drawn on it, and two ways to place it. **Volg de spreker** lets the frame walk along the path found for this clip (see [Following the speaker](#following-the-speaker)); **Zelf kaderen** hands it back to you, so drag the frame (or drag the preview itself) to choose which part of the picture ends up in the reel, and use the zoom slider to crop in further or, at the low end, to fit the whole picture with black bars. Landscape clips start centred and filling the frame; portrait clips start with the whole picture visible. **Herstel** returns to that default.
5. Pick a style: font, weight, size (24–200), text colour, outline size and colour, optional dark translucent background, and how a line appears. Subtitles always sit bottom-centre, above the safe margin that Reels and Shorts overlay with UI. A bigger font spreads over more lines (up to three) before anything is scaled down, so turning the size up really does make the text bigger on screen.
6. Put the church logo in a corner if you want one. The **Logo in beeld** panel picks the corner, the width as a share of the frame, the opacity and the margin, and draws it straight into the preview. Files live in `templates/logos/` and are shared with the end screen.
7. Click **Render video**. Rendering runs as a background job with a progress bar; when it finishes a download link for `final.mp4` appears.

The preview is an HTML `<video>` with `object-fit` mimicking the static crop and an HTML overlay for subtitles; it uses the same fonts and layout rules as the renderer. When the clip ends, the outro plays in the preview as well. Nothing is rendered until you click **Render video**.

### Subtitle animation

Each line can appear in one of four ways, with the speed (60–600 ms) set alongside it. The preview replays the animation on every line, using CSS keyframes that mirror the ASS tags in the render:

| Setting | What it does | ASS |
| --- | --- | --- |
| `none` | the line is simply there | no tags |
| `fade` | fades in and out | `\fad` |
| `pop` | starts at 72% and springs to full size | `\fscx`/`\fscy` with `\t` |
| `slide` | rises 40 px into place | `\move` |

### Captions that read like captions

Most social viewing is muted, so the captions are the clip. Three things make the difference
between something that looks made and something that looks generated.

**Where the line breaks.** Breaking at sixty characters puts the break wherever the counting
lands, which strands "van" or "de" at the end of a line. `transcription.chunk_words` now works
out how far a caption *could* run (on length, on time, and on a silence or a full stop, which
end one whatever the length says) and then scores every break inside that: a finished sentence
is worth most, a comma less, a real silence as much as a sentence, and a line is docked for
ending on one of the Dutch words that lean on what comes next. A good break halfway beats a bad
one at the limit, because the fullness of the line is worth only a couple of points.

Measured on ninety seconds of real preaching, against the old rule: lines ending on punctuation
went from 77% to 85%, and lines left hanging on a leaning word from three to one.

**Word-by-word highlighting.** `Style.highlight` lights each word as it is said, in
`Style.highlightColor`. Whisper's timings are kept on the segment for it (`Segment.words`) and
read back through `subtitles.word_times`, which falls back to spreading the words over the
caption by length when an edit has left the timings not matching the text. In the ASS file every
word carries its own colour and two `\t` switches, on when it is said and off after, rather than
karaoke tags (which colour everything said so far and leave it coloured) or a line per word
(which would restart the entrance animation on every word). `tests/test_render.py` renders a clip
and reads the pixels back to prove the highlight really walks along the line.

**What is wrong with a line, under the line.** The editor marks a caption running faster than
2.5 words a second, standing longer than 7 seconds, or holding a word this church has already
written down as a mishearing, and says which. `frontend/src/captionCheck.ts` holds the rules;
`GET /words` gives the browser the same corrections the transcription applies.

## Bringing the recording in

One service is open at a time. **Andere dienst kiezen** puts it away and brings the chooser
back; it is not a delete, so the recording, its text and its clips stay where they are and
the service reappears under **Eerder mee gewerkt**, which is `GET /services`. Throwing one
away is still **Ruimte vrijmaken**, which knows which recordings are held by clips that have
not been made yet.

Two ways in, and the link is the default one. Most churches already publish the service, so
pasting that address saves finding the file on disk and waiting out a two-gigabyte copy.

The downloading is `yt-dlp`'s job (`backend/fetch.py`): YouTube, Vimeo, Facebook, a direct
link to an mp4 or an m3u8 playlist, and for a page it does not know it still reads that page
for an embedded player or an `og:video` tag. It runs as a job like the others, with progress
and a stop button, and the recording keeps the title the site gave it.

Some platforms hand their video only to their own player. **Kerkdienstgemist** is one, and
`backend/kerkdienstgemist.py` asks its player's question instead: the page address carries a
station id and a recording id, and
`GET https://api.<domain>/api/v2/stations/{station}/recordings/{recording}?include=media`
answers with `download_url` — the signed S3 link the download button in the player points
at, plus the recording's own title, its duration and where the platform thinks the sermon
starts. The request carries the anonymous token the site ships in its own script bundle
(`config.APP.API_CREDENTIALS`); it grants what any visitor already has and is nobody's
account. This leans on a shape nobody promised to keep: when it changes, `resolve` returns
None, the link falls through to the ordinary route, and the reader gets the note in
`SITE_ADVICE` telling them to press the download button themselves. `tests/fixtures/
kerkdienstgemist-recording.json` is a real answer, with the signatures scrubbed, so the
tests parse the shape that was actually there.

The same API answers `GET /api/v2/stations/{station}` and `.../recordings?include=media`,
so a church that fills in its **station number** once (brand → Gegevens) gets its own recent
services listed on the service page, each one fetchable with a button. The number is the one
in the address of the church's page: `kerkdienstgemist.nl/stations/1341` → `1341`. Without
it, that block explains where to find it and links to the site. Private and locked
recordings are left out of the list, since they cannot be fetched anyway.

Times are read from the stamp as written (`2026-08-30T10:00:00+02:00` → "zondag 30 augustus
· 10:00") rather than through `Date`, so a service at ten o'clock says ten o'clock whatever
timezone the computer looking at it is set to; `frontend/test/dates.ts` pins that down.

Kerkomroep has no such resolver, so it still gets a note pointing at its own download.

## Full service clip discovery

```text
Link or upload → Transcribing → Analyzing service → Suggestions ready → Review & select → Process selected clips → Clip editor
```

1. Open the **Full service** tab and drop the complete recording. The scan starts automatically (faster-whisper, forced to `nl`, decoding greedily; see [Two passes](#two-passes-scanning-a-service-writing-out-a-clip)) and shows progress. It is deliberately rough: good enough to find the moments, and replaced per clip in step 7. The black window may print warnings from the speech library while this runs; the progress bar in the browser is what counts.
2. The transcript is labelled into the parts of a service before anything is sent: welcome, songs, reading, prayer, sermon, notices, blessing. No model is involved; it is the words a Dutch service uses, plus where in the hour a part falls and how much silence it leaves. See **Reading the shape of a service** below.
3. The sentences that belong to the singing, the notices and the blessing are dropped, and what is left is packed into as few passages as it fits in. `LLM_PASSAGE_MINUTES` is 40, so an ordinary sermon is a single call: the model reads the whole thing, is asked for the three to six moments the service is worth posting, and answers as structured JSON (start, end, title, summary, reason, confidence). See [One call, not sixteen](#one-call-not-sixteen).
4. Candidate boundaries are snapped to sentence boundaries and proposals covering the same moment are merged (the extra boundaries stay available as alternatives).
5. A sermon too long for one passage gets a **second round**, which reads every surviving proposal at once, with the shape of the service and an excerpt of what is actually said, and picks the ones worth posting. Confidence from two separate reads is not comparable on its own: the best moment of a dull three minutes scores the same as the best moment of the service. Every proposal comes back with a one-line verdict, including the ones passed over. A sermon that fitted in one passage skips this round entirely, because the model already had all of it in front of it.
6. **De dienst** holds both ways of working, under one timeline and one player. **Fragmenten** lists the moments best first, hand-cut ones above the found ones, with the shape of the service drawn behind them. The ones that were found but passed over sit behind **Ook gevonden, niet gekozen** with the reason they lost. **Beluister** plays just that range; **Tekst en tijden** opens the full excerpt and the boundary editor with direct `mm:ss.s` input and -5 / -1 / +1 / +5 second nudges. **Hele tekst** is the whole service to read through, search and cut from yourself; see [Reading the service yourself](#reading-the-service-yourself). Selections and edits are saved automatically.
7. **Process selected clips** creates a normal clip project per selected range. Each one is then heard again over its own seconds, at the careful setting, so the subtitles a viewer reads are not the scan's; and the speaker is found in it, so it opens already framed. Both steps report into the bar at the bottom of the screen, which also lists the finished clips. **Open in editor** switches to the Clip tab for subtitles, styling, framing and rendering. Nothing about rendering lives in the discovery layer.

   Nothing is cut at this point. A clip records which recording it came from and which seconds it covers, and the renderer seeks into the original, so a finished clip is one encode away from the camera instead of two and processing eight moments takes a moment rather than several minutes. `clips.source_of()` answers where a clip's footage is; `clips.materialise()` gives a clip its own copy, which only happens when the recording is about to be removed.

### Reading the shape of a service

`backend/structure.py` labels every sentence with the part of the service it belongs to, using
three kinds of evidence and no model at all:

- **The words.** Weighted phrases per part: "de collecte" and "koffie na de dienst" are notices,
  "laten we bidden" and "hemelse Vader" are prayer, a Bible book with a chapter is a reading,
  "we zingen" and a hymn number are singing.
- **The silence.** A stretch with nothing transcribed is nearly always music. How long a silence
  has to be depends on the transcript: a thinly written one has long gaps everywhere, so the
  threshold is three times its own median gap, never below 25 seconds.
- **The hour.** Where a sentence falls is a tie-breaker only, and the longest unbroken stretch of
  talking is taken as the sermon whatever the words said, so a preacher who opens with a reading
  does not lose those minutes.

Single sentences do not make a part: a label spreads to its quiet neighbours and runs shorter than
twenty seconds are folded into what surrounds them. The filter then runs per sentence: a sentence
is dropped only when it sits in a part a clip never comes from (welcome, songs, notices, blessing),
so a moment that starts during the singing and runs into the sermon is still seen. Prayer and
readings are kept: churches do post those.

Measured on the service in `tests/service_text.py`, 52 of 52 sentences are labelled correctly and
19 of its 59 minutes never leave the house.

### Reading the service yourself

The text is on screen the moment it is written out, before the search has started and while
it runs. Someone who has to have a clip out by lunchtime should not be sitting in front of a
progress bar for a minute, and they usually already half know the moment they are after.

**Hele tekst** is the service sentence by sentence with its timecodes. Typing in the search
box marks every hit and steps through them with ‹ ›, accents and capitals folded away, so
"mattheus" finds "Mattheüs". The parts of the service are buttons across the top, each with
the minute it starts at, because a morning has three blocks of singing in it and the label
alone does not say which is which. Clicking a sentence plays from there; while the recording
plays the sentence being spoken is marked and the list scrolls itself along, until you scroll
away yourself.

Shift-clicking a second sentence takes everything in between. What that covers, how long it
runs and whether that is too short or too long to work as a reel is shown at the bottom, with
the opening words filled in as the name. **Fragment maken** puts it in the same list the
search writes to, so there is one list to choose from and one button at the bottom.

Hand-cut moments carry `source: "self"` and the search may never touch them:

- A run that comes back reads the service off disk before writing, so a fragment cut while
  it was thinking is still there afterwards.
- Saving the list is allowed while the search runs, and the server merges rather than
  overwrites: a moment the browser has not seen yet is added, never dropped. The browser only
  ever removes its own, so nothing that was meant to go comes back.
- They sort above the found ones. A ranking they were never part of should not push them down
  the page.
- **Opnieuw zoeken** replaces what the search found and leaves them alone.

Only **Gekozen fragmenten verwerken** actually locks the list, because it walks the fragments
as it goes. While the search runs, the dock says so and the button waits.

### One call, not sixteen

Analysis used to cut the preaching into overlapping four-minute windows. A ninety-minute service
became about sixteen calls, run three at a time, and then a second round to compare their answers:
three waits in a row before anything appeared. Someone who wanted one clip in a hurry could scrub
through the sermon themselves in the time that took.

A sermon is around twenty thousand tokens, which fits in one call with room to spare, so that is
what gets sent. What changed:

- **Whole passages.** `LLM_PASSAGE_MINUTES` (40) decides how much goes into one call. Everything
  under that is a single call; a marathon splits and the parts run in parallel.
- **No duplicated text.** Four-minute windows overlapped by a minute and carried two minutes of
  run-up each, so a quarter of the transcript was sent twice and the standing instructions went out
  sixteen times. One passage sends each sentence once.
- **The choosing happens in the same call.** The model that has read the whole sermon is asked for
  the shortlist there and then. The second round only runs for a sermon that had to be split.
- **`LLM_EFFORT` now defaults to `medium`.** With one call left, how long the model thinks is most
  of the wait.

What this does to the *suggestions* has not been measured against a real service; `evaluation/`
still holds one invented one. `LLM_PASSAGE_MINUTES=4` in `config.env` puts the old windowing back
if the moments get worse, at the old price in minutes.

### LLM configuration

| Variable | Default | Notes |
| --- | --- | --- |
| `LLM_PROVIDER` | `anthropic` | `anthropic` uses the Claude API (set `ANTHROPIC_API_KEY`); `ollama` uses a local Ollama server, so the whole pipeline stays on your machine. |
| `LLM_MODEL` | `claude-opus-5` / `llama3.1` | Model per provider. |
| `LLM_EFFORT` | `medium` | Claude effort level (`low` … `max`). With a single call this is most of the wait. |
| `LLM_PASSAGE_MINUTES` | `40` | How much of the service goes into one call. Lower splits the sermon into more, smaller calls. |
| `LLM_CONCURRENCY` | `3` | Passages analysed in parallel. Only matters for a sermon long enough to split. |
| `LLM_MAX_TOKENS` | `16000` | Ceiling per answer, thinking included. An answer itself is a few hundred. |
| `LLM_TIMEOUT` | `300` | Seconds to wait for one call. A whole sermon takes longer to read than four minutes did. |
| `OLLAMA_URL` | `http://localhost:11434` | |

Only transcript text is sent to the model, never video or audio. Before you press **Beste momenten zoeken**, the interface says whether the service goes out in one piece or several, roughly how many tokens that is and what it costs at list price, converted from Anthropic's dollar list at `EUR_PER_USD` from `config.env`. For the hour-long service in `tests/service_text.py` that is one call, about 2,700 tokens and € 0,03 with Claude Opus 5. With `LLM_PROVIDER=ollama` it says the run is free and stays on the machine.

### What a pilot measured

While the app works it writes one line per run into `logs/runs.jsonl`: how long writing out
took, what a search cost and how long it took, how many moments were offered and how many
became clips, and how many of those were in the five the app put first. No church name, no
title, no word of anybody's transcript, so that file can be mailed without reading it first.

```bash
.venv/bin/python -m tools.pilot            # the four numbers, in words
.venv/bin/python -m tools.pilot --json     # the same, for a spreadsheet
```

The one that matters is how many made clips came out of the top five. A church that makes four
clips and finds three of them at the top is being served by the ranking; one that finds them at
number nine is not, and no impression would have told you which.

### Measuring whether the suggestions are any good

Prompt changes feel like improvements. `evaluation/` is the fixed set that says whether they
are: one folder per service, holding the transcript the app produced and the moments the church
actually posted. `evaluation/voorbeeld-dienst/` is a made-up service so the tool runs out of the
box; real ones stay out of git, because they are the church's recordings and hold what people
said. See `evaluation/README.md` for the format.

```bash
.venv/bin/python -m tools.evaluate --dry-run          # what a run would send and cost
.venv/bin/python -m tools.evaluate --save baseline.json
.venv/bin/python -m tools.evaluate --compare baseline.json
```

```text
dienst                   gepost gekozen  top5   p@5 recall      $   sec
-----------------------------------------------------------------------
voorbeeld-dienst              3       6     3  0.60   1.00   0.25     0
```

**p@5** is how many of the top five choices are moments the church posted, **recall** how many of
the posted moments were found at all, and the run names the ones it missed so you can go and look
at why. `--compare` marks every number as better or worse than the baseline, cost included, so a
change that buys a point of precision for triple the money is visible as that. Write down the
baseline before touching a prompt.

### Discovery data

Services live in `services/<id>/` (ignored by git) next to the clip projects:

```text
services/service-954de789/
  service.json      title, status, candidates[], clips[]
  source.mp4        the full recording, never modified
  transcript.json   {"segments": [{"start", "end", "text"}, ...]}
  work/audio.wav
```

A **candidate** means "the AI thinks this range could work"; a **processed clip** means "the user approved it and a clip project was created". Both are kept on the service. Clip projects created this way carry `title` and `origin` (service id, candidate id, start, end) so later parts can trace a reel back to the recording.

The interface between discovery and production is one function, `create_clip(source, start, end)` in `backend/clips.py`, which builds a standard project for the existing pipeline. The candidate model has room for future fields (category, hook, keywords, thumbnail time) without changing the workflow.

## Disk space

A 90-minute service is a few GB in, so a church doing this every week fills a laptop inside a
couple of months. **Opruimen** in the app bar shows what is taking up room and what letting go of
it would give back.

- Working audio (a 170 MB wav per service) is thrown away on every start, as soon as there is a
  transcript to show for it. It takes a second to make again.
- A recording can be cleared once every fragment cut from it has been rendered. The transcript,
  the found moments and the finished videos stay; the panel says so on each row. A fragment that
  has not been rendered yet is given its own copy of its seconds first, so nothing is left
  pointing at a file that is gone, and rows that are not ready to go say why.
- Recordings older than `KEEP_WEEKS` (four by default, `0` turns it off) are cleared on start,
  again only when nothing is waiting on them.
- A clip that owns a copy of its footage lets go of it once its video has been made.

When free space drops below 3 GB the readiness check says so and names how much Opruimen could
give back.

## When something goes wrong

- The app bar shows a check of everything the app needs: FFmpeg, the speech model, the analysis model, free disk space and writable folders. It opens by itself when a check fails and says what to do.
- Every one of those checks asks whether a file is where it should be. **Doe de proef**, at the
  bottom of that same panel, asks whether the work runs: it takes the nine-second spoken
  sentence in `selftest/` through audio extraction, the speech model, the detectors and a
  1080×1920 render with a burned-in caption, and says per step whether it worked and how long
  it took. An FFmpeg built without libass, a model that half-downloaded, a card that cannot
  decode: all of those show up here in a minute instead of twenty minutes into a real service.
  The outcome travels in the report below.
- Everything the black window says is kept in `logs/preekstof.log`, and the four previous runs
  sit beside it. The file is capped, so a job that loops all night cannot fill the disk the
  recording needs.
- Next to any error, and at the bottom of the readiness panel, sits **Melding opslaan**. It
  downloads one zip: what went wrong, this machine, the readiness checks, the last four hundred
  log lines, `config.env`, and the state of the service that failed. The API key is struck out
  of all of it, twice over. Nothing is sent anywhere by the app; a person attaches it to a mail
  or does not. That is the whole of the telemetry in this program.
- Windows lets go of a file when it feels like it. Every save goes through a temporary file
  and a rename, and Windows refuses a rename onto a file that anything else has open, which
  includes the virus scanner reading what was just written. `models.write_atomic` gives each
  writer its own temporary name, takes one writer at a time per file, waits out a refused
  rename over about a second and a half, and writes straight over the file if it is still
  held. Saving the status of a service could fail there, and it used to fail *inside* the
  handler that was writing down a different failure, which threw the real error away and left
  the page waiting on work that had already stopped.
- A service that says it is busy with nothing running is not busy. `GET /services/{id}/status`
  checks the job as well as the file, so a status that never reached the disk shows up as what
  it is instead of as a bar that never moves.
- Long jobs can be stopped. Transcribing, analysing, cutting and rendering all have a **Stoppen** button; the job ends at its next checkpoint, which takes a few seconds for a render and up to half a minute for a transcription.
- Interrupted work carries on rather than starting over. Transcription writes down what it has heard every half minute, so closing the laptop half way through a 90-minute service costs the last thirty seconds, not the last twenty minutes. Analysis keeps each passage's answer, so a run that lost a passage to a rate limit only pays for that one the next time. After a restart the service goes back to the step before with a line saying which button carries on; pressing it continues where it stopped.
- Project and service files are written through a temporary file and renamed, so a crash or a power cut cannot leave half a file behind.
- One difficult piece of transcript no longer costs you the whole analysis. Each window is retried with growing pauses on a rate limit, server error or dropped connection, and a window that keeps failing is counted and skipped. You get the moments that were found plus a note saying how many pieces failed and why.
- The interface tells the difference between "the app is not answering" and "this went wrong". Losing the connection shows a calm banner and keeps polling; the work in the black window carries on.
- FFmpeg failures are translated: no space left, no permission, a damaged video file. A missing speech model or a rejected API key says which file to edit.

## Brands: one setup per church

Everything that makes a video belong to a church lives in a **brand**: the church details, the end screen, the default subtitle style and the default background music. Work for two locations or two churches and you make a brand for each, then switch between them in the **Merk en afsluiter** panel. New clips take the settings of the brand that is active, and the end screen is rebuilt when you switch.

Brands are stored as `templates/brands/<id>.json`, with `templates/brands/actief.json` naming the active one. On the first start the old `church.json` and `outro.json` are folded into one brand automatically, so nothing is lost.

## Logos

Logo files live in `templates/logos/` (ignored by git) and are used in two places: the corner of the clip (per project, in the **Logo in beeld** panel) and the end screen (per brand, in **Merk en afsluiter**). Upload once from either panel; png with transparency looks best. The corner logo is composited by FFmpeg with `overlay` at the chosen opacity and margin.

## Background music

The **Muziek** panel puts a track under the clip. Upload an mp3, m4a, wav, aac or ogg file once and it stays available for every clip; files live in `templates/music/`.

- **Volume** sets the level of the bed.
- **Onder de stem** turns on side-chain ducking: the music drops automatically while someone is speaking and comes back in the pauses. This is what makes a bed sound deliberate rather than loud.
- **Uitfaden** fades the music out at the end. The music runs under the end screen as well.

Speech is levelled to -14 LUFS with `loudnorm` before the music is mixed in, and the mix passes through a limiter, so clips from different services sound equally loud on Instagram and YouTube. You hear the music in the rendered video, not in the preview.

## Church outro (end screen)

`templates/outro.mp4` is appended after every clip, normalised to 1080×1920 during rendering. It is generated with FFmpeg (no AI) from two files:

- `templates/church.json` holds the church data. The `churchName` is also the small label above the wordmark in the interface.

  ```json
  {
    "churchName": "Example Church",
    "serviceTimes": ["09:30", "11:30"],
    "instagram": "@examplechurch"
  }
  ```

- `templates/outro.json` holds the look. **The Afsluiter panel in the Clip tab edits all of it**: background (solid colour, gradient with up to four colours and a direction, or an uploaded image with a darkening slider), font, duration, and the text lines with their size, colour, weight, font, letter spacing and capitals. Placement is direct: drag a line in the preview to move it up or down, drag it to the left or right third to align it there, or use **Zet alles boven / midden / onder** to move the whole block at once. The panel draws the end screen live while you type and rebuilds the video when you press **Opslaan en vernieuwen**. The file is created on the first start from the defaults; `templates/outro.example.json` is the copy in the repository. Every field:

  | Field | Meaning |
  | --- | --- |
  | `generate` | `false` keeps your own `outro.mp4` and never regenerates it |
  | `duration` | length in seconds (1–30) |
  | `font` | `Inter`, `Montserrat`, `Poppins` or `Arial`, used by every line without its own `font` |
  | `fade` | fade in and out, in seconds |
  | `background.type` | `solid`, `gradient` or `image` |
  | `background.color` | the colour for `solid` |
  | `background.colors` | 2 to 8 hex colours for `gradient` |
  | `background.angle` | gradient direction in degrees; 0 is left to right, 90 top to bottom |
  | `background.image` | file name in `templates/` for `image` |
  | `background.darken` | 0–1, a black veil over the image so text stays readable |
  | `motion` | `none`, `in` (slow dolly in), `out` (dolly out) or `up` (drift upwards) |

  | `logo.file` | optional PNG in `templates/logos/` (transparency supported) |
  | `logo.width`, `logo.y` | logo width and its vertical centre, in pixels of the 1080×1920 frame |
  | `lines[]` | the text lines, top to bottom |
  | `lines[].text` | the text; `{churchName}`, `{serviceTimes}` and `{instagram}` are filled in from `church.json` |
  | `lines[].y` | vertical centre in pixels (0 is the top, 1920 the bottom) |
| `lines[].align` | `left`, `center` or `right`, within a 60 px margin |
  | `lines[].size`, `weight`, `color` | font size, `regular`…`extrabold`, hex colour |
  | `lines[].font` | override the main font for this line |
  | `lines[].spacing` | extra letter spacing, for small uppercase labels |
  | `lines[].uppercase` | render the text in capitals |
  | `lines[].delay` | seconds before this line appears |

A line that is too wide is wrapped over two lines automatically, inside a 60 px margin on each side, so long church names and service times stay in frame. Move a line with its `y` when the wrapped text ends up too close to the next one. With a camera move the wrap point sits at the frame edge instead, so a line that fits at rest cannot suddenly break in two while it grows.

The camera move is drawn in two layers. Text is moved and scaled by libass, which works in floating point, so it glides instead of snapping to whole pixels; the background is a single still that an FFmpeg crop travels over, which is invisible on a gradient or a photograph. Both follow the same straight line, so the layers stay together. Measured on the default end screen, this brings the frame-to-frame wobble of the text down from 0.76 px to 0.02 px.

The end screen is rebuilt automatically whenever `outro.json` or `church.json` is newer than `outro.mp4`: on start and before every render. In the Clip tab, the **Afsluiter** panel shows the result and has a **Vernieuwen** button, so you can try colours without restarting. `python templates/make_outro.py` does the same from the command line.

Prefer your own video? Put it in `templates/outro.mp4`. Because its file date is then newer than the config, nothing overwrites it; set `"generate": false` to be certain.

The interface is in Dutch and carries the Nieuwe Kerk Utrecht colours: a deep purple app bar, display-size page titles, quiet numbered sections, and a dark stage panel that holds the preview and the one gold call to action. Gold carries meaning rather than decoration: the active tab, the crop frame, the fragment that is playing. Flat surfaces, hairline borders, Poppins throughout. No gradients in the interface itself. The colour tokens live at the top of `frontend/src/index.css`.

The mark is an open book with a waveform coming out of it, one purple vector in
`frontend/public/icon.svg`. It is both the tab icon and the mark in the app bar, and since it
is a single colour the app bar paints it through a CSS mask rather than dropping it in: purple
on the deep-purple bar would be a smudge, and this way it takes whatever colour the bar has.

Anything in `frontend/public/` is copied into the build as-is. That is the only place a brand
asset can live, because `npm run build` empties `frontend/dist` first and the launcher rebuilds
by itself whenever the source is newer than the build.

## Fonts

`templates/fonts/` holds the families the app offers, subset to the Latin characters Dutch needs (SIL Open Font License, licence texts included):

| Family | Character |
| --- | --- |
| Inter, Roboto, Open Sans | neutral sans, easy to read at any size |
| Montserrat, Poppins, Nunito | geometric and friendly |
| Oswald, Barlow Condensed | condensed, fits more words per line |
| Bebas Neue, Anton | heavy display, one weight, all caps feel |
| Lora, Playfair Display | serif, calmer and more formal |

Arial comes from the operating system. The backend scans the folder on request, so **dropping a pair of files named `{Family}-{Weight}.ttf` into `templates/fonts/` adds that font to both the subtitle and end-screen pickers** with no code change. Weights are `Regular`, `Medium`, `SemiBold`, `Bold` and `ExtraBold`; the family name inside the file must be `Family` for Regular and Bold and `Family Weight` for the rest, which is how Google Fonts static instances are built. A family that lacks the chosen weight falls back to its nearest one, so single-weight fonts work everywhere.

The renderer passes this directory to libass and the browser loads the same files, so the preview matches the output.

## API

```text
POST /projects                      create an empty project
POST /projects/{id}/upload          multipart upload (field "file"); probes the video
POST /projects/{id}/transcribe      start the Dutch transcription as a background job
GET  /words                         the mishearings this church knows about
GET  /projects/{id}/transcribe-status  {status, progress, message, error, canStop}
POST /projects/{id}/transcribe/stop stop the transcription that is running
GET  /projects/{id}                 project + transcript
PUT  /projects/{id}/transcript      save edited segments
PUT  /projects/{id}/style           save subtitle style
PUT  /projects/{id}/crop            save the crop window {x, y, zoom}
PUT  /projects/{id}/music           save the background music for this clip
PUT  /projects/{id}/meta            save the title and the description for sharing
PUT  /projects/{id}/watermark       save the corner logo {file, corner, width, opacity, margin}
POST /projects/{id}/render          start the background render job
POST /projects/{id}/render/stop     stop the render that is running
GET  /projects/{id}/render-status   {status, progress, message, error, canStop}
GET  /projects/{id}/output          the rendered final.mp4, named after the clip's title
GET  /projects/{id}/source          the footage behind the clip; for a clip cut from a service
                                    that is the whole recording, and the interface skips to
                                    `sourceStart` and stops at the end of the range
GET  /church                        contents of templates/church.json
GET  /health                        FFmpeg, speech model, analysis model, disk space, folders
GET  /storage                       what is taking up room and what clearing it would give back
POST /storage/clean                 clear one recording or one clip {kind, id}
POST /storage/clean-old             clear everything past the keep-by date with nothing waiting
PUT  /services/{id}/accuracy        pick the quick model or the one that hears more
GET  /brands                        the brands, and which one is active
GET  /brands/{id}                   one brand: church, end screen, subtitle style, music
PUT  /brands/{id}                   save a brand (rebuilds the end screen when it is active)
POST /brands                        create a brand, optionally copied from another
POST /brands/{id}/activate          make a brand active
DELETE /brands/{id}                 remove a brand (never the last one)
GET  /logos                         the logo files for the corner and the end screen
POST /logos                         upload a logo (png, jpg, webp, svg)
DELETE /logos/{name}                remove a logo
GET  /music                         the music files that can go under a clip
POST /music                         upload a music file
DELETE /music/{name}                remove a music file
GET  /fonts                         font families found in templates/fonts
GET  /outro                         the end-screen config from templates/outro.json
PUT  /outro                         save the end-screen config and rebuild the video
POST /outro/background              upload a background image for the end screen
POST /outro/rebuild                 rebuild templates/outro.mp4 from the config on disk
GET  /templates/...                 fonts and outro.mp4 (for the preview)

POST /services                      create an empty service
POST /services/{id}/upload          multipart upload of the full recording
GET  /services                      services worked on before, newest first (?limit=12)
POST /services/{id}/link            fetch the recording from a link (body: {"url"}), as a job
GET  /kerkdienstgemist/stations/{id}  a church's recent services, ready to pick from
POST /services/{id}/transcribe      background transcription (status: transcribing -> transcribed)
POST /services/{id}/analyze         background LLM analysis (status: analyzing -> ready)
GET  /services/{id}                 service + transcript + running job progress
GET  /services/{id}/status          small payload for polling (status, job, counts)
GET  /services/{id}/candidates      ranked candidates
PUT  /services/{id}/candidates      save selection and boundary edits
POST /services/{id}/process-selected  cut each selected candidate into a clip project (status: processing -> complete)
POST /services/{id}/stop            stop the transcription, analysis or cutting that is running
GET  /services/{id}/source          the recording (for candidate preview)
```

Rendering uses an in-process job manager (`backend/jobs.py`), one thread per render. There is no Redis or Celery.

## Project layout

```text
backend/
  main.py           FastAPI routes
  models.py         Pydantic models + project storage (projects/<id>/project.json)
  transcription.py  FFmpeg audio extraction + faster-whisper (nl)
  subtitles.py      transcript → ASS (fonts, outline, box, margins, two-line wrapping)
  renderer.py       ffprobe metadata, crop strategies, FFmpeg render with progress
  jobs.py           in-process background jobs
  discovery.py      transcript passages -> LLM analysis -> deduplicated, ranked ClipCandidates
  settings.py       one value out of config.env, typo and all
  setup.py          the first five minutes: what a church still has to fill in
  version.py        one version number, read by the app, the console and every diagnostic
  outro.py          end-screen config -> ASS + FFmpeg, rebuilt when the config changes
  fonts.py          which font families and weights templates/fonts holds
  brands.py         brand presets: church, end screen, subtitle style, music
  health.py         the checks the interface shows
  clips.py          create_clip(source, start, end): cuts a range into a regular clip project
  mac.py            speech on the graphics chip of an Apple Silicon Mac, via mlx-whisper
  vision.py         the two ONNX detectors: faces (YuNet) and people (YOLOv10n)
  tracking.py       detections -> one calm path for the crop window to walk
frontend/public/
  icon.svg                     the mark: tab icon and app bar, one purple vector
  icons.svg                    the social glyphs the end-screen editor draws from
frontend/src/
  App.tsx                      tab switch between Full service and Clip; holds the welcome gate
  components/Welcome.tsx       the first five minutes: what it is, the key, the church, the station
  api.ts                       typed API client (projects + services)
  remember.ts                  the handful of things kept between visits, under one prefix
  subtitleLayout.ts            layout constants shared with subtitles.py
  crop.ts, track.ts            the crop window and the tracking path, mirrored from renderer.py
  components/ClipEditor.tsx    single-clip editor: project state, API calls, auto-save, render polling
  components/ServiceView.tsx   full-service upload, states, progress, processed clips
  components/ClipSuggestions.tsx  ranked candidate list: preview, select, adjust boundaries
  components/ServiceTranscript.tsx  the whole service to read, search and cut from
  components/ServiceTimeline.tsx    the shape of the service with the fragments on it
  transcriptSearch.ts          hits, highlighting and what a run of sentences covers
  components/BrandPanel.tsx    brand switch, church details and the end-screen editor
  components/MusicPanel.tsx    background music under the clip
  components/LogoPanel.tsx     the church logo in a corner of the clip
  components/SharePanel.tsx    title (file name) and description for the post
  components/SystemCheck.tsx   the readiness check in the app bar
  fonts.ts                     font catalogue: loads the faces and resolves weights
  components/VideoPreview.tsx  9:16 preview with subtitle overlay and outro
  components/SubtitleEditor.tsx
  components/StylePanel.tsx
  components/RenderControls.tsx
  components/ProgressIndicator.tsx
templates/
  church.json, outro.json (created on first start), outro.example.json, make_outro.py, outro.mp4
  fonts/  logos/  music/  brands/  woordenlijst.json
vision/
  face.onnx         YuNet face detector, 227 KB, shipped with the app (MIT)
  person.onnx       YOLOv10n, 9 MB, fetched on first use (AGPL-3.0, see vision/README.md)
launcher.py         loads config.env, fetches FFmpeg when missing, starts the server, opens the browser
start.bat / start.command   one-click launchers for Windows and macOS (create .venv, install, run launcher.py)
config.example.env  template for config.env (API key, LLM provider, whisper model)
tools/speechbench.py        time the two speech engines against each other on your own recording
projects/           one directory per clip project (ignored by git)
services/           one directory per full service (ignored by git)
```

A project directory keeps the source clip untouched next to derived data:

```text
projects/project-3d25a7a1/
  project.json      metadata, style, output settings, crop strategy, tracking path
  source.mp4        original upload
  transcript.json   {"segments": [{"start", "end", "text"}, ...]}
  work/             audio.wav, subtitles.ass, track.cmd
  output/final.mp4
```

## Render pipeline

```text
source.mp4 → static 9:16 crop → fps 30 → burn subtitles.ass (libass) → concat outro
speech → loudnorm -14 LUFS → (optional) mix with ducked music → limiter
→ libx264 crf 20 + AAC 160k → final.mp4
```

The crop window `{x, y, zoom}` on the project decides the framing: `x`/`y` are the frame centre as fractions of the scaled source, `zoom` is relative to the scale that exactly fills the frame (1 fills, smaller letterboxes, larger crops in). The renderer scales the source, crops the part inside the frame and pads whatever is left. Defaults: landscape sources fill the frame centred, portrait sources keep the whole picture. The outro is always scaled to fit. Output is `yuv420p`, High profile, `+faststart`, which uploads directly to Instagram and YouTube.

## Following the speaker

A wide camera at the back of a church puts the preacher in a small part of a broad frame. A 9:16
window either loses them when they move or has to be pulled so far out that the clip looks like
security footage. `crop_strategy="tracked"` lets the window walk along a path found in the clip
itself.

**What looks.** Two ONNX models, run on the CPU through onnxruntime, which is already here for
speech recognition:

| Model | Size | Runs | What it answers |
| --- | --- | --- | --- |
| `vision/face.onnx` (YuNet) | 227 KB | every sample | where the head is, which is what you frame |
| `vision/person.onnx` (YOLOv10n) | 9 MB | every third sample | who is on stage, held across the clip |

The body decides *who* and changes slowly, so it is asked about once a second. The face decides
*where* and is asked every time. When the face turns away the body carries the frame on alone; when
both are gone the last position stands for two and a half seconds and after that the clip admits a
gap. The face model ships with the app. The person model is fetched on first use, the way FFmpeg
already is, and the app still follows a speaker without it.

**What moves.** `tracking.py` turns those sightings into one position per 1/12.5 second, and almost
all of it is about not moving. Distances are shares of the crop window's own width, so the same
numbers behave the same way on a tight crop and a wide one, with the frame edge at 0.5:

- **dead zone** (0.14) the speaker drifts around the middle and nothing happens at all
- **ease** past it the frame glides back, exponentially, capped at 0.4 crop widths per second
- **keep-in line** (0.34) they are about to walk out of the picture, so calm stops being the point
  and the frame catches up at 1.1 crop widths per second
- **cuts** a church with several cameras cuts between them, and there is nothing smooth about a
  cut, so the frame jumps with it. The threshold is a spike against what this clip normally does,
  not a fixed number, because two cameras in one room differ far less than two rooms

Only x moves while the clip plays. On a 9:16 window out of a wide frame there is rarely anything
above or below worth following, and vertical drift is the first thing that reads as wobble.

**How tight.** A camera at the back of a church leaves the speaker small, and a 9:16 window cut out
of that is a distant figure in a lot of empty church, so the search also proposes a zoom. The person
box says how tall the speaker is (without the person model, a head and the seven and a half heads a
standing adult measures); the zoom that would make them fill 62% of the frame height is worked out
and then capped, at 1.6× and at 3.2 output pixels per source pixel, whichever bites first. A 720p
recording therefore gets far less room than a 1080p one, which is the honest answer rather than a
soft clip. Cropping in makes the vertical position matter, so a starting y comes with it, putting
the head about a third of the way down. Both are a starting point: the zoom slider and dragging the
frame up and down stay the user's, and only sideways is locked while the frame follows.

**What renders.** `renderer.track_commands` reads the path at 50 a second and writes a `sendcmd`
script, one line per moment the window would land on a different pixel, driving a labelled
`crop@track` filter. A speaker standing still costs a handful of lines rather than one per frame.
`renderer.track_at` is mirrored in `frontend/src/track.ts`, so the preview draws the frame exactly
where the render will put it; `tests/mirror_cases.py` diffs the two.

**When it runs.** Cutting a service into clips looks for the speaker in each clip while you are
already waiting, so a clip opens with the speaker followed. That is the long part of that step now,
and the dock at the bottom of the page carries the bar, the fragment it is on and what is left. A clip that arrived on its own gets a
**Zoek de spreker** button. Either way the **Beeldkader** panel keeps both modes side by side: a
path that turned out badly is one click away from a static window you place yourself. A path found
in less than 55% of a clip is kept but not switched on.

Measured on a 90-second sermon at 1280×720, one camera: tracked in 15 seconds (six times realtime),
the speaker found in 100% of samples, the frame perfectly still on 93% of steps, and the largest
single step 1% of the width. Rendering the same clip both ways and looking for the head in the
finished 9:16 videos, 68 samples each: average distance from the centre 0.17 tracked against 0.49
static, and 0 samples with the head against the edge of the frame against 15. He stays in frame
either way on this clip, because the speaker stays behind the lectern; where they sit in the frame
is the difference. On a staged clip with a camera change in it the frame jumps inside one frame.
