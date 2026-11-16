"""A clipped avatar does not attribute its bodyless video-and-quote fragment."""

from pathlib import Path

import pytest
from lxml import etree
from taktik.core.social_media.x.services.browsing.navigation import _alignment
from taktik.core.social_media.x.ui.screen import read_screen


def document(name):
    return (Path(__file__).parent / "fixtures" / f"{name}.xml").read_text()


def test_clipped_avatar_preserves_an_unattributed_bodyless_video_and_quote():
    before, after = [
        read_screen(document(f"bodyless-clipped-avatar-{s}"), (1080, 2340))
        for s in ("before", "after")
    ]
    assert not after.rejected_posts
    p = after.fragments[0]
    assert p.body is None and p.media[0].kind == "video" and p.quoted_post.body
    assert not hasattr(p, "author")
    assert _alignment(before, after, scrolling=True) == (1, True)


@pytest.mark.parametrize(
    "mutation",
    [
        "unclipped",
        "overlap",
        "not_clickable",
        "text",
        "class",
        "nested",
        "disabled",
        "scrollable",
        "shape",
    ],
)
def test_only_a_native_clipped_avatar_beside_the_video_is_accepted(mutation):
    root = etree.fromstring(document("bodyless-clipped-avatar-after").encode())
    avatar = root.xpath(
        '//*[@class="android.widget.ImageView"][@bounds="[22,18][154,150]"]'
    )[0]
    if mutation == "unclipped":
        avatar.set("bounds", "[22,136][154,268]")
    elif mutation == "overlap":
        avatar.set("bounds", "[80,18][212,150]")
    elif mutation == "not_clickable":
        avatar.set("clickable", "false")
    elif mutation == "text":
        avatar.set("text", "Unknown")
    elif mutation == "class":
        avatar.set("class", "android.view.View")
    elif mutation == "nested":
        avatar.append(etree.fromstring(etree.tostring(avatar)))
    elif mutation == "disabled":
        avatar.set("enabled", "false")
    elif mutation == "scrollable":
        avatar.set("scrollable", "true")
    else:
        avatar.set("bounds", "[22,18][154,160]")
    assert read_screen(etree.tostring(root), (1080, 2340)).rejected_posts
