"""The native Video/picture wrapper identifies media without its Play glyph."""

from copy import deepcopy
from pathlib import Path

import pytest
from lxml import etree
from taktik.core.social_media.x.services.browsing.navigation import _alignment
from taktik.core.social_media.x.ui.screen import read_screen


def document(name):
    return (Path(__file__).parent / "fixtures" / f"{name}.xml").read_text()


def screen(stage):
    return read_screen(document(f"optional-quote-play-{stage}"), (1080, 2340))


def test_visible_clipped_native_video_does_not_need_a_play_glyph():
    s = screen("after")
    assert not s.rejected_posts
    q = s.posts[0].quoted_post
    assert q.body is None and q.media[0].kind == "video"
    assert q.media[0].visibility.visible_bounds is not None
    assert not q.observable


def test_captured_quote_entry_retains_alignment():
    assert _alignment(screen("before"), screen("after"), scrolling=True) == (0, True)


@pytest.mark.parametrize("mutation", ["unknown", "interactive", "extra", "unclipped"])
def test_optional_glyph_preserves_native_wrapper_validation(mutation):
    root = etree.fromstring(document("optional-quote-play-after").encode())
    card = root.xpath('//*[@content-desc="Quote"]')[0].getparent()
    preview = card[-1]
    if mutation == "unknown":
        preview[1].set("content-desc", "Unknown")
    elif mutation == "interactive":
        preview[1].set("clickable", "true")
    elif mutation == "extra":
        preview.append(deepcopy(preview[-1]))
    else:
        for n in preview.iter():
            n.set("bounds", "[198,2030][1025,2320]")
    assert read_screen(etree.tostring(root), (1080, 2340)).rejected_posts
