"""A compact quoted video can enter partially through the capture bottom."""

import pytest
from lxml import etree
from unit.paths import CORE

from taktik.core.social_media.x.services.browsing.navigation import XError, _alignment
from taktik.core.social_media.x.ui.screen import read_screen


def document(name):
    return (CORE / "tests/unit/social_media/x/fixtures" / f"{name}.xml").read_text()


def test_clipped_compact_video_preserves_quote_and_verified_motion():
    before, after = [
        read_screen(document(f"clipped-compact-video-entry-{s}"), (1080, 2340))
        for s in ("before", "after")
    ]
    assert not after.rejected_posts
    quote = after.posts[0].quoted_post
    assert quote.translation == "Translated from Indonesian"
    assert quote.media[0].kind == "video"
    assert quote.media[0].visibility.bounds == (198, 2207, 399, 2340)
    assert not quote.body_complete
    assert _alignment(before, after, scrolling=True) == (0, True)
    with pytest.raises(XError):
        _alignment(before, after, scrolling=False)


@pytest.mark.parametrize(
    "mutation",
    [
        "unclipped",
        "parent_bottom",
        "too_tall",
        "control",
        "play_outside",
        "body_overlap",
        "media_bounds",
    ],
)
def test_nonsquare_video_requires_capture_clipping_and_native_children(mutation):
    root = etree.fromstring(document("clipped-compact-video-entry-after").encode())
    play = root.xpath('//*[@content-desc="play"]')[0]
    preview = play.getparent()
    if mutation in {"unclipped", "too_tall"}:
        rect = (
            "[198,2207][399,2225]"
            if mutation == "unclipped"
            else "[198,2107][399,2340]"
        )
        for n in (preview, preview[0], preview[1]):
            n.set("bounds", rect)
        if mutation == "unclipped":
            play.set("bounds", "[273,2209][332,2220]")
        else:
            preview.getnext().set("bounds", "[421,2107][1025,2340]")
    elif mutation == "parent_bottom":
        preview.getparent().set("bounds", "[176,2075][1047,2350]")
    elif mutation == "control":
        play.set("clickable", "true")
    elif mutation == "play_outside":
        play.set("bounds", "[273,2330][332,2350]")
    elif mutation == "body_overlap":
        preview.getnext().set("bounds", "[380,2207][1025,2340]")
    else:
        preview[0].set("bounds", "[198,2208][399,2340]")
    assert read_screen(etree.tostring(root), (1080, 2340)).rejected_posts
