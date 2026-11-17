"""A native governmental badge remains video-source metadata."""

from pathlib import Path

import pytest
from lxml import etree

from taktik.core.social_media.x.services.browsing.navigation import _alignment
from taktik.core.social_media.x.ui.screen import read_screen


def document(name):
    return (Path(__file__).parent / "fixtures" / f"{name}.xml").read_text()


def test_governmental_source_badge_preserves_outer_authorship_and_movement():
    before, after = [
        read_screen(document(f"government-credit-{s}"), (1080, 2340))
        for s in ("before", "after")
    ]
    assert not before.rejected_posts
    assert before.posts[0].author == "@fixture_1"
    assert before.posts[0].media[0].source_label == "Fixture text 4"
    assert before.posts[0].labels == ("Verified",)
    assert before.posts[0].advertising == "unknown"
    assert _alignment(before, after, scrolling=True) == (0, True)


@pytest.mark.parametrize(
    "mutation", ["label", "clickable", "outside", "overlap", "text", "class"]
)
def test_source_badge_requires_known_native_shape(mutation):
    root = etree.fromstring(document("government-credit-before").encode())
    badge = root.xpath('//*[@content-desc="Verified Governmental Account"]')[0]
    if mutation == "label":
        badge.set("content-desc", "Unknown")
    elif mutation == "clickable":
        badge.set("clickable", "true")
    elif mutation == "outside":
        badge.set("bounds", "[1050,1307][1094,1351]")
    elif mutation == "overlap":
        badge.set("bounds", "[490,1307][534,1351]")
    elif mutation == "text":
        badge.set("text", "Unknown")
    else:
        badge.set("class", "android.widget.TextView")
    assert read_screen(etree.tostring(root), (1080, 2340)).rejected_posts
