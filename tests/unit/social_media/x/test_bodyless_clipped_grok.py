"""A clipped options target can survive beside the avatar of a bodyless video."""

from dataclasses import replace
from pathlib import Path

import pytest
from lxml import etree
from taktik.core.social_media.x.services.browsing.navigation import XError, _alignment
from taktik.core.social_media.x.ui.screen import read_screen


def document(name):
    return (Path(__file__).parent / "fixtures" / f"{name}.xml").read_text()


def test_clipped_grok_keeps_video_and_quote_unattributed():
    before, after = [
        read_screen(document(f"bodyless-clipped-grok-{s}"), (1080, 2340))
        for s in ("before", "after")
    ]
    assert not after.rejected_posts
    p = after.fragments[0]
    assert not hasattr(p, "author")
    assert p.body is None and p.media[0].kind == "video"
    assert p.quoted_post.translation == "Translated from Indonesian"
    assert _alignment(before, after, scrolling=True) == (1, True)


@pytest.mark.parametrize(
    "mutation",
    [
        "label",
        "class",
        "text",
        "disabled",
        "not_clickable",
        "scrollable",
        "nested",
        "missing_avatar",
        "unclipped",
        "wrong_edge",
        "video_gap",
    ],
)
def test_grok_prefix_requires_native_control_and_clipped_avatar_geometry(mutation):
    root = etree.fromstring(document("bodyless-clipped-grok-after").encode())
    grok = root.xpath('//*[@content-desc="Explain this post with Grok"]')[0]
    if mutation == "label":
        grok.set("content-desc", "Unknown control")
    elif mutation == "class":
        grok.set("class", "android.view.View")
    elif mutation == "text":
        grok.set("text", "Unexpected")
    elif mutation == "disabled":
        grok.set("enabled", "false")
    elif mutation == "not_clickable":
        grok.set("clickable", "false")
    elif mutation == "scrollable":
        grok.set("scrollable", "true")
    elif mutation == "nested":
        grok.append(etree.fromstring(etree.tostring(grok)))
    elif mutation == "missing_avatar":
        grok.getparent().remove(grok.getprevious())
    elif mutation == "unclipped":
        grok.set("bounds", "[879,136][959,165]")
    elif mutation == "wrong_edge":
        grok.set("bounds", "[879,46][950,165]")
    else:
        grok.set("bounds", "[879,46][959,160]")
    assert read_screen(etree.tostring(root), (1080, 2340)).rejected_posts


@pytest.mark.parametrize(
    "mutation",
    ["video", "quote", "quote_body", "old_header", "ambiguous", "uncommanded"],
)
def test_bodyless_header_loss_requires_independent_motion_and_projected_loss(mutation):
    before, after = [
        read_screen(document(f"bodyless-clipped-grok-{s}"), (1080, 2340))
        for s in ("before", "after")
    ]
    p = after.fragments[0]
    if mutation == "video":
        m = p.media[0]
        p = replace(
            p,
            media=(
                replace(
                    m, visibility=replace(m.visibility, bounds=(176, 165, 1047, 1492))
                ),
            ),
        )
    elif mutation == "quote":
        q = p.quoted_post
        p = replace(
            p,
            quoted_post=replace(
                q,
                header_visibility=replace(
                    q.header_visibility, bounds=(481, 1539, 726, 1588)
                ),
            ),
        )
    elif mutation == "quote_body":
        p = replace(p, quoted_post=replace(p.quoted_post, body="Changed quote"))
    elif mutation == "old_header":
        old = before.posts[0]
        before = replace(
            before,
            posts=(
                replace(
                    old,
                    header_visibility=replace(
                        old.header_visibility, bounds=(176, 900, 876, 949)
                    ),
                    author_visibility=replace(
                        old.author_visibility, bounds=(463, 900, 726, 949)
                    ),
                ),
            ),
        )
    elif mutation == "ambiguous":
        before = replace(before, posts=before.posts * 2)
    after = replace(after, fragments=(p,))
    with pytest.raises(XError):
        _alignment(before, after, scrolling=mutation != "uncommanded")
