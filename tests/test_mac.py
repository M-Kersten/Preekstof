"""Listening on the Mac's graphics chip.

None of this can be run for real here: mlx only installs on Apple Silicon. What is tested is
everything around the library, with mlx-whisper replaced by a stub that answers the way the
real one does. Whether it is quicker, and how much, is a question only a Mac can answer; see
tools/speechbench.py.
"""

import sys
import types
import wave
from pathlib import Path

import numpy as np
import pytest

from backend import mac, transcription
from backend.jobs import Cancelled

SR = mac.SAMPLE_RATE


def a_wav(path, seconds: float, quiet_at: list[float] | None = None):
    """Noise for `seconds`, with half a second of near-silence at each of `quiet_at`."""
    audio = (np.random.default_rng(4).normal(0, 0.25, int(seconds * SR))).astype(np.float32)
    for at in quiet_at or []:
        audio[int(at * SR):int((at + 0.5) * SR)] = 0.0
    raw = (np.clip(audio, -1, 1) * 32767).astype(np.int16)
    with wave.open(str(path), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(SR)
        out.writeframes(raw.tobytes())
    return audio


# --- whether to use it at all -----------------------------------------------------


def test_a_machine_that_is_not_a_mac_cannot(monkeypatch):
    monkeypatch.setattr(mac.platform, "system", lambda: "Linux")
    assert not mac.apple_silicon()


def test_an_intel_mac_cannot_either(monkeypatch):
    monkeypatch.setattr(mac.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(mac.platform, "machine", lambda: "x86_64")
    assert not mac.apple_silicon()


def test_an_apple_laptop_can(monkeypatch):
    monkeypatch.setattr(mac.platform, "system", lambda: "Darwin")
    monkeypatch.setattr(mac.platform, "machine", lambda: "arm64")
    assert mac.apple_silicon()


def test_the_right_machine_without_the_library_still_cannot(monkeypatch):
    monkeypatch.setattr(mac, "apple_silicon", lambda: True)
    monkeypatch.setattr(mac, "installed", lambda: False)
    assert not mac.possible()


def test_the_processor_is_what_everything_else_gets(monkeypatch):
    monkeypatch.setattr(mac, "possible", lambda: False)
    monkeypatch.setattr(transcription, "BACKEND", "auto")
    assert transcription.engine() == transcription.CTRANSLATE


def test_an_apple_laptop_that_can_is_used_without_being_asked(monkeypatch):
    monkeypatch.setattr(mac, "possible", lambda: True)
    monkeypatch.setattr(transcription, "BACKEND", "auto")
    assert transcription.engine() == transcription.MLX


def test_saying_which_one_settles_it(monkeypatch):
    """So the two can be compared on the same machine, and so a bad day has a way back."""
    monkeypatch.setattr(mac, "possible", lambda: True)
    monkeypatch.setattr(transcription, "BACKEND", "faster-whisper")
    assert transcription.engine() == transcription.CTRANSLATE
    monkeypatch.setattr(mac, "possible", lambda: False)
    monkeypatch.setattr(transcription, "BACKEND", "mlx")
    assert transcription.engine() == transcription.MLX


def test_the_model_names_the_church_already_set_still_mean_something():
    for name in ("tiny", "base", "small", "medium", "large-v3"):
        assert mac.repo_for(name).startswith("mlx-community/")
    assert mac.repo_for("somebody/their-own") == "somebody/their-own"
    assert mac.repo_for("nonsense") == mac.REPOS["small"], "fall back rather than 404"


def test_every_model_the_app_offers_has_a_converted_one():
    """WHISPER_MODEL is documented with these five; none may quietly have no Mac version."""
    assert set(mac.REPOS) == {"tiny", "base", "small", "medium", "large-v3"}


# --- cutting the audio into pieces ------------------------------------------------


def test_short_audio_is_handed_over_in_one_go(tmp_path):
    audio = a_wav(tmp_path / "a.wav", 20.0)
    assert mac.seams(audio, every=300.0) == []
    assert len(mac.pieces(audio, every=300.0)) == 1


def test_a_long_service_is_cut_into_pieces(tmp_path):
    audio = a_wav(tmp_path / "a.wav", 640.0)
    parts = mac.pieces(audio, every=300.0)
    assert len(parts) == 3
    assert parts[0][0] == 0.0
    assert [round(at) for at, _ in parts] == sorted(round(at) for at, _ in parts)


def test_the_pieces_together_are_the_whole_recording(tmp_path):
    audio = a_wav(tmp_path / "a.wav", 700.0)
    parts = mac.pieces(audio, every=300.0)
    assert sum(len(part) for _at, part in parts) == len(audio)
    rebuilt = np.concatenate([part for _at, part in parts])
    assert np.array_equal(rebuilt, audio), "not a sample may go missing between pieces"


def test_every_piece_starts_where_the_one_before_it_ended(tmp_path):
    audio = a_wav(tmp_path / "a.wav", 700.0)
    parts = mac.pieces(audio, every=300.0)
    for (at, part), (next_at, _) in zip(parts, parts[1:]):
        assert next_at == pytest.approx(at + len(part) / SR, abs=0.01)


def test_the_cut_goes_looking_for_a_silence(tmp_path):
    """A piece boundary in the middle of a word costs that word."""
    audio = a_wav(tmp_path / "a.wav", 640.0, quiet_at=[292.0])
    cut = mac.seams(audio, every=300.0)[0] / SR
    assert 292.0 <= cut <= 292.6, f"cut at {cut:.1f}s, not in the silence at 292s"


def test_a_silence_too_far_away_is_not_chased(tmp_path):
    audio = a_wav(tmp_path / "a.wav", 640.0, quiet_at=[100.0])
    cut = mac.seams(audio, every=300.0)[0] / SR
    assert abs(cut - 300.0) <= mac.LOOK, "it stays near where the piece should end"


def test_audio_of_nothing_does_not_fall_over():
    assert mac.seams(np.zeros(0, np.float32)) == []
    assert mac.loudness(np.zeros(0, np.float32)).size == 1


# --- what comes back --------------------------------------------------------------


class FakeMlx(types.ModuleType):
    """mlx-whisper as it answers on a Mac: one dict per call, in the piece's own seconds."""

    asked: list[dict] = []
    answer: list[dict] = []

    def transcribe(self, audio, **kwargs):
        FakeMlx.asked.append({"samples": len(audio), "dtype": audio.dtype,
                              "loudest": float(np.abs(audio).max()) if len(audio) else 0.0,
                              **kwargs})
        return {"text": "x", "language": "nl", "segments": list(FakeMlx.answer)}


@pytest.fixture
def fake_mlx(monkeypatch):
    module = FakeMlx("mlx_whisper")
    FakeMlx.asked = []
    FakeMlx.answer = [{
        "start": 1.0, "end": 3.0, "text": " Genade zij u",
        "words": [{"word": " Genade", "start": 1.0, "end": 2.0, "probability": 0.9},
                  {"word": " zij", "start": 2.0, "end": 2.5, "probability": 0.9},
                  {"word": " u", "start": 2.5, "end": 3.0, "probability": 0.9}],
    }]
    monkeypatch.setitem(sys.modules, "mlx_whisper", module)
    return FakeMlx


def test_what_it_hears_looks_like_what_the_other_engine_hears(tmp_path, fake_mlx):
    a_wav(tmp_path / "a.wav", 30.0)
    said = list(mac.listen(tmp_path / "a.wav", "small", "kerkdienst"))
    assert len(said) == 1
    assert (said[0].start, said[0].end, said[0].text) == (1.0, 3.0, " Genade zij u")
    assert [w.word for w in said[0].words] == [" Genade", " zij", " u"]
    assert said[0].words[0].start == 1.0


def test_timings_from_a_later_piece_are_in_the_clip_s_own_seconds(tmp_path, fake_mlx):
    a_wav(tmp_path / "a.wav", 640.0, quiet_at=[300.0])
    said = list(mac.listen(tmp_path / "a.wav", "small", None))
    assert len(said) == 3, "three pieces, one sentence each from the stub"
    starts = [round(s.start) for s in said]
    assert starts == sorted(starts) and starts[0] == 1
    assert starts[1] > 290, "the second piece does not start counting from zero again"
    assert said[1].words[0].start == pytest.approx(said[1].start)


def test_the_audio_arrives_in_the_shape_the_model_expects(tmp_path, fake_mlx):
    """Whole numbers here would decode to noise, and nothing would say so."""
    a_wav(tmp_path / "a.wav", 20.0)
    list(mac.listen(tmp_path / "a.wav", "small", None))
    assert fake_mlx.asked[0]["dtype"] == np.float32
    assert 0.0 < fake_mlx.asked[0]["loudest"] <= 1.0
    assert fake_mlx.asked[0]["samples"] == 20 * SR


def test_the_pieces_handed_over_are_the_whole_recording(tmp_path, fake_mlx):
    a_wav(tmp_path / "a.wav", 700.0, quiet_at=[300.0, 600.0])
    list(mac.listen(tmp_path / "a.wav", "small", None))
    assert sum(a["samples"] for a in fake_mlx.asked) == 700 * SR
    assert len(fake_mlx.asked) == 3


def test_the_church_word_list_and_the_language_reach_the_model(tmp_path, fake_mlx):
    a_wav(tmp_path / "a.wav", 20.0)
    list(mac.listen(tmp_path / "a.wav", "medium", "gemeente, genade, Opwekking"))
    assert fake_mlx.asked[0]["initial_prompt"] == "gemeente, genade, Opwekking"
    assert fake_mlx.asked[0]["language"] == "nl"
    assert fake_mlx.asked[0]["word_timestamps"] is True
    assert fake_mlx.asked[0]["path_or_hf_repo"] == mac.REPOS["medium"]


def test_a_piece_is_only_started_when_the_one_before_it_has_been_read(tmp_path, fake_mlx):
    """What makes Stoppen arrive within a piece instead of at the end of the service."""
    a_wav(tmp_path / "a.wav", 640.0)
    said = mac.listen(tmp_path / "a.wav", "small", None)
    assert fake_mlx.asked == [], "nothing decoded before anybody asked"
    next(said)
    assert len(fake_mlx.asked) == 1, "and then only the first piece"


def test_stopping_stops_between_pieces(tmp_path, fake_mlx):
    a_wav(tmp_path / "a.wav", 640.0)
    calls = {"n": 0}

    def stop():
        calls["n"] += 1
        if calls["n"] > 1:
            raise Cancelled

    with pytest.raises(Cancelled):
        list(mac.listen(tmp_path / "a.wav", "small", None, stop))
    assert len(fake_mlx.asked) == 1, "it stopped after the first piece, not after the last"


def test_a_piece_with_nothing_in_it_is_no_reason_to_fall_over(tmp_path, fake_mlx):
    a_wav(tmp_path / "a.wav", 20.0)
    fake_mlx.answer = [{"start": 0.0, "end": 2.0, "text": " hm", "words": None}]
    said = list(mac.listen(tmp_path / "a.wav", "small", None))
    assert said[0].words == []


def test_audio_that_is_not_what_we_wrote_is_refused(tmp_path):
    path = tmp_path / "stereo.wav"
    with wave.open(str(path), "wb") as out:
        out.setnchannels(2)
        out.setsampwidth(2)
        out.setframerate(SR)
        out.writeframes(b"\0" * 400)
    with pytest.raises(ValueError):
        mac.read_wav(path)


# --- the whole way through --------------------------------------------------------


def test_a_transcription_on_the_graphics_chip_comes_out_the_same_shape(tmp_path, fake_mlx, monkeypatch):
    """Everything above the engine: progress, the partial file, the caption chunking."""
    monkeypatch.setattr(transcription, "BACKEND", "mlx")
    monkeypatch.setattr(transcription, "initial_prompt", lambda: "kerkdienst")
    work = tmp_path / "work"

    def fake_extract(source, wav, should_stop=None, on_progress=None, duration=None, start=0.0):
        wav.parent.mkdir(parents=True, exist_ok=True)
        a_wav(wav, 640.0, quiet_at=[300.0])

    monkeypatch.setattr(transcription, "extract_audio", fake_extract)
    seen: list[tuple[float, str]] = []
    out = transcription.transcribe(tmp_path / "in.mp4", work, duration=640.0,
                                   on_progress=lambda f, p: seen.append((f, p)))

    assert [s.text for s in out.segments] == ["Genade zij u"] * 3, "three pieces, chunked and trimmed"
    assert [round(s.start) for s in out.segments] == sorted(round(s.start) for s in out.segments)
    assert [p for _f, p in seen][0] == transcription.AUDIO
    moved = [f for f, p in seen if p == transcription.TEXT]
    assert moved == sorted(moved) and len(moved) > 1, "the bar moves while the pieces come in"
    assert not (work / transcription.PARTIAL_FILE).exists(), "cleaned up when it finished"


def test_a_run_that_stops_halfway_keeps_what_it_heard(tmp_path, fake_mlx, monkeypatch):
    monkeypatch.setattr(transcription, "BACKEND", "mlx")
    monkeypatch.setattr(transcription, "initial_prompt", lambda: "")
    monkeypatch.setattr(transcription, "SAVE_EVERY", 1.0)
    work = tmp_path / "work"

    def fake_extract(source, wav, should_stop=None, on_progress=None, duration=None, start=0.0):
        wav.parent.mkdir(parents=True, exist_ok=True)
        a_wav(wav, 640.0, quiet_at=[300.0])

    monkeypatch.setattr(transcription, "extract_audio", fake_extract)
    heard = {"n": 0}

    def stop():
        heard["n"] += 1
        if heard["n"] > 3:
            raise Cancelled

    with pytest.raises(Cancelled):
        transcription.transcribe(tmp_path / "in.mp4", work, duration=640.0, should_stop=stop)
    done_to, words, _fallback = transcription.load_partial(work)
    assert done_to > 0 and words, "the next attempt carries on instead of starting over"


# --- what the app says about it ---------------------------------------------------


def test_the_readiness_check_names_the_chip_it_runs_on(monkeypatch):
    from backend import health

    monkeypatch.setattr(transcription, "BACKEND", "mlx")
    monkeypatch.setattr(mac, "apple_silicon", lambda: True)
    assert "grafische chip" in health._whisper().detail


def test_a_mac_that_could_be_quicker_is_told_so(monkeypatch):
    """The whole point of the setting is lost if nobody knows it exists."""
    from backend import health

    monkeypatch.setattr(transcription, "BACKEND", "faster-whisper")
    monkeypatch.setattr(mac, "apple_silicon", lambda: True)
    monkeypatch.setattr(health.Path, "home", lambda: Path("/definitely/not/here"))
    detail = health._whisper().detail
    assert "requirements-mac.txt" in detail or "gedownload" in detail


def test_nobody_else_is_bothered_with_advice_they_cannot_use(monkeypatch):
    from backend import health

    monkeypatch.setattr(transcription, "BACKEND", "faster-whisper")
    monkeypatch.setattr(mac, "apple_silicon", lambda: False)
    assert "requirements-mac.txt" not in health._whisper().detail
