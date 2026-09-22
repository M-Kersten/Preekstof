"""What the church already knows about a service, in the sentence the model gets to read.

Three small facts, and none of them guessed. The title and the series are typed in by hand;
the preacher comes off the church's own page. Together they are the difference between a
model reading a wall of text cold and one that knows what it is looking at.
"""

import pytest

from backend.main import sermon_context
from backend.models import Service


def a_service(**fields) -> Service:
    return Service(id="service-1", createdAt="2026-09-06T10:00:00+00:00", **fields)


def test_a_service_nobody_said_anything_about_sends_nothing():
    assert sermon_context(a_service()) == ""


def test_the_title_of_the_preaching_is_said():
    said = sermon_context(a_service(sermonTitle="Rust is geen zwakte"))
    assert said == "De preek van deze dienst heet: Rust is geen zwakte."


def test_the_series_is_said():
    assert "serie: Onderweg." in sermon_context(a_service(series="Onderweg"))


def test_who_is_announced_is_said_as_a_name_and_nothing_more():
    """No "hij", no "de dominee". Most churches type an initial and a surname, which says
    nothing about who is standing there, and the app does not fill that in."""
    said = sermon_context(a_service(preacher="ds. M. Kreuk"))
    assert said == "De spreker staat aangekondigd als: ds. M. Kreuk."
    assert " hij " not in said and " zij " not in said


def test_the_three_come_across_in_the_order_they_were_learned():
    said = sermon_context(a_service(sermonTitle="Rust", series="Onderweg", preacher="ds. M. Kreuk"))
    assert said == ("De preek van deze dienst heet: Rust. Hij hoort bij de serie: Onderweg. "
                    "De spreker staat aangekondigd als: ds. M. Kreuk.")


@pytest.mark.parametrize("field", ["sermonTitle", "series", "preacher"])
def test_a_field_holding_only_spaces_counts_as_empty(field):
    assert sermon_context(a_service(**{field: "   "})) == ""
