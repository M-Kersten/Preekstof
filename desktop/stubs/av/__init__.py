"""Stands in for PyAV inside the desktop app.

faster-whisper imports PyAV when it is loaded, and uses it only to open audio files itself.
Preekstof never lets it: the audio is read by backend/transcription.read_wav and handed over
as samples. The real PyAV is left out of the desktop app on purpose, because its wheel
carries an FFmpeg built with x264 and x265 (GPL), linked into the app's own process (NOTICE).
The FFmpeg the app does carry runs as a separate program.

If anything ever does reach for it, this says so plainly rather than half-working.
"""


def open(*_args, **_kwargs):  # noqa: A001  the name faster-whisper calls
    raise RuntimeError("PyAV zit niet in de desktop-app; het geluid wordt door Preekstof zelf ingelezen.")
