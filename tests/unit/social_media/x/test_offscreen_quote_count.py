"""An offscreen compact media count can enter XML before its count glyph."""

from pathlib import Path

import pytest
from lxml import etree
from taktik.core.social_media.x.services.browsing.navigation import _alignment
from taktik.core.social_media.x.ui.screen import read_screen


def document(name):
    return (Path(__file__).parent / "fixtures" / f"{name}.xml").read_text()


def screen(stage):
    return read_screen(document(f"offscreen-quote-count-{stage}"), (1080, 2340))


def test_offscreen_count_keeps_native_description_without_inventing_glyph():
    s = screen("after")
    assert len(s.posts) == 1
    q = s.posts[0].quoted_post
    assert q.translation == "Translated from Arabic"
    assert q.media[0].description == "1 more media item"
    assert q.media[0].visibility.visible_bounds is None
    assert not q.observable


def test_captured_quote_entry_retains_alignment():
    assert _alignment(screen("before"), screen("after"), scrolling=True) == (0, True)


@pytest.mark.parametrize("mutation", ["visible", "unclipped", "unknown", "interactive"])
def test_missing_count_requires_offscreen_native_clipped_wrapper(mutation):
    root = etree.fromstring(document("offscreen-quote-count-after").encode())
    preview = root.xpath('//*[@content-desc="1 more media item"]')[-1]
    if mutation == "visible":
        preview.set("bounds", "[198,2200][399,2340]")
        preview.getnext().set("bounds", "[421,2200][1025,2340]")
    elif mutation == "unclipped":
        preview.set("bounds", "[198,2283][399,2339]")
    elif mutation == "unknown":
        preview.set("content-desc", "2 more media item")
    else:
        preview.set("clickable", "true")
    s = read_screen(etree.tostring(root), (1080, 2340))
    assert not s.posts
