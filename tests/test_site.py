"""The install page a church is sent to, kept in step with what the release builds."""

import re
from pathlib import Path

import pytest

from backend import updates

ROOT = Path(__file__).resolve().parent.parent
PAGE = (ROOT / "site" / "index.html").read_text(encoding="utf-8")
WORKFLOW = (ROOT / ".github" / "workflows" / "pages.yml").read_text(encoding="utf-8")
REPO = re.search(r"repos/([^/]+/[^/]+)/releases", updates.RELEASES).group(1)


@pytest.mark.parametrize("name", sorted(updates.BUNDLES.values()))
def test_every_download_has_a_button_that_finds_it(name):
    """Renaming a zip in the release without the page means a button that gives a 404."""
    assert f"https://github.com/{REPO}/releases/latest/download/{name}" in PAGE
    assert f'data-asset="{name}"' in PAGE


def test_the_page_asks_the_same_repository_the_update_button_asks():
    assert f"api.github.com/repos/{REPO}/releases/latest" in PAGE


def test_what_the_page_loads_is_put_next_to_it():
    """The workflow copies the icon and the fonts in from where the app keeps them."""
    assert 'href="icon.svg"' in PAGE and "cp frontend/public/icon.svg _site/" in WORKFLOW
    for weight in re.findall(r"fonts/Poppins-(\w+)\.ttf", PAGE):
        assert weight in WORKFLOW.split("for weight in", 1)[1].splitlines()[0], weight
        assert (ROOT / "templates" / "fonts" / f"Poppins-{weight}.ttf").is_file()
    for other in re.findall(r"fonts/((?!Poppins)\w+-\w+\.ttf)", PAGE):
        assert f"templates/fonts/{other}" in WORKFLOW, other
        assert (ROOT / "templates" / "fonts" / other).is_file()


def test_nothing_on_the_page_comes_from_another_server():
    """Fonts from Google would hand every visitor's address to Google; nothing else is needed."""
    loaded = re.findall(r'(?:src|href)="(https?://[^"]+)"', PAGE)
    assert all(url.startswith("https://github.com/") for url in loaded), loaded
    assert "fonts.googleapis" not in PAGE
