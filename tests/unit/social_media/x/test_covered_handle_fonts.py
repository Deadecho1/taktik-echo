"""A taller display-name script does not expose the covered handle below it."""

import pytest
from lxml import etree
from unit.x_fixtures import xml_fixture as document

from taktik.core.social_media.x.services.browsing.navigation import _alignment
from taktik.core.social_media.x.ui.screen import read_screen


def test_covered_handle_uses_its_own_text_height_without_attributing_the_fragment():
    before, after = [
        read_screen(document(f"covered-handle-fonts-{s}"), (1080, 2340))
        for s in ("before", "after")
    ]
    assert not after.rejected_posts
    p = after.fragments[-1]
    assert p.covered_handle.visibility.bounds[3] < p.covered_header_visibility.bounds[3]
    assert p.body == before.posts[0].body
    assert not hasattr(p, "author")
    assert _alignment(before, after, scrolling=True) == (1, True)


@pytest.mark.parametrize(
    "mutation",
    [
        "below_cover",
        "above_header",
        "missing_cover",
        "gap",
        "invalid_handle",
        "interactive",
    ],
)
def test_partial_handle_still_requires_full_cover_of_its_missing_text(mutation):
    root = etree.fromstring(document("covered-handle-fonts-after").encode())
    handle = root.xpath('//*[@text="@fixture_1"]')[0]
    if mutation == "below_cover":
        handle.set("bounds", "[376,222][389,278]")
    elif mutation == "above_header":
        handle.set("bounds", "[376,200][389,271]")
    elif mutation == "missing_cover":
        cover = root.xpath('//*[@resource-id="ntp"]')[0]
        cover.getparent().remove(cover)
    elif mutation == "gap":
        handle.set("bounds", "[376,222][385,271]")
    elif mutation == "invalid_handle":
        handle.set("text", "@Tiwari...")
    else:
        handle.set("clickable", "true")
    assert read_screen(etree.tostring(root), (1080, 2340)).rejected_posts
