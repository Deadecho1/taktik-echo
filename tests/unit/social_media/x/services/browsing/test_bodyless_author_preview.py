"""A captionless outer video can lose its author as a quoted article enters."""

from dataclasses import replace

import pytest
from unit.paths import CORE
from unit.x_fixtures import xml_fixture

from taktik.core.social_media.x.services.browsing.navigation import XError, _alignment
from taktik.core.social_media.x.ui.screen import read_screen


def document(name):
    return xml_fixture(CORE / "tests/unit/social_media/x/fixtures" / f"{name}.xml")


def screens():
    return tuple(
        read_screen(document(f"bodyless-author-preview-{s}"), (1080, 2340))
        for s in ("before", "after")
    )


def test_captionless_video_explains_author_loss_and_quote_preview_entry():
    before, after = screens()
    assert before.posts[0].body is after.fragments[0].body is None
    assert not before.posts[0].quoted_post.media
    assert after.fragments[0].quoted_post.media[0].kind == "preview"
    assert not hasattr(after.fragments[0], "author")
    assert _alignment(before, after, scrolling=True) == (1, True)


@pytest.mark.parametrize(
    "mutation",
    [
        "quote_body",
        "quote_author",
        "video",
        "header",
        "early_card",
        "outer_body",
        "visible_author",
        "uncommanded",
    ],
)
def test_captionless_preview_needs_independent_movement_and_explained_loss(mutation):
    before, after = screens()
    p = after.fragments[0]
    q = p.quoted_post
    if mutation == "quote_body":
        q = replace(q, body="Changed")
    elif mutation == "quote_author":
        q = replace(q, author="@changed")
    elif mutation == "video":
        m = p.media[0]
        p = replace(
            p,
            media=(
                replace(
                    m, visibility=replace(m.visibility, bounds=(176, 122, 1047, 1429))
                ),
            ),
        )
    elif mutation == "header":
        q = replace(
            q,
            header_visibility=replace(
                q.header_visibility, bounds=(407, 1487, 660, 1536)
            ),
        )
    elif mutation == "early_card":
        m = q.media[0]
        q = replace(
            q,
            media=(
                replace(
                    m, visibility=replace(m.visibility, bounds=(176, 1750, 1047, 2340))
                ),
            ),
        )
    elif mutation == "outer_body":
        p = replace(p, body="Invented outer body")
    elif mutation == "visible_author":
        old = before.posts[0]
        before = replace(
            before,
            posts=(
                replace(
                    old,
                    header_visibility=replace(
                        old.header_visibility, bounds=(176, 750, 876, 799)
                    ),
                ),
            ),
        )
    after = replace(after, fragments=(replace(p, quoted_post=q),))
    with pytest.raises(XError):
        _alignment(before, after, scrolling=mutation != "uncommanded")
