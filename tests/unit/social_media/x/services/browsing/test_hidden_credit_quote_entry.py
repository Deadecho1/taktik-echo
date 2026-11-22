"""Unseen native source metadata can vanish while a quote enters below video."""

from dataclasses import replace

import pytest
from unit.x_fixtures import xml_fixture as document

from taktik.core.social_media.x.services.browsing.navigation import XError, _alignment
from taktik.core.social_media.x.ui.screen import read_screen


def screen(stage):
    return read_screen(document(f"hidden-credit-quote-entry-{stage}"), (1080, 2340))


def test_unseen_credit_loss_preserves_independent_text_and_video_motion():
    before, after = screen("before"), screen("after")
    old, new = before.posts[0], after.fragments[0]
    assert old.media[0].source_visibility.visible_bounds is None
    assert old.media[0].source_visibility.bounds[1] >= before.content_viewport[3]
    assert new.media[0].source_label is None
    assert new.body == old.body
    assert new.quoted_post.body is None and new.quoted_post.media
    assert _alignment(before, after, scrolling=True) == (1, True)


@pytest.mark.parametrize(
    "mutation",
    [
        "visible_credit",
        "missing_geometry",
        "above_viewport",
        "changed_credit",
        "body",
        "video_motion",
        "early_quote",
        "ambiguous",
        "uncommanded",
    ],
)
def test_unseen_credit_loss_cannot_replace_retained_content_or_movement(mutation):
    before, after = screen("before"), screen("after")
    old, new = before.posts[0], after.fragments[0]
    media = old.media[0]
    if mutation == "visible_credit":
        media = replace(
            media,
            source_visibility=replace(
                media.source_visibility, visible_bounds=media.source_visibility.bounds
            ),
        )
    elif mutation == "missing_geometry":
        media = replace(media, source_visibility=None)
    elif mutation == "above_viewport":
        media = replace(
            media,
            source_visibility=replace(
                media.source_visibility, bounds=(198, 0, 376, 100)
            ),
        )
    elif mutation == "changed_credit":
        new = replace(
            new, media=(replace(new.media[0], source_label="Different source"),)
        )
    elif mutation == "body":
        new = replace(new, body="Different body")
    elif mutation == "video_motion":
        m = new.media[0]
        new = replace(
            new,
            media=(
                replace(
                    m, visibility=replace(m.visibility, bounds=(176, 460, 1047, 1750))
                ),
            ),
        )
    elif mutation == "early_quote":
        q = new.quoted_post
        new = replace(
            new,
            quoted_post=replace(
                q, visibility=replace(q.visibility, bounds=(176, 1600, 1047, 2340))
            ),
        )
    old = replace(old, media=(media,))
    before = replace(before, posts=(old, old) if mutation == "ambiguous" else (old,))
    after = replace(after, fragments=(new,))
    with pytest.raises(XError):
        _alignment(before, after, scrolling=mutation != "uncommanded")
