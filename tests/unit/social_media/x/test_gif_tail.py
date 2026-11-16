"""Native GIF tails retain their media type and require verified movement."""

from dataclasses import replace
from pathlib import Path

import pytest
from taktik.core.social_media.x.services.browsing.navigation import XError, _alignment
from taktik.core.social_media.x.ui.screen import read_screen


def document(name):
    return (Path(__file__).parent / "fixtures" / f"{name}.xml").read_text()


def screens():
    return tuple(
        read_screen(document(f"gif-tail-{s}"), (1080, 2340))
        for s in ("before", "after")
    )


def test_gif_tail_keeps_native_type_after_author_and_body_leave():
    before, after = screens()
    assert _alignment(before, after, scrolling=True) == (1, True)
    assert after.fragments[0].media[0].kind == "gif"
    assert after.fragments[0].body is None
    assert _alignment(after, after) == (0, False)


@pytest.mark.parametrize("mutation", ["kind", "description", "edge", "body_visible"])
def test_gif_tail_rejects_changes_and_unexplained_body_loss(mutation):
    before, after = screens()
    p = after.fragments[0]
    m = p.media[0]
    if mutation == "kind":
        m = replace(m, kind="video")
    elif mutation == "description":
        m = replace(m, description="Video")
    elif mutation == "edge":
        m = replace(m, visibility=replace(m.visibility, bounds=(176, 111, 1047, 1300)))
    else:
        old = before.posts[0]
        old = replace(
            old,
            body_visibility=replace(old.body_visibility, bounds=(176, 536, 1047, 900)),
        )
        before = replace(before, posts=(old, *before.posts[1:]))
    with pytest.raises(XError):
        _alignment(
            before, replace(after, fragments=(replace(p, media=(m,)),)), scrolling=True
        )
