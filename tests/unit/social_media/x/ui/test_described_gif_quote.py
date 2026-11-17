"""Described GIFs and quotes beneath captionless GIFs preserve scroll anchors."""

import pytest
from lxml import etree
from unit.paths import CORE

from taktik.core.social_media.x.services.browsing.navigation import _alignment
from taktik.core.social_media.x.ui.screen import read_screen


def document(name):
    return (CORE / "tests/unit/social_media/x/fixtures" / f"{name}.xml").read_text()


def screen(xml=None):
    return read_screen(xml or document("described-gif-quote-after"), (1080, 2340))


def test_description_stays_with_gif_and_quote_stays_with_second_author():
    first, second = screen().posts
    assert first.body is None
    assert first.media[0].kind == "gif"
    assert first.media[0].description.startswith("GIF: Fixture animation ")
    assert first.media[0].visibility.overlaps
    assert first.observable
    assert second.body is None
    assert second.media[0].kind == "gif"
    assert second.quoted_post.author.startswith("@fixture_")
    assert second.author != second.quoted_post.author


def test_original_gif_sequence_preserves_both_gifs_and_quote_entry():
    before = read_screen(document("described-gif-quote-selected"), (1080, 2340))
    for stage in ("before", "after"):
        after = read_screen(document(f"described-gif-quote-{stage}"), (1080, 2340))
        assert _alignment(before, after, scrolling=True)[1]
        assert len(after.posts) == 2
        before = after


@pytest.mark.parametrize(
    "mutation",
    [
        "empty",
        "unknown",
        "control_label",
        "control_click",
        "control_bounds",
        "marker_click",
        "control_child",
    ],
)
def test_described_gif_requires_native_description_control(mutation):
    root = etree.fromstring(document("described-gif-quote-after").encode())
    marker = root.xpath('//*[starts-with(@content-desc,"GIF:")]')[0]
    control = marker.getparent().xpath('./node[@content-desc="Image description"]')[0]
    if mutation == "empty":
        marker.set("content-desc", "GIF: ")
    elif mutation == "unknown":
        marker.set("content-desc", "Animation: example")
    elif mutation == "control_label":
        control.set("content-desc", "Open link")
    elif mutation == "control_click":
        control.set("clickable", "false")
    elif mutation == "control_bounds":
        control.set("bounds", "[257,50][389,1051]")
    elif mutation == "marker_click":
        marker.set("clickable", "true")
    else:
        etree.SubElement(control, "node", dict(marker.attrib))
    assert len(screen(etree.tostring(root)).posts) == 1
    assert screen(etree.tostring(root)).posts[0].quoted_post is not None


@pytest.mark.parametrize("mutation", ["image", "above", "horizontal"])
def test_bodyless_gif_quote_requires_media_kind_order_and_width(mutation):
    root = etree.fromstring(document("described-gif-quote-after").encode())
    marker = root.xpath('//*[@content-desc="GIF"]')[0]
    if mutation == "image":
        marker.set("content-desc", "Image")
    elif mutation == "above":
        marker.set("bounds", "[176,1280][1047,1900]")
    else:
        marker.set("bounds", "[177,1280][1047,1850]")
    assert len(screen(etree.tostring(root)).posts) == 1
    assert screen(etree.tostring(root)).posts[0].quoted_post is None


def test_recorded_gif_row_keeps_controls_at_the_padded_media_edge():
    before = read_screen(document("described-gif-row-before"), (1080, 2340))
    after = read_screen(document("described-gif-row-after"), (1080, 2340))
    assert _alignment(before, after, scrolling=True)[1]
    assert len(after.posts[0].media) == 2
    assert all(m.kind == "gif" for m in after.posts[0].media)
