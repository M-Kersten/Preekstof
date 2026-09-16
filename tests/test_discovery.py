"""Windowing, boundary snapping, scoring and dedupe: how candidates get ranked."""

import pytest

from backend.discovery import (COLD_PENALTY, MAX_CLIP, MIN_CLIP, OVERLAP_DUPLICATE, PASSAGE_LEAD,
                               PASSAGE_OVERLAP, PASSAGE_SECONDS, PREFERRED, SHORTLIST_RANGE,
                               LlmCandidate, Window, build_windows, cold_open, dedupe_and_rank,
                               estimate, format_window, opening_line, overlap_fraction, score, snap,
                               wanted_from, window_request)
from backend.models import ClipCandidate, Segment, Transcript

# The splitting mechanics are tested at a size that actually splits. In a real run a sermon
# almost always arrives as one passage, which is the point of PASSAGE_SECONDS being large.
SMALL = {"length": 240.0, "overlap": 60.0, "lead": 120.0}


def talk(count: int, step: float = 4.0) -> list[Segment]:
    """A transcript of `count` sentences, `step` seconds apart."""
    return [Segment(start=i * step, end=i * step + step - 0.4, text=f"Zin nummer {i} van de dienst.")
            for i in range(count)]


def test_no_segments_gives_no_windows():
    assert build_windows([]) == []
    assert build_windows([Segment(start=0, end=1, text="   ")]) == []


def test_windows_cover_every_segment():
    segments = talk(200)
    windows = build_windows(segments, **SMALL)
    covered = {id(s) for w in windows for s in w.segments}
    assert len(covered) == len(segments)


def test_windows_are_about_the_configured_length():
    windows = build_windows(talk(200), **SMALL)
    assert all(w.end - w.start <= SMALL["length"] + 10 for w in windows)
    assert len(windows) > 1


def test_windows_overlap_so_a_moment_on_a_seam_is_still_seen():
    windows = build_windows(talk(200), **SMALL)
    for before, after in zip(windows, windows[1:]):
        assert after.start < before.end, "consecutive windows must share some transcript"
        assert before.end - after.start <= SMALL["overlap"] + 10


def test_windowing_always_makes_progress():
    """A pathological transcript must not spin forever or repeat a window."""
    segments = [Segment(start=0.0, end=600.0, text="Een hele lange zin."),
                Segment(start=1.0, end=2.0, text="Kort."),
                Segment(start=1.5, end=900.0, text="Nog een lange.")]
    windows = build_windows(segments, **SMALL)
    assert windows
    assert len({(w.start, w.end) for w in windows}) == len(windows)


def test_windows_are_numbered_in_order():
    windows = build_windows(talk(120), **SMALL)
    assert [w.index for w in windows] == list(range(len(windows)))


def test_a_whole_sermon_goes_in_one_passage():
    """Forty minutes of preaching is one call, not ten."""
    assert PASSAGE_SECONDS >= 30 * 60, "a passage has to be able to hold a sermon"
    sermon = talk(int(35 * 60 / 4.0))  # thirty-five minutes of sentences
    assert len(build_windows(sermon)) == 1


def test_a_sermon_too_long_for_one_passage_is_split_and_overlaps():
    hour_and_a_half = talk(int(90 * 60 / 4.0))
    passages = build_windows(hour_and_a_half)
    assert len(passages) > 1
    for before, after in zip(passages, passages[1:]):
        assert after.start < before.end
        assert before.end - after.start <= PASSAGE_OVERLAP + 10


def test_snap_moves_boundaries_onto_sentences():
    window = build_windows(talk(40), **SMALL)[0]
    first, second = window.segments[2], window.segments[6]
    proposal = LlmCandidate(start=first.start + 1.5, end=second.end - 1.2, title="t", summary="s",
                            reason="r", confidence=0.8)
    assert snap(proposal, window) == (round(first.start, 2), round(second.end, 2))


def test_snap_leaves_a_boundary_alone_when_no_sentence_is_near():
    """Sentences 30 s apart: a boundary in the middle of one has nothing to snap to."""
    window = build_windows(talk(6, step=30.0), **SMALL)[0]
    proposal = LlmCandidate(start=15.5, end=101.3, title="t", summary="s", reason="r", confidence=0.8)
    start, end = snap(proposal, window)
    assert (start, end) == (15.5, 101.3)


def test_snap_stays_inside_the_window():
    window = build_windows(talk(40), **SMALL)[0]
    proposal = LlmCandidate(start=-500, end=99999, title="t", summary="s", reason="r", confidence=0.5)
    start, end = snap(proposal, window)
    assert window.start <= start <= end <= window.end


def candidate(**kwargs) -> LlmCandidate:
    base = dict(start=0.0, end=45.0, title="t", summary="s", reason="r", confidence=0.8)
    return LlmCandidate(**{**base, **kwargs})


def test_score_prefers_the_useful_length():
    good = score(candidate(), (PREFERRED[0] + PREFERRED[1]) / 2)
    short = score(candidate(), MIN_CLIP + 1)
    long = score(candidate(), MAX_CLIP - 1)
    assert good > short and good > long


def test_score_stays_in_range():
    for confidence in (0.0, 0.5, 1.0, 2.0, -1.0):
        for duration in (5, 20, 45, 90, 200):
            assert -0.2 <= score(candidate(confidence=confidence), duration) <= 1.1


def test_confidence_still_decides_between_equal_lengths():
    assert score(candidate(confidence=0.9), 45) > score(candidate(confidence=0.4), 45)


def clip(start: float, end: float, score_: float = 0.8, id_: str = "") -> ClipCandidate:
    return ClipCandidate(id=id_, start=start, end=end, title="t", summary="s", reason="r",
                         confidence=score_, score=score_)


def test_overlap_fraction_is_relative_to_the_shorter_one():
    assert overlap_fraction(clip(0, 100), clip(0, 10)) == pytest.approx(1.0)
    assert overlap_fraction(clip(0, 10), clip(20, 30)) == 0.0
    assert overlap_fraction(clip(0, 20), clip(10, 30)) == pytest.approx(0.5)


def test_dedupe_keeps_the_best_of_an_overlapping_pair():
    kept = dedupe_and_rank([clip(0, 40, 0.5), clip(2, 42, 0.9)])
    assert len(kept) == 1
    assert kept[0].start == 2 and kept[0].score == 0.9


def test_dedupe_keeps_the_loser_as_an_alternative_boundary():
    kept = dedupe_and_rank([clip(0, 40, 0.5), clip(2, 42, 0.9)])
    assert [(b.start, b.end) for b in kept[0].alternateBoundaries] == [(0, 40)]


def test_dedupe_leaves_separate_moments_alone():
    kept = dedupe_and_rank([clip(0, 40, 0.9), clip(200, 240, 0.7)])
    assert len(kept) == 2


def test_dedupe_ranks_best_first_and_numbers_them():
    kept = dedupe_and_rank([clip(0, 40, 0.4), clip(200, 240, 0.9), clip(400, 440, 0.6)])
    assert [c.score for c in kept] == [0.9, 0.6, 0.4]
    assert [c.id for c in kept] == ["candidate-01", "candidate-02", "candidate-03"]


def test_dedupe_of_nothing_is_nothing():
    assert dedupe_and_rank([]) == []


def test_an_identical_duplicate_adds_no_alternative():
    kept = dedupe_and_rank([clip(0, 40, 0.9), clip(0, 40, 0.8)])
    assert len(kept) == 1 and kept[0].alternateBoundaries == []


def test_overlap_threshold_is_the_line_between_one_moment_and_two():
    share = 100 * OVERLAP_DUPLICATE
    under = dedupe_and_rank([clip(0, 100, 0.9), clip(100 - share + 10, 200 - share + 10, 0.8)])
    over = dedupe_and_rank([clip(0, 100, 0.9), clip(100 - share - 10, 200 - share - 10, 0.8)])
    assert len(under) == 2, "a small overlap is two moments"
    assert len(over) == 1, "a large overlap is one moment proposed twice"


def test_a_candidate_inside_another_is_the_same_moment():
    assert len(dedupe_and_rank([clip(0, 100, 0.9), clip(20, 60, 0.8)])) == 1


def test_estimate_grows_with_the_transcript():
    small = estimate(Transcript(language="nl", segments=talk(50)))
    large = estimate(Transcript(language="nl", segments=talk(500)))
    assert large["windows"] >= small["windows"]
    assert large["tokens"] > small["tokens"]
    assert large["costEur"] >= small["costEur"]
    assert small["model"] and small["provider"]


def test_an_ordinary_service_is_a_single_call():
    """It used to be sixteen calls and a second round on top of them."""
    service = estimate(Transcript(language="nl", segments=talk(int(45 * 60 / 4.0))))
    assert service["windows"] == 1


def test_estimate_of_an_empty_transcript_costs_nothing():
    empty = estimate(Transcript(language="nl", segments=[]))
    assert empty["windows"] == 0 and empty["costEur"] == 0.0


def test_estimate_reports_the_minutes_that_stay_home():
    assert estimate(Transcript(language="nl", segments=talk(50)))["skippedMinutes"] >= 0


# --- what one passage is asked for --------------------------------------------


def passage(minutes: float, index: int = 0) -> Window:
    segments = talk(int(minutes * 60 / 4.0))
    return Window(index=index, start=segments[0].start, end=segments[-1].end, segments=segments)


def test_a_single_passage_is_asked_for_the_shortlist_itself():
    alone = passage(35)
    assert wanted_from(alone, alone=True) == SHORTLIST_RANGE[1]
    text = window_request(alone, "", wanted_from(alone, alone=True), alone=True)
    assert "hele preek" in text
    assert str(SHORTLIST_RANGE[0]) in text and str(SHORTLIST_RANGE[1]) in text


def test_a_split_sermon_proposes_more_per_passage_because_a_round_follows():
    piece = passage(35)
    assert wanted_from(piece, alone=False) > 2
    text = window_request(piece, "", wanted_from(piece, alone=False), alone=False)
    assert "Fragment 1" in text
    assert "hele preek" not in text


def test_a_short_passage_is_still_asked_for_at_least_two():
    assert wanted_from(passage(3), alone=False) == 2


def test_the_prompt_no_longer_caps_every_passage_at_two():
    from backend.discovery import SYSTEM_PROMPT

    assert "hooguit 2" not in SYSTEM_PROMPT, "the count belongs in the request, not the standing instructions"
    assert len(SYSTEM_PROMPT) < 2100


# --- fewer, longer, and starting somewhere a stranger can follow ---------------


def test_a_short_proposal_is_dropped_now_that_clips_are_longer():
    """Under half a minute there is no room to introduce anything."""
    assert MIN_CLIP >= 25
    assert PREFERRED[0] >= 45


def test_the_preferred_length_is_rewarded_and_the_extremes_are_not():
    c = candidate(confidence=0.8)
    assert score(c, 60.0) > score(c, 26.0)
    assert score(c, 60.0) > score(c, 150.0)


def test_a_clip_that_opens_on_a_back_reference_scores_lower():
    c = candidate(confidence=0.8)
    warm = score(c, 60.0, "God vraagt niet dat je perfect bent.")
    cold = score(c, 60.0, "Dat is precies wat ik bedoelde.")
    assert cold < warm
    assert warm - cold == pytest.approx(COLD_PENALTY, abs=1e-6)


@pytest.mark.parametrize("line", [
    "Dat is precies waar het om gaat.",
    "Daarom moeten we vandaag beginnen.",
    "Dus dat is wat rust betekent.",
    "Hij zei toen iets heel bijzonders.",
    "Zoals ik net al zei, God kent je.",
    "En dus komt het hierop neer.",
])
def test_these_openings_leave_the_viewer_in_the_dark(line):
    assert cold_open(line)


@pytest.mark.parametrize("line", [
    "God vraagt niet dat je perfect bent.",
    "Rust is geen zwakte.",
    "Wat doe je met een week die te vol zit?",
    "Het gaat vandaag over vertrouwen.",
    "En God zei tegen Elia: ga naar buiten.",
    "Ik wil je iets vertellen over mijn vader.",
])
def test_these_openings_stand_on_their_own(line):
    assert not cold_open(line)


def test_the_opening_line_is_the_sentence_the_clip_starts_on():
    segments = talk(10, step=10.0)
    assert opening_line(segments, 30.0) == segments[3].text
    # A start halfway through a sentence still opens on that sentence.
    assert opening_line(segments, 34.0) == segments[3].text
    assert opening_line(segments, 9999.0) == ""


def test_a_window_carries_the_minutes_before_it():
    windows = build_windows(talk(200), **SMALL)
    assert windows[0].lead == [], "nothing came before the first window"
    later = windows[2]
    assert later.lead, "a later window knows what led up to it"
    assert all(s.end <= later.start + 0.01 for s in later.lead)
    assert later.start - later.lead[0].start <= SMALL["lead"] + 10


def test_a_second_passage_still_gets_its_run_up():
    passages = build_windows(talk(int(90 * 60 / 4.0)))
    assert passages[0].lead == []
    assert passages[1].lead
    assert passages[1].start - passages[1].lead[0].start <= PASSAGE_LEAD + 10


def test_the_run_up_is_shown_as_context_and_not_as_a_place_to_choose_from():
    windows = build_windows(talk(200), **SMALL)
    text = format_window(windows[2])
    assert "Wat hieraan voorafging" in text
    assert "kies hier niets uit" in text
    for segment in windows[2].segments:
        assert segment.text in text


def test_a_moment_on_a_seam_fits_whole_inside_one_window():
    """Sparse transcripts used to leave a seam of a second or two between windows."""
    segments = [Segment(start=i * 70.0, end=i * 70.0 + 8.0, text=f"Zin {i} van de preek.")
                for i in range(30)]
    windows = build_windows(segments, **SMALL)
    for before, after in zip(windows, windows[1:]):
        assert before.end - after.start >= SMALL["overlap"] - 1
