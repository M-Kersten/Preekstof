"""The house style: the subtitles and the logo every clip of a church shares.

Setting them clip by clip made a batch of five clips five times the same work. So a change
in one clip becomes the house style of the active brand, and goes along to every other clip
that still wore the old house style and has not been made yet. A new clip starts from it.

A clip can keep a look of its own ("alleen voor deze clip"): then nothing it does goes
elsewhere, and nothing done elsewhere comes to it.
"""

from collections.abc import Callable
from typing import Literal

from pydantic import BaseModel

from . import brands, models
from .models import Project, load_project, project_dir, save_project

Part = Literal["style", "watermark"]
IN_BRAND: dict[str, str] = {"style": "subtitleStyle", "watermark": "watermark"}


def dress(project: Project) -> Project:
    """A new clip starts from the active brand: its subtitles, logo and music."""
    brand = brands.active()
    project.style = brand.subtitleStyle.model_copy(deep=True)
    project.music = brand.music.model_copy(deep=True)
    project.watermark = brand.watermark.model_copy(deep=True)
    return project


def made(project_id: str) -> bool:
    """A clip that has a video already. Its look is left as it was made."""
    output = project_dir(project_id) / "output"
    return output.is_dir() and any(output.glob("*.mp4"))


def others(but: str) -> list[Project]:
    found = []
    for path in sorted(models.PROJECTS_DIR.glob("*/project.json")):
        if path.parent.name == but:
            continue
        try:
            project = load_project(path.parent.name)
        except ValueError:  # a damaged file is no reason to stop the edit in hand
            continue
        if project is not None:
            found.append(project)
    return found


def wear(project: Project, part: Part, value: BaseModel,
         busy: Callable[[str], bool] = lambda _id: False) -> list[str]:
    """Give this clip `value`, and make it the house style unless the clip keeps its own.

    Returns the other clips that went along. A clip that is being made right now is left
    alone, like one that is finished: changing it halfway would leave its video out of date
    the moment it arrives.
    """
    setattr(project, part, value)
    save_project(project)
    if part in project.own:
        return []
    brand = brands.active()
    house = getattr(brand, IN_BRAND[part])
    if house == value:
        return []
    along = []
    for other in others(project.id):
        if part in other.own or getattr(other, part) != house or made(other.id) or busy(other.id):
            continue
        setattr(other, part, value.model_copy(deep=True))
        save_project(other)
        along.append(other.id)
    setattr(brand, IN_BRAND[part], value.model_copy(deep=True))
    brands.save(brand)
    return along


def keep_own(project: Project, part: Part, own: bool) -> Project:
    """Let this clip keep its own look, or have it wear the house style again."""
    if own and part not in project.own:
        project.own = [*project.own, part]
    elif not own and part in project.own:
        project.own = [p for p in project.own if p != part]
        setattr(project, part, getattr(brands.active(), IN_BRAND[part]).model_copy(deep=True))
    save_project(project)
    return project
