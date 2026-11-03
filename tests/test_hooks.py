"""The hook: a few seconds from later in the clip, played first.

Claude proposes the sentence; where it sits, and whether it may be used, is decided here,
from the words whisper heard and the times it heard them at.
"""

import pytest

from backend import formats, hooks, renderer
from backend.hooks import LlmHook
from backend.models import Hook, Output, Project, Segment, Spoken, Transcript, VideoInfo

LENGTH = 60.0


def spoken(start: float, text: str, pace: float = 0.4) -> Segment:
    words = text.split()
    timed = [Spoken(start=round(start + i * pace, 2), end=round(start + i * pace + pace - 0.05, 2), word=w)
             for i, w in enumerate(words)]
    return Segment(start=start, end=timed[-1].end, text=text, words=timed)


CLIP = Transcript(language="nl", segments=[
    spoken(0.0, "Vandaag lezen we over de verloren zoon."),
    spoken(4.0, "Een jongen die alles meeneemt en vertrekt."),
    spoken(20.0, "Dus hij komt thuis en zijn vader rent hem tegemoet."),
    spoken(30.0, "Genade is niet wat je verdient, het is wat je krijgt."),
    spoken(40.0, "Dat is het hele evangelie in één zin."),
])


def test_a_quote_is_found_where_it_was_said():
    hook, why = hooks.place("Genade is niet wat je verdient", hooks.said(CLIP), LENGTH)
    assert why == "" and hook is not None
    assert hook.start == pytest.approx(30.0 - hooks.BEFORE, abs=0.01)
    assert 1.5 <= hook.end - hook.start <= 5.0
    assert hook.text == "Genade is niet wat je verdient,"


def test_capitals_and_punctuation_do_not_matter():
    hook, _ = hooks.place("genade is NIET wat je verdient", hooks.said(CLIP), LENGTH)
    assert hook is not None


def test_words_that_are_not_there_are_refused():
    """The model may not improve the sentence; the hook is what was said."""
    hook, why = hooks.place("Genade is niet wat je verdiend hebt", hooks.said(CLIP), LENGTH)
    assert hook is None and "letterlijk" in why


def test_the_cut_never_reaches_into_the_next_word():
    words = hooks.said(CLIP)
    hook, _ = hooks.place("Genade is niet wat je verdient", words, LENGTH)
    following = next(w for w in words if w.start > 31.5 and w.word == "het")
    assert hook.end < following.start


def test_a_hook_from_the_opening_seconds_is_refused():
    """The clip says it again a moment later; that is a repeat, not a preview."""
    hook, why = hooks.place("Vandaag lezen we over de verloren zoon", hooks.said(CLIP), LENGTH)
    assert hook is None and "begin" in why


def test_a_hook_that_leans_on_what_came_before_is_refused():
    hook, why = hooks.place("Dus hij komt thuis en zijn vader rent", hooks.said(CLIP), LENGTH)
    assert hook is None and "verwijzing" in why


@pytest.mark.parametrize("quote, why", [("Genade", "kort"),
                                        ("Genade is niet wat je verdient, het is wat je krijgt. Dat is", "lang")])
def test_too_short_and_too_long_are_refused(quote, why):
    hook, said = hooks.place(quote, hooks.said(CLIP), LENGTH)
    assert hook is None and why in said


def test_the_proposals_that_pass_are_kept_best_first(capsys):
    chosen = hooks.choose([LlmHook(quote="Vandaag lezen we over de verloren zoon", why=""),
                           LlmHook(quote="Genade is niet wat je verdient", why=""),
                           LlmHook(quote="het is wat je krijgt", why=""),
                           LlmHook(quote="Dat is het hele evangelie in één zin", why="")], CLIP, LENGTH)
    assert [h.text for h in chosen] == ["Genade is niet wat je verdient,", "het is wat je krijgt."]
    assert "valt af" in capsys.readouterr().out


def test_the_same_seconds_are_not_offered_twice():
    first = hooks.choose([LlmHook(quote="Genade is niet wat je verdient", why="")], CLIP, LENGTH)
    again = hooks.choose([LlmHook(quote="Genade is niet wat je verdient", why=""),
                          LlmHook(quote="is niet wat je verdient", why=""),
                          LlmHook(quote="het is wat je krijgt", why="")], CLIP, LENGTH, besides=first)
    assert [h.text for h in again] == ["het is wat je krijgt."]


def test_asking_again_names_what_was_offered_before():
    asked = hooks.question(CLIP, "Genade", ["Genade is niet wat je verdient,"])
    assert "al voorgesteld" in asked and "- Genade is niet wat je verdient," in asked
    assert "al voorgesteld" not in hooks.question(CLIP, "Genade")


def test_through_a_stubbed_model(monkeypatch):
    monkeypatch.setattr(hooks, "ON", True)
    monkeypatch.setattr("backend.discovery.check_provider", lambda: None)
    monkeypatch.setattr("backend.discovery.ask", lambda *a, **k: hooks.LlmHooks(hooks=[
        LlmHook(quote="Genade is niet wat je verdient", why="de kern")]))
    found = hooks.suggest(CLIP, LENGTH, "Genade")
    assert len(found) == 1 and found[0].by == "claude" and found[0].on


def test_no_key_is_no_hook_and_no_failure(monkeypatch):
    monkeypatch.setattr(hooks, "ON", True)
    monkeypatch.setattr("backend.discovery.check_provider",
                        lambda: (_ for _ in ()).throw(RuntimeError("geen sleutel")))
    assert hooks.suggest(CLIP, LENGTH) == []


def test_a_short_clip_gets_no_hook(monkeypatch):
    monkeypatch.setattr(hooks, "ON", True)
    monkeypatch.setattr("backend.discovery.check_provider", lambda: pytest.fail("niets vragen"))
    assert hooks.suggest(CLIP, 12.0) == []


def test_switched_off_asks_nothing(monkeypatch):
    monkeypatch.setattr(hooks, "ON", False)
    monkeypatch.setattr("backend.discovery.check_provider", lambda: pytest.fail("niets vragen"))
    assert hooks.suggest(CLIP, LENGTH) == []


def test_the_question_carries_the_lines_with_their_times():
    asked = hooks.question(CLIP, "De verloren zoon")
    assert "De verloren zoon" in asked
    assert "30.0-" in asked and "Genade is niet wat je verdient" in asked


# --- what it shows -------------------------------------------------------------------


def test_the_hook_captions_hold_only_its_own_words_counted_from_zero():
    hook, _ = hooks.place("Genade is niet wat je verdient", hooks.said(CLIP), LENGTH)
    shown = hooks.captions(CLIP, hook)
    assert [s.text for s in shown.segments] == ["Genade is niet wat je verdient,"]
    first = shown.segments[0]
    assert first.start == pytest.approx(0.0, abs=0.2)
    assert first.end <= hook.end - hook.start + 1e-6
    assert first.words[0].start == pytest.approx(hooks.BEFORE, abs=0.01)


def test_a_hook_set_by_hand_stays_inside_the_clip():
    hook = hooks.by_hand(Hook(start=58.0, end=63.0), LENGTH)
    assert (hook.start, hook.end, hook.by) == (58.0, 60.0, "hand")
    with pytest.raises(ValueError):
        hooks.by_hand(Hook(start=10.0, end=10.2), LENGTH)
    with pytest.raises(ValueError):
        hooks.by_hand(Hook(start=10.0, end=30.0), LENGTH)


# --- what it makes -------------------------------------------------------------------


INFO = VideoInfo(width=1280, height=720, duration=30.0, fps=25.0, hasAudio=True)


def command(tmp_path, hook=None):
    return renderer.build_command(tmp_path / "rec.mp4", INFO, tmp_path / "main.ass", None, None, Output(),
                                  tmp_path / "out.mp4", source_start=100.0, hook=hook,
                                  hook_subtitles=tmp_path / "hook.ass" if hook else None)


def test_without_a_hook_the_command_is_what_it_was(tmp_path):
    argv, total = command(tmp_path)
    graph = argv[argv.index("-filter_complex") + 1]
    assert total == 30.0 and "hookv" not in graph and argv.count("-i") == 1


def test_the_hook_is_its_own_few_seconds_of_the_recording_played_first(tmp_path):
    argv, total = command(tmp_path, (14.9, 17.9))
    assert total == pytest.approx(33.0)
    assert argv.count("-i") == 2
    second = argv.index("-i", argv.index("-i") + 1)
    assert argv[second - 4:second] == ["-ss", "114.900", "-t", "3.000"]
    graph = argv[argv.index("-filter_complex") + 1]
    assert "[hookv][mainv]concat=n=2" in graph
    assert "fade=t=out" in graph and "color=white" in graph
    assert "[hooka][maina]concat=n=2:v=0:a=1,loudnorm" in graph
    assert "hook.ass" in graph


def test_a_moving_frame_follows_on_from_where_the_hook_starts(tmp_path):
    from backend.models import Track

    track = Track(fps=10.0, x=[i / 300 for i in range(301)], enough=True)
    argv, _ = renderer.build_command(tmp_path / "rec.mp4", INFO, tmp_path / "main.ass", None, None, Output(),
                                     tmp_path / "out.mp4", crop_strategy="tracked", track=track,
                                     source_start=0.0, commands=tmp_path / "track.cmd", hook=(20.0, 23.0),
                                     hook_subtitles=tmp_path / "hook.ass", hook_commands=tmp_path / "hook.cmd")
    graph = argv[argv.index("-filter_complex") + 1]
    assert "crop@hook=" in graph and "crop@track=" in graph
    lines = (tmp_path / "hook.cmd").read_text().splitlines()
    assert lines[0].startswith("0.0000 crop@hook x")
    assert float(lines[-1].split()[0]) <= 3.0
    main = (tmp_path / "track.cmd").read_text()
    assert "crop@hook" not in main


def test_a_clip_without_a_hook_keeps_its_recipe():
    """Made before hooks existed, it is not out of date because of them."""
    bare = Project(id="p", createdAt="nu")
    off = bare.model_copy(update={"hook": Hook(start=10, end=13, on=False)})
    on = bare.model_copy(update={"hook": Hook(start=10, end=13)})

    from backend import brands

    brand = brands.Brand(id="b", name="B")
    words = Transcript()
    assert formats.recipe(bare, words, brand) == formats.recipe(off, words, brand)
    assert formats.recipe(bare, words, brand) != formats.recipe(on, words, brand)


# --- through the app ---------------------------------------------------------------------


@pytest.fixture
def clip(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    from backend import main, models

    monkeypatch.setattr(models, "PROJECTS_DIR", tmp_path / "projects")
    project = models.new_project()
    project.sourceInfo = VideoInfo(width=1280, height=720, duration=LENGTH, fps=25.0, hasAudio=True)
    models.save_project(project)
    models.save_transcript(project, CLIP)
    return TestClient(main.app), project.id


def test_a_hook_set_in_the_editor_is_kept_as_chosen_by_hand(clip):
    client, pid = clip
    said = client.put(f"/projects/{pid}/hook", json={"hook": {"start": 29.9, "end": 32.5, "text": "", "on": True,
                                                              "by": "claude"}}).json()
    assert said["hook"]["by"] == "hand" and said["hook"]["end"] == 32.5


def test_switching_it_off_keeps_where_it_was(clip, monkeypatch):
    client, pid = clip
    client.put(f"/projects/{pid}/hook", json={"hook": {"start": 29.9, "end": 32.5, "text": "", "on": True}})
    said = client.put(f"/projects/{pid}/hook", json={"hook": {"start": 29.9, "end": 32.5, "text": "", "on": False}})
    assert said.json()["hook"]["on"] is False and said.json()["hook"]["start"] == 29.9


def test_a_hook_of_nothing_is_refused(clip):
    client, pid = clip
    said = client.put(f"/projects/{pid}/hook", json={"hook": {"start": 10.0, "end": 10.2, "text": ""}})
    assert said.status_code == 400


def test_asking_without_a_hook_takes_the_best(clip, monkeypatch):
    client, pid = clip
    monkeypatch.setattr(hooks, "ON", True)
    monkeypatch.setattr("backend.discovery.check_provider", lambda: None)
    monkeypatch.setattr("backend.discovery.ask", lambda *a, **k: hooks.LlmHooks(hooks=[
        LlmHook(quote="Genade is niet wat je verdient", why=""), LlmHook(quote="het is wat je krijgt", why="")]))
    said = client.post(f"/projects/{pid}/hook/suggest").json()
    assert said["hook"]["text"].startswith("Genade") and said["hook"]["by"] == "claude"
    assert len(said["hookOptions"]) == 2


def test_asking_again_adds_others_and_leaves_the_hook_alone(clip, monkeypatch):
    """Somebody browsing proposals decides which one to use; a new list does not decide for them."""
    client, pid = clip
    asked = []
    monkeypatch.setattr(hooks, "ON", True)
    monkeypatch.setattr("backend.discovery.check_provider", lambda: None)
    answers = [[LlmHook(quote="Genade is niet wat je verdient", why="")],
               [LlmHook(quote="Genade is niet wat je verdient", why=""), LlmHook(quote="het is wat je krijgt", why="")]]
    monkeypatch.setattr("backend.discovery.ask",
                        lambda user, *a, **k: asked.append(user) or hooks.LlmHooks(hooks=answers.pop(0)))
    client.post(f"/projects/{pid}/hook/suggest")
    said = client.post(f"/projects/{pid}/hook/suggest").json()
    assert said["hook"]["text"].startswith("Genade")
    assert [o["text"] for o in said["hookOptions"]] == ["het is wat je krijgt.", "Genade is niet wat je verdient,"]
    assert "al voorgesteld" in asked[1] and "Genade is niet wat je verdient," in asked[1]


def test_taking_another_proposal_keeps_it_a_proposal(clip, monkeypatch):
    client, pid = clip
    monkeypatch.setattr(hooks, "ON", True)
    monkeypatch.setattr("backend.discovery.check_provider", lambda: None)
    monkeypatch.setattr("backend.discovery.ask", lambda *a, **k: hooks.LlmHooks(hooks=[
        LlmHook(quote="Genade is niet wat je verdient", why=""), LlmHook(quote="het is wat je krijgt", why="")]))
    options = client.post(f"/projects/{pid}/hook/suggest").json()["hookOptions"]
    said = client.put(f"/projects/{pid}/hook", json={"hook": options[1]}).json()
    assert said["hook"]["text"] == "het is wat je krijgt." and said["hook"]["by"] == "claude"


def test_nothing_usable_says_so(clip, monkeypatch):
    client, pid = clip
    monkeypatch.setattr(hooks, "ON", True)
    monkeypatch.setattr("backend.discovery.check_provider", lambda: None)
    monkeypatch.setattr("backend.discovery.ask", lambda *a, **k: hooks.LlmHooks(hooks=[]))
    said = client.post(f"/projects/{pid}/hook/suggest")
    assert said.status_code == 422 and "zelf" in said.json()["detail"]


def test_a_new_suggestion_never_replaces_one_chosen_by_hand(clip, monkeypatch):
    from backend import main, models

    _client, pid = clip
    project = models.load_project(pid)
    project.hook = Hook(start=40.0, end=42.5, by="hand")
    monkeypatch.setattr(hooks, "suggest", lambda *a, **k: pytest.fail("niets vragen"))
    main.offer_hook(project, CLIP)
    assert project.hook.start == 40.0


def test_the_editor_knows_the_same_leaning_words():
    """frontend/src/hook.ts warns about a hand-picked hook with the same words the checks use."""
    import json
    import re
    from pathlib import Path

    from backend import discovery

    source = (Path(__file__).resolve().parent.parent / "frontend" / "src" / "hook.ts").read_text(encoding="utf-8")
    words = json.loads(re.search(r"COLD_WORDS = new Set\((\[.*?\])\)", source).group(1))
    phrases = json.loads(re.search(r"COLD_PHRASES = (\[.*?\])", source).group(1))
    assert set(words) == discovery.COLD_WORDS
    assert set(phrases) == set(discovery.COLD_PHRASES)
