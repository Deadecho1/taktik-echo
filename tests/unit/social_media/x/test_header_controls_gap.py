"""Native clipped header controls explain the gap before retained body text."""

from pathlib import Path

import pytest
from lxml import etree
from unit.x_fixtures import xml_fixture

from taktik.core.social_media.x.services.browsing.navigation import _alignment
from taktik.core.social_media.x.ui.screen import read_screen


def document(name):
    return xml_fixture(Path(__file__).parent / "fixtures" / f"{name}.xml")


def test_retained_header_controls_explain_body_start_below_viewport():
    before, after = (
        read_screen(document(f"header-controls-gap-{s}"), (1080, 2340))
        for s in ("before", "after")
    )
    assert not after.rejected_posts
    assert _alignment(before, after, scrolling=True) == (1, True)
    fragment = after.fragments[0]
    assert fragment.body_visibility.bounds[1] == 139
    assert not hasattr(fragment, "author")


def test_native_header_control_padding_can_extend_above_its_container():
    before, after = (
        read_screen(document(f"header-control-padding-{s}"), (1080, 2340))
        for s in ("before", "after")
    )
    assert not after.rejected_posts
    assert _alignment(before, after, scrolling=True) == (1, True)
    assert after.fragments[0].body_visibility.bounds[1] == 139


@pytest.mark.parametrize("mutation", ["label", "gap", "unclipped", "interactive_body"])
def test_body_gap_requires_native_clipped_controls(mutation):
    root = etree.fromstring(document("header-controls-gap-after").encode())
    grok = root.xpath('//*[@content-desc="Explain this post with Grok"]')[0]
    if mutation == "label":
        grok.set("content-desc", "Unknown")
    elif mutation == "gap":
        grok.set("bounds", "[879,50][959,138]")
    elif mutation == "unclipped":
        grok.set("bounds", "[879,137][959,139]")
    else:
        body = grok.getparent().xpath('./node[@text!=""]')[0]
        body.set("clickable", "true")
    after = read_screen(etree.tostring(root), (1080, 2340))
    assert not after.fragments
