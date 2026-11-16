"""Offscreen quoted headers can reveal articles without authored body text."""

from dataclasses import replace
from pathlib import Path

import pytest
from taktik.core.social_media.x.services.browsing.navigation import XError, _alignment
from taktik.core.social_media.x.ui.screen import read_screen


def document(name):
    return (Path(__file__).parent / "fixtures" / f"{name}.xml").read_text()


def screens():
    return tuple(
        read_screen(document(f"header-article-entry-{s}"), (1080, 2340))
        for s in ("before", "after")
    )


def test_header_only_quote_reveals_an_article_without_inventing_body_text():
    before, after = screens()
    assert _alignment(before, after, scrolling=True) == (0, True)
    assert after.posts[0].quoted_post.body is None
    assert not after.observable_posts


@pytest.mark.parametrize(
    "mutation",
    ["body", "author", "labels", "header", "early_article", "video", "uncommanded"],
)
def test_article_entry_requires_original_text_and_explained_motion(mutation):
    before, after = screens()
    p = after.posts[0]
    q = p.quoted_post
    if mutation == "body":
        p = replace(p, body="Changed")
    elif mutation == "author":
        q = replace(q, author="@changed")
    elif mutation == "labels":
        q = replace(q, labels=())
    elif mutation == "header":
        q = replace(
            q,
            header_visibility=replace(
                q.header_visibility, bounds=(471, 1775, 744, 1824)
            ),
        )
    elif mutation == "early_article":
        m = q.media[0]
        q = replace(
            q,
            media=(
                replace(
                    m, visibility=replace(m.visibility, bounds=(176, 1740, 1047, 2340))
                ),
            ),
        )
    elif mutation == "video":
        m = p.media[0]
        p = replace(
            p,
            media=(
                replace(
                    m, visibility=replace(m.visibility, bounds=(176, 628, 1047, 1717))
                ),
            ),
        )
    with pytest.raises(XError):
        _alignment(
            before,
            replace(after, posts=(replace(p, quoted_post=q),)),
            scrolling=mutation != "uncommanded",
        )
