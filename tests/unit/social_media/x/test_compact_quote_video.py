"""The native compact video thumbnail belongs to its quoted text."""

from pathlib import Path

import pytest
from lxml import etree
from unit.x_fixtures import xml_fixture as document

from taktik.core.social_media.x.services.browsing.navigation import _alignment
from taktik.core.social_media.x.ui.screen import read_screen

FIXTURES = Path(__file__).with_name("fixtures")


def test_compact_quote_video_remains_media_with_its_own_quoted_body():
    before, after = [
        read_screen(document(f"compact-quote-video-{s}"), (1080, 2340))
        for s in ("before", "after")
    ]
    post = next(p for p in after.posts if p.author == "@fixture_4")
    assert post.quoted_post.author == "@fixture_4"
    assert post.quoted_post.media[0].kind == "video"
    assert post.quoted_post.body != post.body
    assert _alignment(before, after, scrolling=True) == (1, True)


@pytest.mark.parametrize(
    "mutation", ["play", "nested", "control", "overlap", "body_top", "outside"]
)
def test_compact_quote_video_rejects_unknown_children_and_geometry(mutation):
    root = etree.fromstring(document("compact-quote-video-after").encode())
    play = root.xpath('//*[@content-desc="play"]')[0]
    preview = play.getparent()
    if mutation == "play":
        play.set("content-desc", "Unknown")
    elif mutation == "nested":
        etree.SubElement(play, "node", text="Unknown")
    elif mutation == "control":
        play.set("clickable", "true")
    elif mutation == "outside":
        play.set("bounds", "[0,0][50,50]")
    else:
        body = preview.getnext()
        body.set(
            "bounds",
            "[300,1919][1025,2066]"
            if mutation == "overlap"
            else "[421,1900][1025,2066]",
        )
    screen = read_screen(etree.tostring(root), (1080, 2340))
    assert not any(p.author == "@fixture_4" for p in screen.posts)
