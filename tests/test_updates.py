"""Is there a newer one. Asked once, said once, and never acted on by itself."""

import json
import urllib.error
from io import BytesIO

import pytest

from backend import updates, version


class Answered:
    def __init__(self, body: dict | str):
        self.body = json.dumps(body).encode() if isinstance(body, dict) else body.encode()

    def read(self, limit=None):
        return self.body[:limit] if limit else self.body

    def __enter__(self):
        return self

    def __exit__(self, *_):
        return False


def answering(monkeypatch, answer):
    def reply(request, timeout=None):
        if isinstance(answer, Exception):
            raise answer
        return answer

    monkeypatch.setattr(updates.urllib.request, "urlopen", reply)


# --- which number is newer --------------------------------------------------------


@pytest.mark.parametrize("there, want", [
    ("0.9.1", True), ("0.10.0", True), ("1.0.0", True), ("v1.0.0", True),
    ("0.9.0", False), ("0.8.9", False), ("v0.9.0", False), ("0.0.1", False),
])
def test_only_a_higher_number_counts_as_newer(there, want):
    assert updates.newer(there, "0.9.0") is want


def test_ten_comes_after_nine_rather_than_before_it():
    """The one comparison a string would get wrong."""
    assert updates.newer("0.10.0", "0.9.0")
    assert not updates.newer("0.9.0", "0.10.0")


@pytest.mark.parametrize("there", ["", "onbekend", "v", "nightly", None])
def test_a_number_that_cannot_be_read_is_never_newer(there):
    assert not updates.newer(there or "", "0.9.0")


def test_a_tag_written_the_way_github_writes_it_is_understood():
    assert updates.as_numbers("v0.9.1") == (0, 9, 1)
    assert updates.as_numbers("Preekstof 1.2.3 (pilot)") == (1, 2, 3)


# --- what GitHub said --------------------------------------------------------------


def test_a_release_is_read_out_of_the_answer(monkeypatch):
    answering(monkeypatch, Answered({
        "tag_name": "v1.0.0",
        "html_url": "https://github.com/M-Kersten/Preekstof/releases/tag/v1.0.0",
        "body": "## Wat er verandert\n\n- De lijst laat zien wie voorging\n",
    }))
    there = updates.latest()
    assert there.version == "1.0.0"
    assert there.url.endswith("/v1.0.0")
    assert there.headline() == "De lijst laat zien wie voorging"


def test_a_heading_is_not_the_headline():
    """Every set of notes opens with one, and it tells a volunteer nothing."""
    assert updates.Release("1.0.0", "https://x", "# Preekstof 1.0.0\n\nEen echte regel\n") \
        .headline() == "Een echte regel"


def test_release_notes_nobody_wrote_leave_the_headline_empty():
    assert updates.Release("1.0.0", "https://x", "").headline() == ""
    assert updates.Release("1.0.0", "https://x", "## Alleen een kop\n").headline() == ""


@pytest.mark.parametrize("gone", [
    urllib.error.URLError("no route"), OSError("connection reset"),
    urllib.error.HTTPError("u", 403, "rate limited", {}, BytesIO(b"")),
])
def test_no_internet_means_nothing_is_said(monkeypatch, gone):
    """A church whose internet is down still has to get to its own app."""
    answering(monkeypatch, gone)
    assert updates.latest() is None
    assert updates.note() == ""


@pytest.mark.parametrize("said", [
    {}, {"tag_name": ""}, {"tag_name": "nightly"}, {"name": "geen nummer"},
])
def test_an_answer_without_a_readable_number_is_no_release(monkeypatch, said):
    answering(monkeypatch, Answered(said))
    assert updates.latest() is None


def test_nonsense_instead_of_json_is_survived(monkeypatch):
    answering(monkeypatch, Answered("<html>502 Bad Gateway</html>"))
    assert updates.latest() is None


def test_a_url_that_is_not_a_url_falls_back_to_the_releases_page(monkeypatch):
    """The one field here that ends up in front of a user, so it is not taken on trust."""
    answering(monkeypatch, Answered({"tag_name": "v1.0.0", "html_url": "javascript:alert(1)"}))
    assert updates.latest().url == "https://github.com/M-Kersten/Preekstof/releases/latest"


# --- what the black window says ----------------------------------------------------


def test_a_newer_version_is_named_with_where_to_get_it(monkeypatch):
    answering(monkeypatch, Answered({
        "tag_name": "v9.9.9", "html_url": "https://github.com/M-Kersten/Preekstof/releases/tag/v9.9.9",
        "body": "- Sneller uitschrijven\n",
    }))
    said = updates.note()
    assert "9.9.9" in said and version.VERSION in said
    assert "Sneller uitschrijven" in said
    assert "https://" in said
    assert "draait gewoon door" in said, "nothing installs itself"


def test_running_the_newest_one_is_worth_no_words_at_all(monkeypatch):
    answering(monkeypatch, Answered({"tag_name": f"v{version.VERSION}"}))
    assert updates.note() == ""


def test_an_older_release_than_this_one_says_nothing(monkeypatch):
    answering(monkeypatch, Answered({"tag_name": "v0.0.1"}))
    assert updates.note() == ""
