"""Paths inside FFmpeg filters, with the characters real folders have.

The desktop app's own check put it in a folder called Programma's and every clip failed:
"Error parsing filterchain". The same happens to the browser version on a computer whose
user folder is C:\\Users\\O'Brien. These run FFmpeg itself on such a folder.
"""

import shutil
import subprocess
from pathlib import Path

import pytest

from backend import outro, renderer
from backend.models import FONTS_DIR

pytestmark = pytest.mark.skipif(shutil.which("ffmpeg") is None, reason="needs FFmpeg")

ASS = """[Script Info]
ScriptType: v4.00+
PlayResX: 320
PlayResY: 240

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, OutlineColour, BackColour, Bold, Italic, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV
Style: Default,Montserrat,24,&H00FFFFFF,&H00000000,&H00000000,1,0,1,2,0,2,10,10,10

[Events]
Format: Layer, Start, End, Style, Text
Dialogue: 0,0:00:00.00,0:00:01.00,Default,Preekstof
"""


@pytest.mark.parametrize("folder", ["Programma's", "O'Brien", "met spatie", "a:b"])
@pytest.mark.parametrize("escape", [renderer._ffpath, outro.filter_path])
def test_ffmpeg_finds_subtitles_and_fonts_in_any_folder(tmp_path, folder, escape):
    if ":" in folder and shutil.which("cmd"):
        pytest.skip("Windows allows no colon in a folder name")
    here = tmp_path / folder
    here.mkdir()
    subtitles = here / "proef.ass"
    subtitles.write_text(ASS, encoding="utf-8")
    fonts = here / "fonts"
    shutil.copytree(FONTS_DIR, fonts)
    graph = f"ass=filename='{escape(subtitles)}':fontsdir='{escape(fonts)}'"
    said = subprocess.run(["ffmpeg", "-hide_banner", "-loglevel", "error", "-f", "lavfi",
                           "-i", "color=c=black:s=320x240:d=0.5", "-vf", graph, "-f", "null", "-"],
                          capture_output=True, text=True, timeout=60)
    assert said.returncode == 0, said.stderr


def test_a_plain_path_is_left_as_it_was():
    assert renderer._ffpath(Path("/home/kerk/clip.ass")) == "/home/kerk/clip.ass"
    assert renderer._ffpath(Path("C:/Users/kerk/clip.ass")) == "C\\:/Users/kerk/clip.ass"
