"""Known header coverage can coincide with quoted article revelation."""

from dataclasses import replace

import pytest
from unit.paths import CORE
from unit.x_fixtures import xml_fixture

from taktik.core.social_media.x.services.browsing.navigation import XError, _alignment
from taktik.core.social_media.x.ui.screen import read_screen


def document(name):
    return xml_fixture(CORE / "tests/unit/social_media/x/fixtures" / f"{name}.xml")


def screens():
    return tuple(
        read_screen(document(f"covered-quote-reveal-{s}"), (1080, 2340))
        for s in ("before", "after")
    )


def test_covered_outer_handle_and_revealed_preview_keep_independent_movement():
    before, after = screens()
    assert _alignment(before, after, scrolling=True) == (1, True)
    assert not after.posts
    assert after.fragments[0].covered_header_visibility.bounds == (176, 187, 876, 236)
    assert not hasattr(after.fragments[0], "author")


@pytest.mark.parametrize(
    "mutation",
    ["no_cover", "wrong_cover", "header_motion", "no_header", "body", "quote"],
)
def test_coverage_requires_original_header_projection_and_known_overlay(mutation):
    before, after = screens()
    p = after.fragments[0]
    if mutation == "no_cover":
        after = replace(after, overlaps=())
    elif mutation == "wrong_cover":
        p = replace(
            p,
            covered_header_visibility=replace(
                p.covered_header_visibility, overlaps=((800, 143, 900, 275),)
            ),
        )
    elif mutation == "header_motion":
        p = replace(
            p,
            covered_header_visibility=replace(
                p.covered_header_visibility, bounds=(176, 200, 876, 249)
            ),
        )
    elif mutation == "no_header":
        p = replace(p, covered_header_visibility=None)
    elif mutation == "body":
        p = replace(p, body="Changed")
    else:
        p = replace(p, quoted_post=replace(p.quoted_post, author="@changed"))
    with pytest.raises(XError):
        _alignment(before, replace(after, fragments=(p,)), scrolling=True)
