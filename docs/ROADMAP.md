# Roadmap: from working pipeline to weekly production tool

The pipeline runs end to end: service in, ranked moments out, 9:16 clip with subtitles and end
screen. What it is not yet is something a volunteer can run every Monday without a developer
nearby, and the moments it proposes are not yet reliably the ones a church would post.

Three phases. Phase 1 removes what will break or exhaust someone on a real weekly run. Phase 2
makes the selection worth trusting. Phase 3 makes the output look produced.

Each step lists the priority it serves, using the numbering from the request:
(1) selection and ranking, (2) stability and performance, (3) review UX,
(4) tracking and framing, (5) captions and clip quality, (6) church-specific analysis.

---

## Phase 1 · Survive weekly use

Two to three weeks. Nothing here is glamorous and all of it is load-bearing.

### Step 1 · A regression net, before anything else
Serves (2)

**Build.** A `tests/` package with pytest covering the pure functions that carry the quality of the
product: `subtitles.layout_text`, `discovery.build_windows/snap/score/dedupe_and_rank`,
`clips.slice_transcript`, `renderer.cropGeometry`, `brands.slug`. A fixed 3-minute transcript
fixture whose ASS output is asserted byte for byte. A node test that runs the same fixtures
through `subtitleLayout.ts` and `crop.ts` and diffs against the Python results. One end-to-end
test that pushes a 20-second fixture video through upload, a stubbed transcript and a render,
asserting 1080×1920 and the expected duration.

**Why.** 5,959 lines of code and zero automated tests. Every step below touches wrapping, ranking
or the FFmpeg filter chain, and today the only way to learn that something broke is to render a
video and look at it. Worse, `subtitles.py` ↔ `subtitleLayout.ts` and `renderer.py` ↔ `crop.ts`
are hand-maintained mirrors: when they drift, the preview quietly lies about the render, and
nobody notices until a church posts a clip whose subtitles sit somewhere else.

**Done.** `pytest` green in under 30 seconds, `npm test` runs the mirror comparison on the same
fixtures, both wired into CI and the session-start hook. A deliberate one-character change to
`CHAR_WIDTH_RATIO` in either language turns the suite red.

### Step 2 · Stop encoding every clip twice
Serves (2) and (5)

**Build.** Remove the intermediate cut. `clips.create_clip` re-encodes each selected range at CRF
18 full resolution (`backend/clips.py:15`), and the renderer then encodes that result again. The
range is already recorded on the project as `origin.start/end`, so the render can read the service
recording directly with `-ss`/`-t` on the input. Keep `extract_range` behind a flag for the case
where someone wants to delete the recording and keep the clips.

**Why.** Two generations of H.264 on every clip, visible as mush on skin tones and gradients, and
roughly double the CPU per clip. Processing eight moments from a 90-minute service means eight
full re-encodes before any subtitle work starts.

**Done.** "Verwerk gekozen fragmenten" finishes in seconds instead of minutes. A rendered clip is
one encode away from the camera original. A side-by-side of the same moment, old against new,
shows less blocking in the background.

### Step 3 · Batched transcription with a real ETA
Serves (2)

**Build.** Move to faster-whisper's `BatchedInferencePipeline` with the batch size chosen from
available cores and memory. Let model size follow the job: `small` for clips, an explicit
"nauwkeuriger, duurt langer" switch for `medium` on full services. Derive an ETA from the
throughput of the first two minutes and show it as time remaining, not only a percentage.

**Why.** 20 to 40 minutes for a 90-minute service on a laptop CPU is the longest wait in the
product by a wide margin. Batching typically gives two to four times on CPU. The person running
this on Monday morning wants to start it and walk away with a number they can plan around.

**Done.** A 90-minute recording transcribes in under 15 minutes on a mid-range laptop, and the
remaining-time estimate is within 20% for the whole second half of the run.

### Step 4 · Retention and disk hygiene
Serves (2)

**Build.** A cleanup pass on startup plus an "Opruimen" panel. Services older than N weeks lose
`source.mp4` and `work/audio.wav` and keep `service.json` and the transcript. Rendered projects
lose `source.mp4` once the output has been downloaded. Show what is kept and what it costs in GB,
and let the church change N.

**Why.** A 90-minute service is 2 to 6 GB in, plus a 170 MB wav, plus a full-resolution copy per
selected clip. Weekly use fills a laptop inside two months, and today's failure mode is FFmpeg
dying halfway through a render with the disk full.

**Done.** Ten simulated weekly services leave the app under 10 GB. The health check warns while
there is still room to act, not after a render has already failed.

### Step 5 · Jobs that survive a closed laptop
Serves (2)

**Build.** Persist job state on each progress update. On startup, offer to resume instead of only
marking the work as failed, which is all `models.recover_services` does now. Transcription resumes
from the last completed segment. Analysis skips windows whose results are already on disk.

**Why.** Closing the lid during a 30-minute transcription currently loses all of it, and that is
the most expensive step in the product to redo. It will happen every week.

**Done.** Killing the process mid-transcription and restarting picks up where it stopped, with a
complete transcript and no duplicated segments.

---

## Phase 2 · Make the selection worth trusting

Three to four weeks. This is where the product either earns its place or does not.

### Step 6 · Two-pass analysis: read the windows, then choose like an editor
Serves (1)

**Build.** Keep the map step over 180-second windows. Add a reduce step: send every surviving
candidate back to the model in a single call, each with its title, summary, reason and excerpt,
together with a short summary of the whole service, and ask it to pick and rank the best five to
ten for this service. Require a one-line justification per pick and an explicit reason for each
rejection. Keep both layers so the reviewer can open "ook gevonden, niet gekozen".

**Why.** Ranking today is `confidence + duration bonus` (`backend/discovery.py`, `score`), where
confidence is self-reported per window by a model that has never seen the rest of the service.
Across 36 windows those numbers are not comparable, so the ordering is close to arbitrary. Nothing
in the pipeline ever compares the sermon's best moment against its second best. This is the single
biggest lever on whether the proposed clips are worth posting.

**Done.** On three real services, at least four of the top five after the reduce pass are moments
the church would actually post, judged blind against the current ranking by someone from that
church.

### Step 7 · Know which part of the service you are in
Serves (1) and (6)

**Build.** A cheap structural pass before analysis that labels the transcript into welcome, songs,
readings, prayer, sermon, notices and blessing, using the vocabulary already in
`templates/woordenlijst.json` plus timing heuristics: song blocks produce sparse transcript,
notices cluster at the end, readings carry book names. Feed the label into each window prompt and
drop notice and liturgy windows before they are sent at all.

**Why.** Roughly half of a 90-minute service is not sermon. Analysing it costs money, adds noise to
the candidate list, and the prompt currently has to fight it with a bullet point. Skipping it is
cheaper and produces a cleaner list.

**Done.** Analysis cost falls by 40% or more on a real service, no candidate lands inside a notices
block, and the review timeline shows the service structure as a background band.

### Step 8 · An evaluation set, so "better" means something
Serves (1)

**Build.** Ten real services with a human-marked list of the moments that were actually posted. A
script that runs the pipeline over them and reports precision at five, recall of the posted set,
and cost per service. Every prompt or scoring change is measured on it before it ships.

**Why.** Prompt changes feel better and get worse all the time. Without a fixed set the team tunes
by anecdote. This is also the first number a national tech partner will ask for, and the one that
turns "we built a tool" into "we measured it".

**Done.** `python -m tools.evaluate` prints the table, and today's pipeline has a baseline written
down next to the date.

### Step 9 · Church vocabulary that improves itself
Serves (6)

**Build.** Extend `templates/woordenlijst.json` per brand with preacher names, series titles,
recurring hymn collections and local place names. Add a light feedback loop: when someone corrects
a word in the subtitle editor, offer to add that correction to the church's list. Pass the sermon
title and series into the analysis prompt when the church fills them in.

**Why.** Whisper gets Dutch church language wrong in predictable, repeating ways, and every wrong
word costs the reviewer an edit. Names are the worst of it and the most damaging in a clip that
goes out in public.

**Done.** After a month of use at one church, an unedited transcript from that church has fewer
than one name error per five minutes.

---

## Phase 3 · Make it look produced

Four to six weeks.

### Step 10 · Review in one screen, decided in five minutes
Serves (3)

**Build.** Rework `ClipSuggestions.tsx` from a scrolling article list into a triage view: compact
candidate rows on the left, one large 9:16 preview on the right playing the selected candidate
with live subtitles, and keyboard control (j/k to move, space to play, Enter to accept, x to
reject). A running count of what is selected, and bulk accept and reject. Boundary nudging stays,
behind a disclosure.

**Why.** The current screen asks the user to scroll a long list, open a disclosure, read an
excerpt and operate a separate player below. A volunteer with 20 minutes will not do that for 15
candidates. Selection is the only step in the product that genuinely needs human judgement, so it
deserves the best interface in it.

**Done.** Someone who has never seen the app reviews 15 candidates and produces four clips in
under five minutes without asking a question.

### Step 11 · Dynamic 9:16 framing
Serves (4)

**Built.** `backend/vision.py` looks at three frames a second with YuNet for faces and, every third
of those, YOLOv10n for people; the body says who is on stage and holds that identity, the face says
where the head is. `backend/tracking.py` turns the sightings into one x per 1/12.5 second through a
dead zone, an exponential ease with a speed cap, a keep-in line that lifts the cap when the speaker
is about to leave the picture, and a shot-cut detector that snaps rather than pans when a church
cuts to another camera. `renderer.track_commands` writes a `sendcmd` script read at 50 a second
against a labelled `crop@track` filter; `frontend/src/track.ts` mirrors the same lookup so the
preview shows where the render will put the frame. Cutting a service runs it per clip; a clip on
its own has a **Zoek de spreker** button. A path found in under 55% of a clip is kept but not
switched on, and **Zelf kaderen** is always one click away.

The timeline with draggable keyframes was dropped on purpose. Two buttons and a sentence about what
was found is the whole interface: a path that reads wrong is not worth editing keyframe by keyframe
when placing a static window by hand takes five seconds.

**Why.** A wide camera at the back of a church puts the preacher in a small part of a broad frame.
A static centre crop either loses them when they move or has to be pulled so far out that the clip
looks like security footage. This is the clearest visual difference between a clip cut from a
recording and a clip made for social.

**Done.** Measured on a 90-second sermon at 1280×720: detection runs at six times realtime, the
speaker is found in 100% of samples, the frame is perfectly still on 93% of steps, and the largest
single step is 1% of the width. Rendered both ways and measured on the finished videos, the head
sits 0.17 from the centre tracked against 0.49 static, and never against the edge against 15 of 68
samples. A staged two-camera cut jumps inside one frame.

### Step 12 · Captions that read like captions
Serves (5)

**Built.** `chunk_words` works out how far a caption could run and then scores every break inside
that: a finished sentence, a comma, a real silence, and a penalty for ending on one of the Dutch
words that lean on what comes next. Whisper's word timings are kept on the segment instead of
being thrown away, read back through `subtitles.word_times`, which spreads the words over the
caption when an edit has left the timings not matching the text; `Style.highlight` lights each
word as it is said, in the ASS file and in the preview, from those same timings. The editor marks
a line faster than 2.5 words a second, longer than 7 seconds, or holding a word the church has
written down as a mishearing, and says which.

**Why.** Captions are what the viewer actually reads, since most social viewing is muted. A line
break in the wrong place is the difference between a clip that looks made and one that looks
generated.

**Done.** On ninety seconds of real preaching, lines ending on punctuation went from 77% to 85%
and lines left hanging on a leaning word from three to one; over a twenty-line sample at least
three quarters end where the sentence breathes. The highlighting is proved by rendering a clip
and reading the pixels: one word lit at a time, walking along the line, nothing lit before the
caption starts. The editor flags every line that is too fast, too long, or holds a known
mishearing, with the reason under the line itself.

---

## Phase 4 · Out of your own hands

A pilot at a handful of churches, with Donkey Mobile watching. The question stops being
whether the code is good and becomes what happens on a Monday morning at a church you
cannot see, on a computer you have never touched, run by someone who will not read a
manual and cannot open a terminal.

Everything that has been built so far assumed the developer was in the room. These steps
remove that assumption. Three to four weeks, and the first three block everything else.

**Not in this phase, on purpose.** One installation stays one church. No accounts, no
server, no multi-tenancy, no hosting. Every pilot church runs it on their own machine
exactly as it runs today, because the fastest way to learn whether this is worth building
into a product is to put the thing that already works in front of five churches, and the
slowest is to rebuild it as a service first.

### Step 13 · A licence, before the repository leaves the building
Serves (share)

**Build.** A `LICENSE` file. Without one, nothing is granted: another company may read a
public repository but may not run, modify or ship it, and a careful engineering team will
notice that before they notice anything else. Two honest options. All rights reserved plus
a short written permission for Donkey Mobile to evaluate and pilot it, if this may become a
product. Or a permissive licence if it may not. Decide which, and add a `NOTICE` listing
what the app already depends on and under what terms: FFmpeg, faster-whisper, CTranslate2,
YuNet, YOLOv10n, yt-dlp, the bundled fonts, the Anthropic SDK.

**Why.** It is one file and it is the only thing on this list that a lawyer will ask for
first.

**Done.** A `LICENSE` at the root, a `NOTICE` naming every bundled dependency and its
licence, and a line in the README saying what a pilot church is allowed to do.

### Step 14 · Shut the door the browser left open
Serves (2)

**Build.** `allow_origins=["*"]` with no authentication anywhere. While the app runs, any
website open in the same browser can read `http://localhost:8000/services`, fetch a
transcript, and post to delete a service or start a job. The frontend is served from the
same origin as the API, so the wildcard buys nothing: restrict it to the app's own origin
plus the Vite dev server, and add a test that a foreign origin is refused.

**Why.** It is five lines. On one developer's laptop it is theoretical; at five churches
with volunteers who browse while the app runs, it is a transcript of a pastoral prayer
leaving the building.

**Done.** A request carrying `Origin: https://ergens-anders.nl` comes back without an
`access-control-allow-origin` header, the app itself still works, and a test in
`tests/test_origins.py` fails if the wildcard ever comes back.

### Step 15 · A version, said out loud
Serves (support)

**Build.** One version string, written once and read everywhere: the app bar, the readiness
panel, the window title of the black console, and every diagnostic the app produces. A
`CHANGELOG.md` in the repo with a line per release in plain Dutch, aimed at a volunteer
rather than a developer.

**Why.** The first question on every support call is which version they are running, and
today nobody can answer it. It also makes "dat is vorige week opgelost" a checkable claim
instead of a hope.

**Done.** The version is visible in the interface without scrolling, appears in the
diagnostic of step 17, and `git tag` matches what the app says.

### Step 16 · Install and update without a developer — gedaan (0.9.0)
Serves (onboarding)

**Wat er staat.** Een tag bouwt `preekstof-<versie>.zip` uit wat git bijhoudt en zet hem op
Releases; `tools/release.py` doet dat ook met de hand. De zip weigert zichzelf als de tag en
`backend/version.py` iets anders zeggen, of als de meegecommitte `frontend/dist` niet is wat
die code bouwt. Bij het starten kijkt `backend/updates.py` één keer bij GitHub en zegt in het
zwarte venster wat er is en waar het staat; installeren doet hij nooit zelf. Het scherm voor de
sleutel kwam er al in dezelfde versie.

**Nog niet gedaan.** Niemand heeft de tien minuten geklokt op iemand die de app nog nooit zag.
Dat is de eigenlijke test en die moet bij de eerste pilotkerk.

**Build.** Two things a volunteer cannot do today: get the app, and get the new one. Ship a
release as a downloadable zip that contains what `git clone` gives them, so nobody installs
git. Then add an update check: on start, the launcher asks GitHub for the newest release
and, when there is one, says so in the black window with what changed and what to download.
Not an auto-update, because a church rebuilding itself unattended on a Sunday morning is
worse than a church running last month's version.

The harder half is the API key. Today it goes into `config.env` with Notepad, and that is
the single biggest wall between a willing church and a working app. Replace it with a
first-run screen: the app opens, sees no key, and asks for one with a link to where you get
it and a sentence about what it costs. It writes `config.env` itself. The same screen is
where a key issued by Donkey Mobile would go later, so this step does not commit you to who
pays.

**Why.** Every pilot church that fails here never becomes a pilot church, and you will not
hear about it.

**Done.** Someone who has never seen a terminal downloads the zip, double-clicks
`start.bat`, pastes a key into the screen the app shows them, and gets to the upload page.
Timed on someone who has not seen the app before: under ten minutes, without you on the
phone.

### Step 17 · When it breaks, you get to see it — gedaan (0.9.0)
Serves (support)

**Wat er staat.** Alles wat het zwarte venster zegt gaat naar `logs/preekstof.log`, per keer,
met de vier vorige ernaast en een plafond erop. Naast elke foutmelding en onderin het
gereedheidspaneel staat **Melding opslaan**: één zip met de melding, de gereedheidscontroles,
de laatste vierhonderd regels, de instellingen, de dienst die vastliep en `runs.jsonl`. De
sleutel wordt er twee keer uit gefilterd. De app stuurt zelf niets, ergens heen.

**Gecontroleerd.** De drie gevraagde storingen zijn nagespeeld in `tests/test_diagnose.py`:
geen sleutel, een opname die niet te lezen is, en een volle schijf. Alle drie noemen de
oorzaak op de eerste pagina en geen van de drie bevat de sleutel.

**Build.** Every failure in this app currently ends in `print()` to a console window that
the volunteer closes. There is nothing to send you. So: a log file next to the app,
rotated per run and capped, holding everything the black window shows. And an "Er ging iets
mis" button on any error that writes one zip to the desktop: the version, the operating
system, the last few hundred log lines, the state of the service that failed, and the
settings with the API key struck out. The volunteer mails it. Nothing is sent anywhere by
the app itself.

**Why.** A pilot where the only report is "het werkte niet" teaches you nothing, and asking
a volunteer to reproduce a failure is asking them to stop using it. The deliberate absence
of telemetry is also what lets a church say yes: nothing leaves their building unless a
person attaches it to an email.

**Done.** Three failures staged on purpose (no key, a corrupt recording, a full disk) each
produce a zip that names the cause on its first page, and none of the three contains the
API key.

### Step 18 · What happens to our recording, in writing — gedaan (0.9.0)
Serves (share)

**Wat er staat.** `PRIVACY.md`, één pagina voor een kerkenraad, en de korte versie in de app
naast de kosten. Het benoemt wat er in een uitgeschreven preek kan staan waar niemand aan
denkt, zegt dat dat onder de AVG bijzondere persoonsgegevens zijn, en wijst de uitweg aan
(`LLM_PROVIDER=ollama`) voor een kerk die dat niet wil. `tests/test_privacy.py` houdt de
belofte tegen de code aan: een module die met de buitenwereld praat en niet in de pagina staat,
laat de test vallen.

**Build.** A `PRIVACY.md` a church can hand to its own board, and a short version in the
app where the cost estimate already is. It has to say plainly: the recording and the audio
never leave the computer; the written-out text of the preaching goes to Anthropic and is
not used for training under their API terms; the speech and detection models are downloaded
once from Hugging Face; the recording is fetched from wherever the church already publishes
it; nothing is sent to the developer. Then the parts churches actually worry about: a
sermon transcript carries names of sick members and what was prayed for, which under the
AVG is not ordinary personal data. Name it, say that `LLM_PROVIDER=ollama` keeps everything
in the building for a church that will not accept it, and say how long recordings are kept
(`KEEP_WEEKS`) and how to wipe them.

**Why.** Donkey Mobile's customers will ask, and the honest answer here is a good one. It
is only a weakness while it is undocumented.

**Done.** A church council can read one page and decide. The same page answers, without
hedging, what a transcript contains and where it goes.

### Step 19 · Say what machine it needs, measured — half gedaan (0.9.0)
Serves (onboarding)

**Wat er staat.** Het gereedheidspaneel heeft een regel **Snelheid**. Elke keer uitschrijven
schrijft op hoeveel audio er in hoeveel tijd ging, en vanaf de tweede dienst citeert het paneel
de mediaan van wat déze computer echt deed. Meer dan twee uur voor één dienst staat niet op
groen: dat is niet traag, dat is onbruikbaar.

**Wat er niet staat.** De tabel in de README heeft één echt gemeten rij: vier kernen x86_64,
`small` op de processor, 0,20 seconde werk per seconde audio, dus 18 minuten voor anderhalf
uur dienst. De rijen voor Apple Silicon en voor een NVIDIA-kaart staan er als *niet gemeten*,
omdat een geraden getal het getal is waar een kerk haar zondag op plant. Die moeten op een
echte MacBook en een echte pc gedraaid worden; `tools/speechbench.py` doet het werk.

**Build.** Transcription is the long pole and nobody knows how long it is on a church's
actual computer. Add a benchmark the launcher can run once (`tools/speechbench.py` already
does most of it) and write the answer into the README as a table: this processor, this many
minutes for a service of ninety. Then a readiness check that says, before the first
upload, roughly how long this machine will take. A church that learns on Sunday afternoon
that it takes two hours has already stopped using it.

**Why.** The most common pilot failure is not a bug. It is a computer that is too slow and
an expectation nobody set.

**Done.** The readiness panel states a number for the machine it is on, and that number is
within a quarter of what the machine really does on a real service.

### Step 20 · Let the pilot teach you something — klaargezet, wacht op kerken
Serves (1)

**Wat er staat.** `evaluation/TOESTEMMING.md` is de mail die verstuurd moet worden, inclusief
de twee dingen die een kerk zelf moet nakijken voordat ze ja zegt. `tools/adopt.py` maakt van
een dienst die de app gedaan heeft een meetgeval, met als antwoordblad de clips die echt
gemaakt zijn; een dienst zonder clips wordt geweigerd in plaats van met een leeg antwoordblad
opgenomen. En de app schrijft tijdens het werken elke keer op wat het kostte en hoe lang het
duurde, in `logs/runs.jsonl`, waar geen kerknaam en geen woord uitgeschreven tekst in staat.
`tools/pilot.py` maakt daar de vier getallen van.

**Wat er niet staat.** Vijf echte diensten. Die bestaan alleen als er kerken zijn, en pas als
er toestemming ligt.

**Build.** `evaluation/` holds one invented service, so no claim about the quality of the
suggestions is currently checkable. Ask each pilot church, in writing, whether one of their
services may be kept as a test case: the transcript, and which moments they actually
posted. Five real services turn `tools/evaluate.py` from a harness into an instrument. Log
per run what it cost and how long it took, so at the end of the pilot there are four
numbers per church rather than an impression.

**Why.** The pilot is the only chance to find out whether reading the whole sermon in one
call finds better moments than sixteen windows did, and whether the moments a church posts
are the ones the app ranks first. After the pilot those services are gone.

**Done.** Five real services in `evaluation/`, with permission on file, and a table showing
precision at five and recall per church against the moments they posted themselves.

### What is still open from Phase 3

Step 10, review in one screen, was never finished. The transcript panel took part of it:
the whole service is readable and searchable, and a moment can be cut by hand. What is
missing is the timing claim, that someone who has never seen the app reviews the
suggestions and produces four clips in under ten minutes. The pilot is where that gets
measured rather than designed.

---

## Phase 5 · Believable on the first Sunday

Phase 4 made the app shippable. This phase is about the hour after it is shipped.

A pilot does not fail on a crash. It fails in the first hour, at the moment somebody cannot
tell whether the thing is working or hung, and again three weeks later when it stops for a
reason nobody can read. Both of those are quiet. Nobody writes to say "I waited eleven
minutes at four percent and gave up"; they simply stop opening it, and you find out at the
end of the pilot that two of the five churches used it twice.

So the question here is not whether the app can do the work. It can. The question is
whether a volunteer, alone in a church office on a Sunday afternoon, keeps believing it is
doing the work.

**Not in this phase, on purpose.** No new output, no new panel, no better clips. Everything
below either shortens the time somebody spends not knowing, or turns a silent failure into
a sentence.

### Step 21 · Prove it works, in one minute, before it matters — gedaan (0.9.0)
Serves (onboarding, support)

**Wat er staat.** Onderin het gereedheidspaneel staat **Doe de proef**. Die haalt
`selftest/proef.opus`, één gesproken Nederlandse zin van negen seconden en 22 kB, door
dezelfde vier stappen als een echte dienst: geluid eruit met FFmpeg, het spraakmodel dat de
zin terugleest, de detectoren over elk beeld, en een render naar 1080×1920 met een ondertitel
erin gebrand. Elke stap zegt of hij liep en hoe lang hij deed. De clip komt eronder te staan
om te bekijken, en wat het model terugleest staat er in zijn eigen woorden bij, fouten en al.

**Gemeten.** Op de machine waar dit gebouwd is: 1,4 + 6,5 + 1,3 + 5,5 seconden, met het model
al in de cache. De eerste keer op een lege machine kost het de 460 MB download erbij.

**Waarom het niet perfect hoeft.** De zin is met espeak-ng gemaakt, dus niemands stem, en
whisper verstaat hem niet woord voor woord. De proef kijkt of genoeg ankerwoorden terugkomen
in plaats van of de zin klopt; een test die perfectie eist zou afgaan op een machine die het
prima doet.

**Ook.** De uitkomst gaat mee in de zip van **Melding opslaan**, en `melding.txt` opent er nu
mee. Een melding van een machine die de proef nooit gedraaid heeft zegt dat ook, want dat is
het eerste wat je terug zou vragen.

**Build.** One button that runs ten seconds of built-in audio through the whole chain:
audio out of a file, the speech model, following a face, a rendered clip with a caption on
it. It says which of the four worked and how long each took, and it leaves the result on
screen to look at.

**Why.** Today a church finds out that FFmpeg is missing, or the model never downloaded, or
the card cannot be used, twenty minutes into its first real service. Everything in the
readiness panel is a check on whether a file exists; none of it is a check on whether the
work actually runs. This is also the first thing to ask for in a support mail, and the
answer fits in the report `Melding opslaan` already makes.

**Done.** A fresh install with no speech model downloaded presses one button and, within a
few minutes, either has a clip on screen or a line naming which step failed and why. The
outcome rides along in the diagnostic zip.

### Step 22 · Never stand still without saying why — gedaan (0.9.0)
Serves (onboarding)

**Wat er staat.** De eerste keer uitschrijven haalt het spraakmodel op, en dat staat nu in de
balk: *Spraakmodel wordt opgehaald · 147 van 148 MB · dit gebeurt één keer*. Ongeveer één
melding per megabyte, dus leesbaar in plaats van flikkerend. `WhisperModel(size)` haalde het
zelf op en zei niets; het gebeurt nu in `fetch_model`, waar het geteld kan worden. FFmpeg in
het zwarte venster zegt nu ook hoeveel van hoeveel.

**Drie dingen die dit lastiger maakten dan het klinkt.** De download van faster-whisper zet
de voortgangsbalk hard uit, dus die weg is dicht. Sinds hf-xet worden de bestanden ergens
anders in elkaar gezet en blijft de cachemap leeg tot het eind, dus bytes op schijf tellen
geeft vijf megabyte van vierhonderd en dan een sprong. En Hugging Face maakt twee balken over
dezelfde download, één voor de lijn en één voor het weer in elkaar zetten, dus optellen telt
elke megabyte dubbel. Het wordt nu geteld in onze eigen subclass, de verste van de twee telt,
en tqdm's eigen teller wordt niet gelezen omdat die stilvalt zodra de balk uit staat, wat
deze app zelf veroorzaakt in `quiet_hub_notices`.

**Gaat er iets mis, dan verandert er niets.** Elke fout in dit pad geeft de maat ongewijzigd
terug en laat `WhisperModel` het zelf ophalen, stil, zoals het altijd ging.

**Build.** The speech model is 460 MB, downloaded on the first transcription. While that
happens the panel says "Het spraakmodel wordt geladen" and the bar sits at four percent, for
as long as the church's line takes. Report the download itself: megabytes, a moving bar, and
a sentence saying this happens once. The same for FFmpeg in the launcher, which already has
a percentage in the black window and nothing in the browser.

**Why.** It is the only place in the app where nothing moves and nothing is said, and it
falls on the very first run, which is the run that decides whether there is a second.

**Done.** A first transcription on a machine with an empty cache shows megabytes arriving
and the words "dit gebeurt één keer". Nobody has to look at the black window to know the
app is alive.

### Step 23 · Refuse the job you cannot finish
Serves (2)

**Build.** Estimate what a job needs before starting it, from the size of the recording, and
refuse with a number when the disk cannot hold it. Point at **Ruimte vrijmaken** and say how
much is standing there.

**Why.** A render that fills the disk at eighty percent is the worst failure this app has:
it costs the work already done, and it leaves nothing free to clean up with. The readiness
panel warns below three gigabytes, which is a different thing from knowing that this
particular service will not fit.

**Done.** A disk with too little room says so before the first byte is written, with the
number it needs and the number it has. Staged on purpose in a test.

### Step 24 · Let the first start be one start
Serves (onboarding)

**Build.** On a machine without Python, `start.bat` installs it and then asks the volunteer
to close the window and run the file again. Ship an embeddable Python in the release zip
instead, so the first double-click is the only double-click. Nothing about the installer
question changes; this works inside the zip that already exists.

**Why.** That second action is where a willing church stops, and it is the failure you will
never hear about, because it happens before there is anything to report.

**Done.** A Windows machine with no Python runs the app from one double-click, and the
winget branch is gone from `start.bat`.

### Step 25 · Say "op" when it is op
Serves (support)

**Build.** A rate limit and an empty account both arrive as a 429. The first is worth
waiting out and the app does, with growing pauses. The second never comes good, and the app
waits anyway and then reports a limit. Tell them apart, and say the one that means money.
While there: one heavy job at a time per machine, so two browser tabs cannot make each other
slow for no visible reason.

**Why.** "Het zegt dat het vol is" is what a church reports when the answer is that somebody
has to put twenty euro on an account. Weeks of a pilot can go that way.

**Done.** An account with no credit says so in one sentence naming the console page, without
retrying first. Starting a second heavy job says what is already running.

### What this phase is measured on

Not a feature list. Three things, at the end of the pilot:

- every church got to a first clip without a phone call;
- every stop the app made was one somebody could read;
- `logs/runs.jsonl` came back from more than one church.

---

## Deliberately deferred

Multi-platform publishing, scheduling, an asset library, analytics, thumbnail generation, output
in other languages, multi-user accounts, and anything that needs a server.

All of it gets easier once four numbers are good: how long a service takes end to end, how many of
the top five proposals get posted, how long a review takes, and how the clip holds up next to one
a designer made. Until those are good, more features make a bigger tool, not a better one.
