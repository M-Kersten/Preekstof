"""The text under the post: written by the model, checked by the app, finished with the church's own lines.

The model writes the body and nothing else. A quote it made up, a Bible passage nobody read
out, a link or a hashtag it slipped in anyway: each of those is caught here, because the
text goes out under the church's name and nobody proofreads a Monday-evening post twice.
"""

import time

import pytest
from fastapi.testclient import TestClient

from backend import brands, discovery, main, models, posts
from backend.models import (ChurchInfo, ClipCandidate, ClipOrigin, Project, Segment, Service, ShareSettings,
                            Transcript, VideoInfo)

SPOKEN = ("Paulus schrijft in Efeziërs 2 vers 8 dat je gered bent uit genade. "
          "Genade is geen beloning voor wie het goed doet. Het is een geschenk aan wie het niet verdient.")


def facts(**fields) -> posts.Facts:
    base = {"church": "De Kerk", "title": "Genade is geen beloning", "summary": "Over genade als geschenk.",
            "spoken": SPOKEN, "known": SPOKEN}
    return posts.Facts(**{**base, **fields})


def answer(**fields) -> posts.LlmPost:
    base = {"instagram": "Genade is geen beloning. Wat verandert er als je dat gelooft?",
            "facebook": "In de dienst ging het over genade.",
            "whatsapp": "Een mooi stuk over genade.",
            "hashtags": ["genade"], "bijbeltekst": ""}
    return posts.LlmPost(**{**base, **fields})


# --- quotes ------------------------------------------------------------------------


def test_a_quote_that_was_said_word_for_word_stands():
    body = 'Een zin om te onthouden: "Genade is geen beloning voor wie het goed doet."'
    assert posts.honest(body, SPOKEN)


def test_a_quote_nobody_said_is_caught():
    assert not posts.honest('"Genade is een beloning voor wie hard werkt."', SPOKEN)


def test_curly_and_dutch_quotation_marks_count_as_quotes_too():
    assert not posts.honest("„God houdt van wie het verdient”", SPOKEN)
    assert posts.honest("„Het is een geschenk aan wie het niet verdient”", SPOKEN)


def test_a_word_or_two_between_quotes_is_an_expression_not_a_quote():
    assert posts.honest('Wat betekent "genade" voor jou?', SPOKEN)


def test_a_text_with_a_made_up_quote_is_not_used(monkeypatch):
    made = posts.from_model(answer(facebook='De predikant zei: "Wie gelooft wordt rijk en gezond."'), facts())
    assert "rijk en gezond" not in made.facebook
    assert made.facebook == posts.template(facts()).facebook
    assert made.instagram.startswith("Genade is geen beloning"), "the other texts stay"


# --- what it was told to leave out ----------------------------------------------------


def test_hashtags_and_links_in_the_body_are_taken_out():
    cleaned = posts.clean("Kijk mee #genade op https://example.com/dienst of www.kerk.nl vandaag")
    assert "#" not in cleaned and "http" not in cleaned and "www" not in cleaned
    assert cleaned == "Kijk mee op of vandaag"


def test_hashtags_are_made_the_way_instagram_reads_them():
    assert posts.tags(["Genade", "#Hoop", "heilige geest", "genade", "", "2026"], 5) == [
        "#genade", "#hoop", "#heiligegeest"]


# --- the Bible passage ----------------------------------------------------------------


def test_a_passage_named_with_digits_is_kept():
    assert posts.checked_passage("Efeziërs 2:8", SPOKEN) == "Efeziërs 2:8"


def test_a_passage_said_in_words_is_kept():
    said = "We lezen Psalm drieëntwintig, vers een tot en met zes."
    assert posts.checked_passage("Psalm 23:1-6", said) == "Psalm 23:1-6"


def test_verses_that_were_not_said_are_left_off():
    assert posts.checked_passage("Efeziërs 2:9", SPOKEN) == "Efeziërs 2"


def test_a_chapter_that_was_not_said_leaves_only_the_book():
    assert posts.checked_passage("Efeziërs 4:1", SPOKEN) == "Efeziërs"


def test_a_book_nobody_mentioned_is_dropped():
    assert posts.checked_passage("Romeinen 8:28", SPOKEN) == ""


def test_something_that_is_not_a_book_is_dropped():
    assert posts.checked_passage("Hoofdstuk 3", "hoofdstuk 3") == ""
    assert posts.checked_passage("", SPOKEN) == ""


def test_other_spellings_of_the_same_book_count():
    assert posts.checked_passage("Matteüs 5:3", "In Mattheüs 5 vers 3 staat het") == "Matteüs 5:3"
    assert posts.checked_passage("Efeziërs 2", "aan de gemeente in Efeze, hoofdstuk 2") == "Efeziërs 2"


def test_a_numbered_book_keeps_its_number():
    said = "In de eerste brief aan de Korintiërs, hoofdstuk dertien"
    assert posts.checked_passage("1 Korintiërs 13", said) == "1 Korintiërs 13"


def test_numbers_are_written_the_way_they_are_said():
    assert posts.in_words(8) == "acht"
    assert posts.in_words(22) == "tweeëntwintig"
    assert posts.in_words(23) == "drieëntwintig"
    assert posts.in_words(40) == "veertig"
    assert posts.in_words(119) == "honderdnegentien"
    assert posts.in_words(150) == "honderdvijftig"


def test_a_passage_the_church_named_for_the_service_counts_too():
    known = f"{SPOKEN} Johannes 3"
    assert posts.checked_passage("Johannes 3", known) == "Johannes 3"


# --- the finished texts -------------------------------------------------------------------


def draft(**fields) -> posts.PostDraft:
    base = {"instagram": "Tekst voor Instagram.", "facebook": "Tekst voor Facebook.",
            "whatsapp": "Tekst voor WhatsApp.", "hashtags": ["genade", "hoop"], "bible": "Efeziërs 2:8"}
    return posts.PostDraft(**{**base, **fields})


def test_instagram_gets_the_passage_the_link_in_bio_and_all_the_tags():
    text = posts.assemble(draft(), "instagram", ShareSettings(hashtags=["#dekerk"]), "https://kerk.nl/dienst")
    assert text == ("Tekst voor Instagram.\n\nBijbelgedeelte: Efeziërs 2:8\n\n"
                    "De hele dienst terugkijken? De link staat in onze bio.\n\n#dekerk #genade #hoop")


def test_facebook_gets_the_link_itself_and_only_the_churchs_own_tags():
    text = posts.assemble(draft(), "facebook", ShareSettings(hashtags=["#dekerk"]), "https://kerk.nl/dienst")
    assert "De hele dienst terugkijken: https://kerk.nl/dienst" in text
    assert text.endswith("#dekerk") and "#genade" not in text


def test_whatsapp_is_the_text_and_the_link_and_nothing_else():
    text = posts.assemble(draft(), "whatsapp", ShareSettings(hashtags=["#dekerk"]), "https://kerk.nl/dienst")
    assert text == "Tekst voor WhatsApp.\nhttps://kerk.nl/dienst"


def test_without_a_link_nothing_points_to_the_whole_service():
    text = posts.assemble(draft(), "instagram", ShareSettings(), "")
    assert "bio" not in text and "terugkijken" not in text


def test_a_book_without_a_chapter_gets_no_line_of_its_own():
    assert "Bijbelgedeelte" not in posts.assemble(draft(bible="Efeziërs"), "facebook", ShareSettings(), "")


def test_instagram_stops_at_six_tags():
    many = ShareSettings(hashtags=["a1", "b2", "c3", "d4", "e5"])
    text = posts.assemble(draft(hashtags=["f6", "g7"]), "instagram", many, "")
    assert text.split("\n\n")[-1] == "#a1 #b2 #c3 #d4 #e5 #f6"


# --- the settings -----------------------------------------------------------------------


def test_a_link_without_its_beginning_is_completed():
    assert posts.tidy_link("kerkdienstgemist.nl/stations/1341") == "https://kerkdienstgemist.nl/stations/1341"
    assert posts.tidy_link("  ") == ""


def test_something_that_is_not_a_link_is_refused():
    with pytest.raises(ValueError):
        posts.tidy_link("onze website")


def test_settings_are_kept_the_way_they_are_used():
    tidy = posts.tidy_share(ShareSettings(shapes=["1x1", "9x16", "4x5", "1x1"], hashtags=["Kerk", "#Utrecht", ""],
                                          link="www.kerk.nl"))
    assert tidy.shapes == ["4x5", "1x1"]
    assert tidy.hashtags == ["#kerk", "#utrecht"]
    assert tidy.link == "https://www.kerk.nl"


# --- where the whole service is -------------------------------------------------------------


@pytest.fixture
def folders(tmp_path, monkeypatch):
    monkeypatch.setattr(models, "PROJECTS_DIR", tmp_path / "projects")
    monkeypatch.setattr(models, "SERVICES_DIR", tmp_path / "services")
    monkeypatch.setattr(main, "SERVICES_DIR", tmp_path / "services")
    templates = tmp_path / "templates"
    (templates / "brands").mkdir(parents=True)
    monkeypatch.setattr(brands, "BRANDS_DIR", templates / "brands")
    monkeypatch.setattr(brands, "ACTIVE_FILE", templates / "brands" / "actief.json")
    brands.save(brands.Brand(id="kerk", name="De Kerk", church=ChurchInfo(churchName="De Kerk")))
    brands.set_active("kerk")
    return tmp_path


def a_service(link: str = "https://kerkdienstgemist.nl/stations/1341/events/recording/99") -> Service:
    (models.service_dir("service-1") / "work").mkdir(parents=True, exist_ok=True)
    service = Service(id="service-1", createdAt="2026-09-21T09:00:00", preacher="ds. M. Kreuk",
                      sermonTitle="Gered uit genade", link=link,
                      candidates=[ClipCandidate(id="c1", start=600, end=640, title="Genade is geen beloning",
                                                summary="Genade als geschenk.")])
    models.save_service(service)
    return service


def a_clip(with_service: bool = True) -> Project:
    folder = models.project_dir("clip")
    (folder / "work").mkdir(parents=True, exist_ok=True)
    (folder / "output").mkdir(exist_ok=True)
    (folder / "source.mp4").write_bytes(b"not really a video")
    project = Project(id="clip", createdAt="2026-09-21T10:00:00", title="Genade is geen beloning",
                      sourceVideo="source.mp4",
                      sourceInfo=VideoInfo(width=1920, height=1080, duration=40, fps=25, hasAudio=True),
                      origin=ClipOrigin(serviceId="service-1", candidateId="c1", start=600, end=640)
                      if with_service else None)
    models.save_project(project)
    models.save_transcript(project, Transcript(segments=[Segment(start=0, end=9, text=SPOKEN)]))
    return project


def test_a_link_the_church_typed_wins(folders):
    a_service()
    link, where = posts.link_for(a_clip(), ShareSettings(link="https://youtube.com/@dekerk"), "1341")
    assert (link, where) == ("https://youtube.com/@dekerk", "merk")


def test_otherwise_the_page_the_service_came_from(folders):
    a_service()
    link, where = posts.link_for(a_clip(), ShareSettings(), "1341")
    assert where == "dienst" and link.endswith("/recording/99")


def test_otherwise_the_churchs_own_page(folders):
    link, where = posts.link_for(a_clip(with_service=False), ShareSettings(), "1341")
    assert where == "station" and "1341" in link


def test_a_clip_on_its_own_with_nothing_set_has_no_link(folders):
    assert posts.link_for(a_clip(with_service=False), ShareSettings(), "") == ("", "")


# --- writing -------------------------------------------------------------------------------


def test_what_the_model_is_given(folders):
    a_service()
    said = posts.facts_for(a_clip(), "De Kerk")
    assert said.summary == "Genade als geschenk."
    assert "ds. M. Kreuk" in said.about and "Gered uit genade" in said.about
    assert "Gered uit genade" in said.known, "a passage in the sermon title may be checked against it"
    question = posts.question(said)
    assert "Kerk: De Kerk" in question and SPOKEN in question


def test_an_install_nobody_set_up_is_not_named_in_a_post(folders):
    assert posts.facts_for(a_clip(with_service=False), posts.DEFAULT_CHURCH).church == ""


def test_the_way_to_address_the_reader_reaches_the_model(folders, monkeypatch):
    asked: list[str] = []
    monkeypatch.setattr(discovery, "check_provider", lambda: None)
    monkeypatch.setattr(discovery, "ask", lambda user, system, schema, effort="": asked.append(system) or answer())
    brand = brands.active()
    brand.share = ShareSettings(address="u")
    brands.save(brand)
    a_clip()
    written = posts.write("clip")
    assert written.by == "model"
    assert "Spreek de lezer aan met u." in asked[0] and "{address}" not in asked[0]


def test_without_a_key_the_plain_texts_are_used_and_it_says_why(folders, monkeypatch):
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("ANTHROPIC_AUTH_TOKEN", raising=False)
    monkeypatch.setattr(discovery, "LLM_PROVIDER", "anthropic")
    a_clip(with_service=False)
    written = posts.write("clip")
    assert written.by == "template"
    assert "sleutel" in written.note
    assert written.draft.instagram.startswith("Genade is geen beloning.")


def test_an_empty_account_says_so(folders, monkeypatch):
    monkeypatch.setattr(discovery, "check_provider", lambda: None)

    def broke(*a, **k):
        raise discovery.NoMoney(discovery.OUT_OF_MONEY)

    monkeypatch.setattr(discovery, "ask", broke)
    a_clip()
    assert "tegoed" in posts.write("clip").note


def test_a_clip_without_words_gets_the_plain_texts(folders, monkeypatch):
    monkeypatch.setattr(discovery, "ask", lambda *a, **k: pytest.fail("nothing to write about"))
    project = a_clip()
    models.save_transcript(project, Transcript())
    assert posts.write("clip").by == "template"


def test_switched_off_it_never_asks(folders, monkeypatch):
    monkeypatch.setattr(posts, "ON", False)
    monkeypatch.setattr(discovery, "ask", lambda *a, **k: pytest.fail("switched off"))
    a_clip()
    assert "WRITE_POSTS" in posts.write("clip").note


# --- the window ----------------------------------------------------------------------------


@pytest.fixture
def client(folders, monkeypatch):
    monkeypatch.setattr(discovery, "check_provider", lambda: None)
    monkeypatch.setattr(discovery, "ask", lambda *a, **k: answer(bijbeltekst="Efeziërs 2:8"))
    with TestClient(main.app) as running:
        yield running


def written(client, seconds: float = 5.0) -> dict:
    limit = time.monotonic() + seconds
    while True:
        state = client.get("/projects/clip/post").json()
        if state["job"]["status"] in ("done", "error") and state["post"]:
            return state
        if time.monotonic() > limit:
            raise AssertionError("de tekst is nooit klaar gekomen")
        time.sleep(0.02)


def test_the_window_asks_for_the_texts_and_gets_them(client):
    a_service()
    a_clip()
    assert client.get("/projects/clip/post").json()["post"] is None
    client.post("/projects/clip/post")
    state = written(client)["post"]
    assert state["by"] == "model" and state["bible"] == "Efeziërs 2:8"
    assert state["linkFrom"] == "dienst"
    assert "https://kerkdienstgemist.nl" in state["texts"]["facebook"]


def test_a_text_changed_by_hand_is_kept_and_wins(client):
    a_clip()
    client.post("/projects/clip/post")
    written(client)
    mine = "Mijn eigen tekst."
    state = client.put("/projects/clip/post", json={"platform": "instagram", "text": mine}).json()["post"]
    assert state["texts"]["instagram"] == mine and state["own"] == ["instagram"]
    brand = brands.active()
    brand.share = ShareSettings(hashtags=["#nieuw"])
    brands.save(brand)
    state = client.get("/projects/clip/post").json()["post"]
    assert state["texts"]["instagram"] == mine, "a change to the settings does not overwrite it"
    assert "#nieuw" in state["texts"]["facebook"], "the ones nobody touched do follow"


def test_putting_a_text_back_the_way_it_was_undoes_the_edit(client):
    a_clip()
    client.post("/projects/clip/post")
    original = written(client)["post"]["texts"]["whatsapp"]
    client.put("/projects/clip/post", json={"platform": "whatsapp", "text": "Anders."})
    state = client.put("/projects/clip/post", json={"platform": "whatsapp", "text": original}).json()["post"]
    assert state["own"] == []


def test_writing_again_drops_what_was_changed_by_hand(client):
    a_clip()
    client.post("/projects/clip/post")
    written(client)
    client.put("/projects/clip/post", json={"platform": "facebook", "text": "Anders."})
    client.post("/projects/clip/post")
    time.sleep(0.2)
    state = written(client)["post"]
    assert state["own"] == [] and state["texts"]["facebook"] != "Anders."


def test_an_unknown_place_is_refused(client):
    a_clip()
    assert client.put("/projects/clip/post", json={"platform": "tiktok", "text": "x"}).status_code == 400


def test_the_settings_are_saved_on_the_brand(client):
    answer_ = client.put("/share", json={"shapes": ["1x1"], "address": "u", "hashtags": ["Kerk"],
                                         "link": "kerk.nl"})
    assert answer_.status_code == 200
    kept = brands.active().share
    assert kept.shapes == ["1x1"] and kept.address == "u" and kept.hashtags == ["#kerk"]
    assert kept.link == "https://kerk.nl"
    assert client.get("/share").json()["address"] == "u"


def test_a_link_that_is_not_one_is_refused_with_a_reason(client):
    answer_ = client.put("/share", json={"shapes": [], "address": "je", "hashtags": [], "link": "onze site"})
    assert answer_.status_code == 400
    assert "webadres" in answer_.json()["detail"]


def test_making_a_video_writes_the_text_alongside_the_first_time(client, monkeypatch):
    monkeypatch.setattr(main, "end_screen", lambda project, shape: None)
    monkeypatch.setattr(main.renderer, "render_video",
                        lambda source, info, subs, output, destination, **kw: destination.write_bytes(b"x"))
    a_clip()
    client.post("/projects/clip/render")
    assert written(client)["post"]["by"] == "model"
