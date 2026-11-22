"""A composer overlap below the retained body start does not erase movement."""

from dataclasses import replace

import pytest
from unit.x_fixtures import xml_fixture as document

from taktik.core.social_media.x.services.browsing.navigation import XError, _alignment
from taktik.core.social_media.x.ui.screen import read_screen


def screens():
    return tuple(
        read_screen(document(f"composer-video-entry-{s}"), (1080, 2340))
        for s in ("before", "after")
    )


def test_video_entry_uses_clear_header_and_body_start_while_composer_covers_bottom():
    before, after = screens()
    assert _alignment(before, after, scrolling=True) == (1, True)
    assert not after.posts[0].observable
    assert after.posts[0].body_visibility.overlaps


@pytest.mark.parametrize(
    "mutation",
    [
        "cover_start",
        "clipped",
        "outside",
        "inaccessible",
        "body",
        "movement",
        "missing_neighbor",
        "missing_tail",
    ],
)
def test_partial_body_anchor_still_requires_exact_content_and_visible_start(mutation):
    before, after = screens()
    p = after.posts[0]
    v = p.body_visibility
    if mutation == "cover_start":
        v = replace(v, overlaps=((882, v.bounds[1], 1036, v.bounds[1] + 150),))
    elif mutation == "clipped":
        v = replace(v, clipped=True)
    elif mutation == "outside":
        v = replace(v, visible_bounds=None)
    elif mutation == "inaccessible":
        v = replace(v, accessible=False)
    elif mutation == "body":
        p = replace(p, body="Changed")
    elif mutation == "movement":
        x1, y1, x2, y2 = v.bounds
        v = replace(v, bounds=(x1, y1 + 30, x2, y2))
    p = replace(p, body_visibility=v)
    after = replace(after, posts=(p,))
    if mutation == "missing_neighbor":
        before = replace(before, posts=before.posts[:-1])
        after = replace(after, posts=())
    elif mutation == "missing_tail":
        after = replace(after, fragments=())
    with pytest.raises(XError):
        _alignment(before, after, scrolling=True)
