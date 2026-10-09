"""The audio reaches the speech model as samples, never as a file it opens itself.

faster-whisper opens files through PyAV, and PyAV 19 dropped an argument faster-whisper 1.2
still passes: on a church's Mac every transcription ended in a TypeError before one word.
"""

import struct
import wave

import numpy as np
import pytest

from backend import transcription


def a_wav(path, samples, rate=16000, channels=1):
    with wave.open(str(path), "wb") as out:
        out.setnchannels(channels)
        out.setsampwidth(2)
        out.setframerate(rate)
        out.writeframes(struct.pack(f"<{len(samples)}h", *samples))
    return path


def test_the_wav_comes_back_as_the_samples_whisper_wants(tmp_path):
    heard = transcription.read_wav(a_wav(tmp_path / "a.wav", [0, 16384, -32768, 32767]))
    assert heard.dtype == np.float32
    assert heard.tolist() == pytest.approx([0.0, 0.5, -1.0, 32767 / 32768])


def test_a_wav_in_another_shape_is_refused_out_loud(tmp_path):
    with pytest.raises(RuntimeError):
        transcription.read_wav(a_wav(tmp_path / "b.wav", [0, 0], rate=44100))


def test_faster_whisper_is_handed_samples_and_not_a_path(tmp_path, monkeypatch):
    import faster_whisper

    given = []

    class Pipeline:
        def __init__(self, model):
            pass

        def transcribe(self, audio, **kwargs):
            given.append(audio)
            return iter([]), None

    def extract(source, wav_path, *args, **kwargs):
        a_wav(wav_path, [0] * 1600)

    monkeypatch.setattr(faster_whisper, "BatchedInferencePipeline", Pipeline)
    monkeypatch.setattr(transcription, "engine", lambda: "faster-whisper")
    monkeypatch.setattr(transcription, "get_model", lambda *a, **k: object())
    monkeypatch.setattr(transcription, "extract_audio", extract)
    transcription.transcribe(tmp_path / "bron.mp4", tmp_path / "werk", duration=0.1,
                             how=transcription.Listening("tiny", 1, "scan"))
    assert given and isinstance(given[0], np.ndarray)
