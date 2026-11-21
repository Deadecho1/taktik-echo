"""Offscreen native video wrappers can enter before their Play glyph."""

from pathlib import Path

import pytest
from lxml import etree

from taktik.core.social_media.x.services.browsing.navigation import _alignment
from taktik.core.social_media.x.ui.screen import read_screen


def document(name):
    return (Path(__file__).parent / "fixtures" / f"{name}.xml").read_text()


def screen(stage="after"):
    return read_screen(document(f"offscreen-quote-video-{stage}"), (1080, 2340))


def test_offscreen_video_does_not_invent_play_control_or_quoted_body():
    s = screen()
    assert not s.rejected_posts
    q = s.posts[0].quoted_post
    assert q.body is None and not q.body_complete
    assert q.media[0].kind == "video"
    assert q.media[0].visibility.visible_bounds is None
    assert not q.observable
    assert _alignment(screen("before"), s, scrolling=True)[1]


@pytest.mark.parametrize(
    "mutation",
    [
        "unclipped_media",
        "unknown",
        "interactive_child",
        "wrong_bounds",
    ],
)
def test_missing_play_requires_a_bottom_clipped_native_video(mutation):
    root = etree.fromstring(document("offscreen-quote-video-after").encode())
    card = root.xpath('//*[@content-desc="Quote"]')[0].getparent()
    preview = card[-1]
    if mutation == "unclipped_media":
        rect = "[198,2235][1025,2339]"
        for n in preview.iter():
            n.set("bounds", rect)
    elif mutation == "unknown":
        preview[1].set("content-desc", "Unknown")
    elif mutation == "interactive_child":
        preview[1].set("clickable", "true")
    else:
        preview[1].set("bounds", "[198,2236][1025,2340]")
    assert read_screen(etree.tostring(root), (1080, 2340)).rejected_posts
