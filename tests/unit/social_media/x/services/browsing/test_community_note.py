"""Keep reader-supplied context separate across translated-header loss."""

from dataclasses import replace

import pytest
from unit.paths import CORE

from taktik.core.social_media.x.services.browsing.navigation import (
    XError,
    _alignment,
    scroll_region,
)
from taktik.core.social_media.x.ui.screen import read_screen

FIXTURES = CORE / "tests/unit/social_media/x/fixtures"


def screens():
    return tuple(
        read_screen(
            (FIXTURES / f"community-note-{stage}.xml").read_text(), (1080, 2340)
        )
        for stage in ("before", "after")
    )


def test_translated_header_loss_and_community_note_revelation():
    before, after = screens()
    assert not after.rejected_posts
    (fragment,) = after.fragments
    assert fragment.body == before.posts[0].body
    assert fragment.translation == before.posts[0].translation
    assert fragment.community_note.body.startswith("Fixture reader-supplied context")
    assert not hasattr(fragment, "author")
    assert _alignment(before, after, scrolling=True) == (1, True)
    assert scroll_region(after)[1] > 0


@pytest.mark.parametrize(
    "field",
    [
        "body",
        "translation",
        "title",
        "visibility",
        "header_visibility",
        "body_visibility",
        "missing",
    ],
)
@pytest.mark.parametrize("scrolling", [False, True])
def test_known_note_cannot_change_during_refresh(field, scrolling):
    _, before = screens()
    (fragment,) = before.fragments
    note = fragment.community_note
    if field == "missing":
        note = None
    elif field.endswith("visibility"):
        view = getattr(note, field)
        x1, y1, x2, y2 = view.bounds
        note = replace(note, **{field: replace(view, bounds=(x1, y1 + 20, x2, y2))})
    else:
        note = replace(note, **{field: "Changed"})
    after = replace(before, fragments=(replace(fragment, community_note=note),))
    with pytest.raises(XError):
        _alignment(before, after, scrolling=scrolling)


def test_note_revelation_must_project_below_the_prior_capture():
    before, after = screens()
    (fragment,) = after.fragments
    note = fragment.community_note
    x1, y1, x2, y2 = note.visibility.bounds
    note = replace(
        note, visibility=replace(note.visibility, bounds=(x1, y1 - 200, x2, y2))
    )
    after = replace(after, fragments=(replace(fragment, community_note=note),))
    with pytest.raises(XError):
        _alignment(before, after, scrolling=True)


def test_unchanged_note_refresh_cannot_claim_movement():
    _, screen = screens()
    assert _alignment(screen, screen) == (0, False)
    assert _alignment(screen, screen, scrolling=True) == (0, False)
