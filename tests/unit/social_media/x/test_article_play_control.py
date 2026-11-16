"""A native article Play control is separate from quoted title and summary."""

from pathlib import Path

import pytest
from lxml import etree
from taktik.core.social_media.x.services.browsing.navigation import (
    _alignment,
    scroll_region,
)
from taktik.core.social_media.x.ui.screen import read_screen


def document(name):
    return (Path(__file__).with_name("fixtures") / f"{name}.xml").read_text()


def screen(stage):
    return read_screen(document(f"article-play-control-{stage}"), (1080, 2340))


def test_article_play_control_does_not_become_quoted_text_or_a_scroll_target():
    before, after = screen("before"), screen("after")
    assert not after.rejected_posts
    q = after.fragments[0].quoted_post
    assert q.body is None and len(q.media) == 1
    assert q.media[0].kind == "preview"
    assert q.media[0].description and q.media[0].preview_text
    assert "Play" not in q.labels
    assert _alignment(before, after, scrolling=True) == (1, True)
    region, _, exclusions = scroll_region(after)
    assert (899, 2087, 1031, 2219) in exclusions
    assert region[2] <= 176


@pytest.mark.parametrize(
    "mutation",
    [
        "label",
        "control_class",
        "disabled",
        "not_clickable",
        "extra",
        "glyph_clickable",
        "glyph_text",
        "glyph_outside",
        "over_title",
        "not_square",
        "order",
    ],
)
def test_article_play_control_requires_native_shape_and_geometry(mutation):
    root = etree.fromstring(document("article-play-control-after").encode())
    glyph = root.xpath('//*[@content-desc="Play"]')[0]
    control = glyph.getparent()
    preview = control.getparent()
    if mutation == "label":
        glyph.set("content-desc", "Unknown")
    elif mutation == "control_class":
        control.set("class", "android.widget.Button")
    elif mutation == "disabled":
        control.set("enabled", "false")
    elif mutation == "not_clickable":
        control.set("clickable", "false")
    elif mutation == "extra":
        control.append(etree.fromstring(etree.tostring(glyph)))
    elif mutation == "glyph_clickable":
        glyph.set("clickable", "true")
    elif mutation == "glyph_text":
        glyph.set("text", "Unknown")
    elif mutation == "glyph_outside":
        glyph.set("bounds", "[1020,2125][1075,2180]")
    elif mutation == "over_title":
        glyph.set("bounds", "[880,2125][935,2180]")
    elif mutation == "not_square":
        control.set("bounds", "[899,2087][1031,2200]")
    else:
        preview.insert(1, control)
    assert read_screen(etree.tostring(root), (1080, 2340)).rejected_posts
