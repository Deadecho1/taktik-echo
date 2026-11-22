"""A clipped options target can survive beside the avatar of a bodyless video."""

import pytest
from lxml import etree
from unit.x_fixtures import xml_fixture as document

from taktik.core.social_media.x.services.browsing.navigation import _alignment
from taktik.core.social_media.x.ui.screen import read_screen


def test_clipped_options_keeps_video_and_quote_unattributed():
    before, after = [
        read_screen(document(f"bodyless-clipped-options-{s}"), (1080, 2340))
        for s in ("before", "after")
    ]
    assert not after.rejected_posts
    p = after.fragments[0]
    assert not hasattr(p, "author")
    assert p.body is None and p.media[0].kind == "video"
    assert p.quoted_post.translation == "Translated from Indonesian"
    assert _alignment(before, after, scrolling=True) == (1, True)


@pytest.mark.parametrize(
    "mutation",
    [
        "unclipped",
        "wrong_edge",
        "too_low",
        "class",
        "label",
        "text",
        "disabled",
        "not_clickable",
        "scrollable",
        "nested",
        "missing_avatar",
    ],
)
def test_clipped_options_requires_native_control_shape_and_avatar(mutation):
    root = etree.fromstring(document("bodyless-clipped-options-after").encode())
    options = root.xpath('//*[@content-desc="Post options"]')[0]
    if mutation == "unclipped":
        options.set("bounds", "[959,136][1080,268]")
    elif mutation == "wrong_edge":
        options.set("bounds", "[900,6][1021,138]")
    elif mutation == "too_low":
        options.set("bounds", "[959,6][1080,190]")
    elif mutation == "class":
        options.set("class", "android.view.View")
    elif mutation == "label":
        options.set("content-desc", "Unknown action")
    elif mutation == "text":
        options.set("text", "Unexpected")
    elif mutation == "disabled":
        options.set("enabled", "false")
    elif mutation == "not_clickable":
        options.set("clickable", "false")
    elif mutation == "scrollable":
        options.set("scrollable", "true")
    elif mutation == "nested":
        options.append(etree.fromstring(etree.tostring(options)))
    else:
        options.getparent().remove(options.getprevious())
    assert read_screen(etree.tostring(root), (1080, 2340)).rejected_posts
