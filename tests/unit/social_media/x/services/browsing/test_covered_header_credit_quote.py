"""Clear retained author/body anchors survive a partial outer-header cover."""

from dataclasses import replace

import pytest
from unit.x_fixtures import xml_fixture as document

from taktik.core.social_media.x.services.browsing.navigation import XError, _alignment
from taktik.core.social_media.x.ui.screen import read_screen


def screen(stage):
    return read_screen(document(f"covered-header-credit-quote-{stage}"), (1080, 2340))


def test_partial_header_cover_does_not_make_retained_content_observable():
    before, after = screen("before"), screen("after")
    old, new = before.posts[0], after.fragments[0]
    assert not old.observable and old.header_visibility.overlaps
    assert old.author_visibility.unobscured and old.body_visibility.unobscured
    assert new.media[0].source_label and new.quoted_post.translation
    assert new.body == old.body
    assert not new.quoted_post.observable
    assert _alignment(before, after, scrolling=True) == (1, True)


@pytest.mark.parametrize(
    "mutation",
    [
        "author_cover",
        "body_cover",
        "header_clipped",
        "changed_body",
        "video_motion",
        "early_credit",
        "early_quote",
        "ambiguous",
        "uncommanded",
    ],
)
def test_credit_and_quote_entry_requires_clear_anchors_and_projected_revelation(
    mutation,
):
    before, after = screen("before"), screen("after")
    old, new = before.posts[0], after.fragments[0]
    if mutation in {"author_cover", "body_cover"}:
        field = "author_visibility" if mutation == "author_cover" else "body_visibility"
        v = getattr(old, field)
        old = replace(old, **{field: replace(v, overlaps=(v.bounds,))})
    elif mutation == "header_clipped":
        v = old.header_visibility
        old = replace(old, header_visibility=replace(v, visible_bounds=None))
    elif mutation == "changed_body":
        new = replace(new, body="Changed content")
    elif mutation == "video_motion":
        m = new.media[0]
        new = replace(
            new,
            media=(
                replace(
                    m, visibility=replace(m.visibility, bounds=(176, 810, 1047, 2107))
                ),
            ),
        )
    elif mutation == "early_credit":
        m = new.media[0]
        new = replace(
            new,
            media=(
                replace(
                    m,
                    source_content=(),
                    source_visibility=replace(
                        m.source_visibility, bounds=(198, 1700, 531, 1832)
                    ),
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
    before = replace(before, posts=(old, old) if mutation == "ambiguous" else (old,))
    after = replace(after, fragments=(new,))
    with pytest.raises(XError):
        _alignment(before, after, scrolling=mutation != "uncommanded")
