"""Clipped name-only headers retain the native four-pixel glyph overhang."""

import pytest
from lxml import etree
from unit.x_fixtures import xml_fixture as document

from taktik.core.social_media.x.services.browsing.navigation import _alignment
from taktik.core.social_media.x.ui.screen import read_screen


def screen(stage):
    return read_screen(document(f"clipped-name-overhang-{stage}"), (1080, 2340))


def test_clipped_overhang_keeps_both_authors_unknown_and_retains_movement():
    before, after = screen("before"), screen("after")
    p = after.fragments[0]
    assert not hasattr(p, "author")
    assert p.quoted_post.author is None
    assert p.body == before.fragments[-1].body
    assert not after.observable_posts
    assert _alignment(before, after, scrolling=True) == (0, True)


@pytest.mark.parametrize("delta", [-5, -4, 0, 4, 5])
def test_name_overhang_tolerance_is_bounded(delta):
    root = etree.fromstring(document("clipped-name-overhang-after").encode())
    name = root.xpath('//*[@resource-id="timeline_post"]')[0][0]
    name.set("bounds", f"[{176 + delta},84][727,144]")
    result = read_screen(etree.tostring(root), (1080, 2340))
    assert bool(result.fragments) is (abs(delta) <= 4)


@pytest.mark.parametrize("mutation", ["handle", "unclipped", "height", "control"])
def test_overhanging_name_keeps_clipping_and_plain_text_guards(mutation):
    root = etree.fromstring(document("clipped-name-overhang-after").encode())
    header = root.xpath('//*[@resource-id="timeline_post"]')[0]
    name = header[0]
    if mutation == "handle":
        name.set("text", "@unknown")
    elif mutation == "unclipped":
        header.set("bounds", "[176,136][876,196]")
        name.set("bounds", "[172,136][727,196]")
    elif mutation == "height":
        name.set("bounds", "[172,84][727,143]")
    else:
        name.set("clickable", "true")
    assert not read_screen(etree.tostring(root), (1080, 2340)).fragments
