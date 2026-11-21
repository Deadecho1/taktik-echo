"""Translation leaves with the outer body while quoted media retains motion."""

from dataclasses import replace
from pathlib import Path

import pytest

from taktik.core.social_media.x.services.browsing.navigation import XError, _alignment
from taktik.core.social_media.x.ui.screen import read_screen


def document(name):
    return (Path(__file__).parent / "fixtures" / f"{name}.xml").read_text()


def screen(stage):
    return read_screen(document(f"translated-body-video-gap-{stage}"), (1080, 2340))


def test_disappeared_translation_stays_absent_in_unattributed_fragment():
    before, after = screen("before"), screen("after")
    assert before.posts[0].translation == "Translated from Indonesian"
    p = after.fragments[0]
    assert p.translation is p.body is None
    assert p.media[0].visibility.bounds[1] > after.content_viewport[1]
    assert _alignment(before, after, scrolling=True) == (1, True)


@pytest.mark.parametrize(
    "mutation",
    ["translation", "body_visible", "video_motion", "quote_motion", "uncommanded"],
)
def test_translation_loss_still_requires_projected_body_loss_and_motion(mutation):
    before, after = screen("before"), screen("after")
    a, b = before.posts[0], after.fragments[0]
    if mutation == "translation":
        b = replace(b, translation="Translated from French")
    elif mutation == "body_visible":
        a = replace(
            a, body_visibility=replace(a.body_visibility, bounds=(176, 399, 1047, 780))
        )
    elif mutation == "video_motion":
        m = b.media[0]
        b = replace(
            b,
            media=(
                replace(
                    m, visibility=replace(m.visibility, bounds=(176, 176, 1047, 1463))
                ),
            ),
        )
    elif mutation == "quote_motion":
        q = b.quoted_post
        b = replace(
            b,
            quoted_post=replace(
                q,
                header_visibility=replace(
                    q.header_visibility, bounds=(446, 1532, 738, 1581)
                ),
            ),
        )
    before = replace(before, posts=(a,))
    after = replace(after, fragments=(b,))
    with pytest.raises(XError):
        _alignment(before, after, scrolling=mutation != "uncommanded")
