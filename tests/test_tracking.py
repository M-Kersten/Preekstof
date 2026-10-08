"""The calm path: what makes the frame stand still, ease, catch up, and jump on a cut.

Nothing here decodes video or loads a model. Everything below is the arithmetic between a
list of sightings and a list of positions, which is where the feel of the movement lives
and where a wrong constant is invisible until someone watches a finished clip.
"""

import math

import pytest

from backend import tracking
from backend.models import CropWindow, Output, VideoInfo
from backend.tracking import (DEAD_ZONE, KEEP_IN, MAX_PAN, PATH_FPS, RESCUE_PAN, SAMPLE_FPS,
                              Sighting, Watch, again, anchors, choose, coverage, glide,
                              half_width, is_cut, prominence)
from backend.vision import Box

OUT = Output(width=1080, height=1920, fps=30)
WIDE = VideoInfo(width=1920, height=1080, duration=30.0, fps=25.0, videoCodec="h264",
                 hasAudio=True, audioCodec="aac", audioSampleRate=48000, audioChannels=2)


def held(x: float, count: int) -> list[float | None]:
    return [x] * count


# --- who to follow ----------------------------------------------------------------


def test_the_person_in_the_middle_wins_from_one_at_the_edge():
    middle = Box(x=960, y=400, w=90, h=120, score=0.8)
    edge = Box(x=120, y=400, w=90, h=120, score=0.8)
    assert choose([edge, middle], 1920, 1080) is middle


def test_a_bigger_box_wins_from_a_smaller_one_in_the_same_place():
    near = Box(x=900, y=400, w=140, h=190, score=0.7)
    far = Box(x=900, y=400, w=60, h=80, score=0.7)
    assert choose([far, near], 1920, 1080) is near


def test_prominence_falls_off_towards_the_edge():
    box = lambda x: Box(x=x, y=400, w=90, h=120, score=0.8)  # noqa: E731
    assert prominence(box(960), 1920, 1080) > prominence(box(500), 1920, 1080)
    assert prominence(box(500), 1920, 1080) > prominence(box(60), 1920, 1080)


def test_the_same_person_is_recognised_one_step_later():
    was = Box(x=900, y=400, w=90, h=120, score=0.8)
    moved = Box(x=960, y=400, w=90, h=120, score=0.8)
    other = Box(x=300, y=400, w=90, h=120, score=0.9)
    assert again([other, moved], was, 1920) is moved


def test_a_leap_across_the_room_is_somebody_else():
    was = Box(x=300, y=400, w=90, h=120, score=0.8)
    far = Box(x=1500, y=400, w=90, h=120, score=0.9)
    assert again([far], was, 1920) is None


def test_nobody_in_the_frame_is_nobody_to_follow():
    assert choose([], 1920, 1080) is None
    assert again([], Box(x=300, y=400, w=90, h=120, score=0.8), 1920) is None


def test_a_subject_goes_stale_after_a_few_seconds():
    watch = Watch(x=900.0, x_at=10.0)
    assert watch.fresh(10.0 + tracking.LOST_AFTER - 0.01)
    assert not watch.fresh(10.0 + tracking.LOST_AFTER + 0.01)


# --- cuts -------------------------------------------------------------------------


def test_a_quiet_clip_never_invents_a_cut():
    assert not is_cut(3.0, [2.0, 2.5, 3.0, 2.8])
    assert not is_cut(7.9, [1.0] * 12)  # below the floor, whatever the ratio says


def test_a_real_camera_change_is_a_cut():
    assert is_cut(20.4, [2.0, 2.5, 3.1, 2.2, 3.7])


def test_a_busy_clip_needs_more_before_it_counts():
    busy = [9.0, 10.0, 11.0, 9.5]
    assert not is_cut(20.0, busy)  # 2x the usual is not enough
    assert is_cut(30.0, busy)


def test_the_first_sample_has_nothing_to_compare_against():
    assert not is_cut(50.0, [])


# --- the path ---------------------------------------------------------------------


def test_a_speaker_who_stands_still_gives_a_frame_that_never_moves():
    path, jumps = glide(held(0.5, 40), [False] * 40, reach=0.25, start_at=0.5)
    assert jumps == []
    assert max(path) - min(path) == 0


def test_small_drift_inside_the_dead_zone_moves_nothing():
    reach = 0.25
    drift = DEAD_ZONE * reach * 2 * 0.8  # just inside
    path, _ = glide([0.5] * 5 + [0.5 + drift] * 35, [False] * 40, reach=reach, start_at=0.5)
    assert max(path) - min(path) == 0


def test_leaving_the_dead_zone_eases_the_frame_back():
    reach = 0.25
    target = 0.5 + DEAD_ZONE * reach * 2 * 2.0
    path, _ = glide([0.5] * 3 + [target] * 60, [False] * 63, reach=reach, start_at=0.5)
    assert path[0] == pytest.approx(0.5, abs=1e-6)
    # It stops chasing once the speaker is comfortably inside again, so it settles just
    # short of dead centre rather than hunting for it.
    assert abs(target - path[-1]) < DEAD_ZONE * reach * 2
    assert path[-1] > path[0] + DEAD_ZONE * reach * 2 * 0.5
    steps = [b - a for a, b in zip(path, path[1:])]
    assert all(s >= -1e-9 for s in steps), "an ease towards the right never goes left"
    assert max(steps) <= MAX_PAN * reach * 2 / PATH_FPS + 1e-9, "no faster than the speed limit"


def test_a_move_sets_off_slowly_and_comes_to_rest_slowly():
    reach = 0.25
    target = 0.5 + DEAD_ZONE * reach * 2 * 2.0
    path, _ = glide([0.5] * 3 + [target] * 60, [False] * 63, reach=reach, start_at=0.5)
    steps = [b - a for a, b in zip(path, path[1:])]
    moving = [s for s in steps if s > 1e-7]
    assert moving[0] < max(moving) / 4, "it gathers speed rather than starting at full tilt"
    assert moving[-1] < max(moving) / 4, "it settles rather than stopping dead"
    changes = [abs(b - a) * PATH_FPS * PATH_FPS for a, b in zip(steps, steps[1:])]
    assert max(changes) <= tracking.ACCEL * reach * 2 + 1e-6, "no jolt anywhere in the move"


def test_a_move_brings_the_speaker_back_to_the_middle():
    """Stopping at the edge of the dead zone left the speaker there, ready to set off the next move."""
    reach = 0.25
    target = 0.5 + DEAD_ZONE * reach * 2 * 1.5
    path, _ = glide([0.5] * 3 + [target] * 90, [False] * 93, reach=reach, start_at=0.5)
    assert abs(target - path[-1]) < tracking.SETTLE * reach * 2 * 1.5


def test_a_slow_walk_is_followed_in_one_move():
    reach = 0.25
    walk = [0.5] * 6 + [0.5 + 0.12 * i / 24 for i in range(24)] + [0.62] * 30
    path, _ = glide(walk, [False] * len(walk), reach=reach, start_at=0.5)
    steps = [b - a for a, b in zip(path, path[1:])]
    crawl = MAX_PAN * reach * 2 / PATH_FPS / 20  # the last creep of a settling frame is no move
    still = [abs(s) < crawl for s in steps]
    started = [i for i in range(1, len(still)) if still[i - 1] and not still[i]]
    assert len(started) == 1, "the frame goes along with them instead of stopping and starting"


def test_one_stray_look_moves_nothing():
    looks = [0.5] * 12 + [0.5 + DEAD_ZONE * 0.5 * 2.5] + [0.5] * 12
    path, _ = glide(looks, [False] * len(looks), reach=0.25, start_at=0.5)
    assert max(path) - min(path) == 0


def test_someone_walking_out_of_the_frame_is_caught_faster_than_eased():
    reach = 0.25
    far = 0.5 + KEEP_IN * reach * 2 * 1.4
    path, _ = glide([0.5] + [far] * 40, [False] * 41, reach=reach, start_at=0.5)
    steps = [b - a for a, b in zip(path, path[1:])]
    assert max(steps) > MAX_PAN * reach * 2 / PATH_FPS, "the speed limit is lifted to keep up"
    assert max(steps) <= RESCUE_PAN * reach * 2 / PATH_FPS + 1e-9


def test_a_clip_opens_on_the_speaker_rather_than_panning_onto_them():
    path, _ = glide(held(0.8, 30), [False] * 30, reach=0.25, start_at=0.2)
    assert path[0] == pytest.approx(0.8), "the window the user set is only a fallback"


def test_without_a_single_sighting_the_users_own_window_stands():
    path, jumps = glide([None] * 30, [False] * 30, reach=0.25, start_at=0.3)
    assert jumps == []
    assert set(path) == {0.3}


def test_the_frame_jumps_on_a_cut_and_says_where():
    reach = 0.25
    targets = [0.3] * 10 + [0.8] * 10
    cuts = [False] * 10 + [True] + [False] * 9
    path, jumps = glide(targets, cuts, reach=reach, start_at=0.3)
    assert len(jumps) == 1
    step = jumps[0]
    assert path[step] - path[step - 1] == pytest.approx(0.5, abs=0.02), "one step, not a pan"


def test_a_cut_back_to_the_same_framing_does_not_twitch():
    targets = [0.5] * 20
    cuts = [False] * 8 + [True] + [False] * 11
    path, jumps = glide(targets, cuts, reach=0.25, start_at=0.5)
    assert jumps == []
    assert max(path) - min(path) == 0


def test_the_path_never_leaves_the_picture():
    path, _ = glide([1.6] * 10 + [-0.9] * 10, [False] * 20, reach=0.25, start_at=0.5)
    assert all(0.0 <= x <= 1.0 for x in path)


def test_the_path_is_as_long_as_the_clip():
    seconds = 8
    samples = int(seconds * SAMPLE_FPS) + 1
    path, _ = glide(held(0.5, samples), [False] * samples, reach=0.25, start_at=0.5)
    assert len(path) == pytest.approx(seconds * PATH_FPS + 1, abs=1)


def test_an_empty_clip_gives_an_empty_path():
    assert glide([], [], reach=0.25, start_at=0.5) == ([], [])


# --- the numbers around it --------------------------------------------------------


def test_half_the_crop_width_is_a_share_of_the_source():
    reach = half_width(WIDE, OUT, CropWindow(x=0.5, y=0.5, zoom=1.0))
    assert 0.0 < reach < 0.5
    tighter = half_width(WIDE, OUT, CropWindow(x=0.5, y=0.5, zoom=2.0))
    assert tighter < reach, "zooming in makes the window narrower"


def test_sightings_become_fractions_of_the_width():
    seen = [Sighting(0.0, 0.0), Sighting(0.3, 960.0), Sighting(0.6, 1920.0), Sighting(0.9, None)]
    assert anchors(seen, 1920) == [0.0, 0.5, 1.0, None]


def test_a_sighting_outside_the_frame_is_pulled_back_in():
    assert anchors([Sighting(0.0, -40.0), Sighting(0.3, 2400.0)], 1920) == [0.0, 1.0]


def test_coverage_counts_the_samples_that_found_somebody():
    seen = [Sighting(0.0, 100.0), Sighting(0.3, None), Sighting(0.6, 120.0), Sighting(0.9, 140.0)]
    assert coverage(seen) == pytest.approx(0.75)
    assert coverage([]) == 0.0


def test_the_zones_stay_in_the_order_they_are_meant_to_be_in():
    assert 0 < DEAD_ZONE < KEEP_IN < 0.5, "the frame edge sits at 0.5"
    assert DEAD_ZONE <= tracking.SNAP_AFTER < KEEP_IN, "a cut never jumps for less than a pan would"
    assert MAX_PAN < RESCUE_PAN
    assert tracking.PATH_FPS > tracking.SAMPLE_FPS, "the path is written finer than it is sampled"


def test_full_speed_can_be_shed_before_arriving():
    """Slowing down from the top speed must fit in the gentle braking, or the frame overshoots."""
    assert tracking.MAX_PAN / tracking.TAU <= tracking.ACCEL
    assert tracking.SETTLE < DEAD_ZONE


# --- how tight to crop ------------------------------------------------------------


def a_body(height_share: float, at: float = 0.5, count: int = 12) -> list[Sighting]:
    """Sightings of somebody standing still, `height_share` of the frame tall."""
    height = height_share * 1080
    return [Sighting(i / SAMPLE_FPS, 960.0,
                     Box(x=960, y=at * 1080, w=height / 3, h=height, score=0.8))
            for i in range(count)]


def test_somebody_who_already_fills_the_frame_is_not_cropped_in_on():
    assert tracking.suggest_zoom(a_body(0.85), WIDE, OUT) is None


def test_somebody_small_in_a_wide_shot_is_cropped_in_on():
    zoom = tracking.suggest_zoom(a_body(0.35), WIDE, OUT)
    assert zoom is not None and zoom > 1.0


def test_cropping_in_stops_before_the_picture_falls_apart():
    tiny = tracking.suggest_zoom(a_body(0.08), WIDE, OUT)
    assert tiny is not None and tiny <= tracking.ZOOM_MAX


def test_a_low_resolution_source_is_allowed_far_less_room():
    from backend.renderer import cover_scale

    small = VideoInfo(width=854, height=480, duration=30.0, fps=25.0, videoCodec="h264",
                      hasAudio=True, audioCodec="aac", audioSampleRate=48000, audioChannels=2)
    big = VideoInfo(width=3840, height=2160, duration=30.0, fps=25.0, videoCodec="h264",
                    hasAudio=True, audioCodec="aac", audioSampleRate=48000, audioChannels=2)
    seen = a_body(0.25)
    poor, rich = tracking.suggest_zoom(seen, small, OUT), tracking.suggest_zoom(seen, big, OUT)
    assert rich is not None and (poor is None or poor < rich)
    if poor:
        assert cover_scale(small, OUT) * poor <= tracking.UPSCALE_MAX + 1e-9


def test_a_difference_too_small_to_notice_is_not_made():
    # Just under the fill it aims for: cropping in by a few percent only costs sharpness.
    assert tracking.suggest_zoom(a_body(tracking.FILL / 1.04), WIDE, OUT) is None


def test_without_enough_sightings_nothing_is_proposed():
    assert tracking.suggest_zoom(a_body(0.3, count=2), WIDE, OUT) is None
    assert tracking.suggest_zoom([], WIDE, OUT) is None


def test_faces_alone_can_still_say_how_far_away_somebody_is():
    """Without the person model there are only heads, and a head implies a body."""
    heads = [Sighting(i / SAMPLE_FPS, 960.0, None,
                      Box(x=960, y=300, w=40, h=0.05 * 1080, score=0.9))
             for i in range(12)]
    zoom = tracking.suggest_zoom(heads, WIDE, OUT)
    assert zoom is not None and zoom > 1.0


def test_the_head_ends_up_high_in_the_frame_rather_than_in_the_middle():
    seen = [Sighting(i / SAMPLE_FPS, 960.0, None, Box(x=960, y=0.30 * 1080, w=40, h=60, score=0.9))
            for i in range(12)]
    y = tracking.suggest_y(seen, WIDE, OUT, 1.6)
    assert y is not None
    visible = tracking.visible_share(WIDE, OUT) / 1.6
    where = (0.30 - (y - visible / 2)) / visible  # where the head lands in the finished frame
    assert 0.25 < where < 0.42, "not centred, and not against the top edge"


def test_nothing_is_said_about_the_vertical_when_the_whole_height_is_in_frame():
    seen = a_body(0.5)
    assert tracking.suggest_y(seen, WIDE, OUT, 1.0) is None


def test_the_frame_stays_on_the_picture_however_high_the_speaker_stands():
    for at in (0.05, 0.5, 0.95):
        y = tracking.suggest_y(a_body(0.3, at=at), WIDE, OUT, 1.6)
        assert y is not None and 0.0 <= y <= 1.0
