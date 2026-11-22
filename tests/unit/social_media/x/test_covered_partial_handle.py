"""A handle clipped by the New posts overlay remains unattributed."""

from pathlib import Path

import pytest
from lxml import etree

from taktik.core.social_media.x.services.browsing.navigation import _alignment
from taktik.core.social_media.x.ui.screen import read_screen

FIXTURES = Path(__file__).with_name("fixtures")


def document(name):
    return (FIXTURES / f"{name}.xml").read_text()


def test_covered_partial_handle_keeps_body_as_an_unattributed_anchor():
    before, after = [
        read_screen(document(f"covered-partial-handle-{s}"), (1080, 2340))
        for s in ("before", "after")
    ]
    assert not after.rejected_posts
    assert len(after.fragments) == 2
    assert after.fragments[1].body == before.posts[0].body
    assert not hasattr(after.fragments[1], "author")
    assert _alignment(before, after, scrolling=True) == (1, True)


@pytest.mark.parametrize(
    "mutation", ["no_cover", "handle_gap", "partial_text", "badge", "interactive"]
)
def test_covered_header_still_requires_the_known_cover_and_exact_structure(mutation):
    root = etree.fromstring(document("covered-partial-handle-after").encode())
    handle = root.xpath('//*[@text="@fixture_1"]')[0]
    if mutation == "no_cover":
        cover = root.xpath('//*[@resource-id="ntp"]')[0]
        cover.getparent().remove(cover)
    elif mutation == "handle_gap":
        handle.set("bounds", "[368,225][380,274]")
    elif mutation == "partial_text":
        handle.set("text", "@asta...")
    elif mutation == "badge":
        handle.getprevious().set("content-desc", "Unknown")
    else:
        handle.set("clickable", "true")
    screen = read_screen(etree.tostring(root), (1080, 2340))
    assert screen.rejected_posts
    assert all(f.body is None for f in screen.fragments)
