"""The shorter age can disappear while a native covered handle slice remains."""

import pytest
from lxml import etree
from unit.x_fixtures import xml_fixture as document

from taktik.core.social_media.x.services.browsing.navigation import _alignment
from taktik.core.social_media.x.ui.screen import read_screen


def screen(stage):
    return read_screen(document(f"clipped-handle-age-loss-{stage}"), (1080, 2340))


def test_retained_body_and_video_keep_measured_movement():
    before, after = screen("before"), screen("after")
    assert _alignment(before, after, scrolling=True) == (1, True)
    assert before.posts[0].body == after.fragments[0].body
    assert not after.observable_posts


@pytest.mark.parametrize(
    "mutation",
    [
        "no_cover",
        "badge",
        "handle",
        "interactive",
        "header_not_clipped",
        "handle_edge",
        "badge_edge",
        "name_edge",
    ],
)
def test_clipped_handle_requires_native_shape_and_known_cover_edge(mutation):
    root = etree.fromstring(document("clipped-handle-age-loss-after").encode())
    header = root.xpath('//*[@resource-id="timeline_post"]')[0]
    name, badge, handle = header
    if mutation == "no_cover":
        cover = root.xpath('//*[@resource-id="ntp"]')[0]
        cover.getparent().remove(cover)
    elif mutation == "badge":
        badge.set("content-desc", "Unknown")
    elif mutation == "handle":
        handle.set("text", "@partial...")
    elif mutation == "interactive":
        handle.set("clickable", "true")
    elif mutation == "header_not_clipped":
        header.set("bounds", "[176,137][876,186]")
    elif mutation == "handle_edge":
        handle.set("bounds", "[474,111][725,148]")
    elif mutation == "badge_edge":
        badge.set("bounds", "[414,115][465,143]")
    else:
        name.set("bounds", "[176,111][415,170]")
    assert read_screen(etree.tostring(root), (1080, 2340)).rejected_posts
