"""A translated compact quote can enter below an attributed bodyless video."""

from dataclasses import replace
from pathlib import Path

import pytest
from lxml import etree
from taktik.core.social_media.x.services.browsing.navigation import XError, _alignment
from taktik.core.social_media.x.ui.screen import read_screen


def document(name):
    return (Path(__file__).parent / "fixtures" / f"{name}.xml").read_text()


def screens():
    return tuple(
        read_screen(document(f"translated-compact-entry-{s}"), (1080, 2340))
        for s in ("before", "after")
    )


def test_translated_thumbnail_quote_stays_separate_from_the_bodyless_outer_video():
    before, after = screens()
    assert not after.rejected_posts
    post = after.posts[0]
    assert post.body is None
    assert post.quoted_post.body
    assert post.quoted_post.translation == "Translated from Indonesian"
    assert post.quoted_post.media[0].description == "1 more media item"
    assert _alignment(before, after, scrolling=True) == (0, True)


@pytest.mark.parametrize(
    "mutation", ["outside", "overlap", "interactive", "preview", "unknown", "extra"]
)
def test_translation_requires_the_validated_compact_layout(mutation):
    root = etree.fromstring(document("translated-compact-entry-after").encode())
    label = root.xpath('//*[@text="Translated from Indonesian"]')[0]
    preview = label.getnext()
    if mutation == "outside":
        label.set("bounds", "[170,2090][725,2133]")
    elif mutation == "overlap":
        label.set("bounds", "[283,2090][725,2160]")
    elif mutation == "interactive":
        label.set("clickable", "true")
    elif mutation == "preview":
        preview[0].set("text", "+2")
    elif mutation == "unknown":
        label.set("text", "Translated from ???")
    else:
        node = etree.fromstring(etree.tostring(label))
        node.set("text", "Unknown content")
        label.getparent().insert(label.getparent().index(preview), node)
    after = read_screen(etree.tostring(root), (1080, 2340))
    assert after.rejected_posts


@pytest.mark.parametrize(
    "mutation",
    [
        "author",
        "header_motion",
        "video_motion",
        "early_quote",
        "unclipped_video",
        "header_covered",
        "uncommanded",
    ],
)
def test_quote_entry_needs_retained_author_and_independent_video_motion(mutation):
    before, after = screens()
    p = after.posts[0]
    if mutation == "author":
        p = replace(p, author="@changed")
    elif mutation in {"header_motion", "header_covered"}:
        h = p.header_visibility
        r = h.bounds
        p = replace(
            p,
            header_visibility=replace(h, bounds=(r[0], r[1] + 20, r[2], r[3] + 20))
            if mutation == "header_motion"
            else replace(h, clipped=True),
        )
    elif mutation == "video_motion":
        m = p.media[0]
        r = m.visibility.bounds
        p = replace(
            p,
            media=(
                replace(
                    m,
                    visibility=replace(
                        m.visibility, bounds=(r[0], r[1] + 20, r[2], r[3])
                    ),
                ),
            ),
        )
    elif mutation == "early_quote":
        q = p.quoted_post
        p = replace(
            p,
            quoted_post=replace(
                q, visibility=replace(q.visibility, bounds=(176, 1700, 1047, 2340))
            ),
        )
    elif mutation == "unclipped_video":
        old = before.posts[0]
        m = old.media[0]
        old = replace(
            old,
            media=(
                replace(
                    m,
                    visibility=replace(
                        m.visibility, visible_bounds=m.visibility.bounds, clipped=False
                    ),
                ),
            ),
        )
        before = replace(before, posts=(old,))
    after = replace(after, posts=(p,))
    with pytest.raises(XError):
        _alignment(before, after, scrolling=mutation != "uncommanded")
