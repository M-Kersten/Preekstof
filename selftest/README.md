# The ten seconds the app checks itself with

`proef.opus` is one Dutch sentence, spoken by a machine:

> Dit is een proef van Preekstof. Als je deze zin terugleest in de app, dan werkt het
> uitschrijven op deze computer.

Twenty-two kilobytes. It is the only thing the self-test needs that has to travel with the
app, because everything else it uses it makes on the spot with FFmpeg.

## Why a machine voice

A recording of a person would be somebody's voice, which is somebody's to give, and it would
have to be licensed and kept. This was made with espeak-ng, which produces nobody's voice:

```bash
espeak-ng -v nl -s 140 -w proef.wav "Dit is een proef van Preekstof. Als je deze zin \
terugleest in de app, dan werkt het uitschrijven op deze computer."
ffmpeg -i proef.wav -c:a libopus -b:a 24k -ar 16000 -ac 1 proef.opus
```

It is deliberately not clean speech. A synthetic voice is harder than a preacher on a good
microphone, so a machine that reads this back has room to spare on a real service.

## What it is allowed to get wrong

Whisper does not return it word for word. On the machine this was made on it came back as
"Dit is een proefmanpreekstof. Als je deze zin terughleest in de aap, dan merkt het
uitschrijven op deze computer." That is the expected quality, and the self-test is built
around it: it looks for a handful of words that survive and counts how many came back,
rather than comparing the whole sentence. A test that demands perfection here would fail on
a working machine, which is worse than no test.
