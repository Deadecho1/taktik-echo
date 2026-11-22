"""A clipped quoted article can enter before its title is in the hierarchy."""

from dataclasses import replace

import pytest
from unit.x_fixtures import xml_fixture as document

from taktik.core.social_media.x.services.browsing.navigation import XError, _alignment
from taktik.core.social_media.x.ui.screen import read_screen


def screens():
    return tuple(
        read_screen(document(f"blank-quoted-preview-{s}"), (1080, 2340))
        for s in ("before", "after")
    )


def test_blank_article_enters_with_retained_text_and_independent_motion():
    before, after = screens()
    assert _alignment(before, after, scrolling=True) == (1, True)
    assert not after.observable_posts
    assert not hasattr(after.fragments[0], "author")
    preview = after.fragments[0].quoted_post.media[0]
    assert preview.description is preview.preview_text is None


@pytest.mark.parametrize(
    "mutation",
    [
        "outer_body",
        "quote_body",
        "quote_author",
        "quote_labels",
        "video",
        "header",
        "early_preview",
        "preview_width",
        "missing_title_geometry",
        "unclipped_quote",
        "unexplained_header_loss",
        "duplicate",
        "uncommanded",
    ],
)
def test_blank_preview_cannot_replace_independent_continuity_evidence(mutation):
    before, after = screens()
    p = after.fragments[0]
    q = p.quoted_post
    m = q.media[0]
    if mutation == "outer_body":
        p = replace(p, body="Changed")
    elif mutation == "quote_body":
        q = replace(q, body="Changed")
    elif mutation == "quote_author":
        q = replace(q, author="@changed")
    elif mutation == "quote_labels":
        q = replace(q, labels=())
    elif mutation == "video":
        video = p.media[0]
        p = replace(
            p,
            media=(
                replace(
                    video,
                    visibility=replace(video.visibility, bounds=(176, 414, 1047, 1523)),
                ),
            ),
        )
    elif mutation == "header":
        q = replace(
            q,
            header_visibility=replace(
                q.header_visibility, bounds=(457, 1541, 661, 1590)
            ),
        )
    elif mutation == "early_preview":
        q = replace(
            q,
            media=(
                replace(
                    m, visibility=replace(m.visibility, bounds=(176, 1740, 1047, 2340))
                ),
            ),
        )
    elif mutation == "preview_width":
        q = replace(
            q,
            media=(
                replace(
                    m, visibility=replace(m.visibility, bounds=(196, 1961, 1047, 2340))
                ),
            ),
        )
    elif mutation == "missing_title_geometry":
        q = replace(q, media=(replace(m, description="Unlocated title"),))
    elif mutation == "unclipped_quote":
        old = before.posts[0]
        quote = old.quoted_post
        before = replace(
            before,
            posts=(
                replace(
                    old,
                    quoted_post=replace(
                        quote,
                        visibility=replace(
                            quote.visibility, visible_bounds=quote.visibility.bounds
                        ),
                    ),
                ),
            ),
        )
    elif mutation == "unexplained_header_loss":
        old = before.posts[0]
        before = replace(
            before,
            posts=(
                replace(
                    old,
                    header_visibility=replace(
                        old.header_visibility, bounds=(176, 700, 1000, 800)
                    ),
                ),
            ),
        )
    elif mutation == "duplicate":
        before = replace(before, posts=(*before.posts, before.posts[0]))
    after = replace(after, fragments=(replace(p, quoted_post=q),))
    with pytest.raises(XError):
        _alignment(before, after, scrolling=mutation != "uncommanded")
