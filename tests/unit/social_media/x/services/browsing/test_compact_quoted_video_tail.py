"""A quoted thumbnail survives after the outer video and quoted text leave."""

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
        read_screen(document(f"compact-quoted-video-tail-{s}"), (1080, 2340))
        for s in ("before", "after")
    )


def test_quoted_video_tail_uses_neighbor_motion_and_explains_prior_content_loss():
    before, after = screens()
    p = after.fragments[0]
    assert p.body is None and p.quoted_post is None
    assert (
        p.media[0].visibility.bounds[::2]
        == before.fragments[0].quoted_post.media[0].visibility.bounds[::2]
    )
    assert _alignment(before, after, scrolling=True) == (0, True)


@pytest.mark.parametrize(
    "mutation",
    [
        "outer_video_visible",
        "quote_header_visible",
        "quote_body_visible",
        "outer_body_visible",
        "source",
        "horizontal",
        "missing_neighbors",
        "duplicate",
        "uncommanded",
    ],
)
def test_tail_cannot_discard_visible_content_or_infer_motion_without_neighbors(
    mutation,
):
    before, after = screens()
    p = before.fragments[0]
    q = p.quoted_post
    if mutation == "outer_video_visible":
        m = p.media[0]
        r = m.visibility.bounds
        p = replace(
            p,
            media=(
                replace(
                    m, visibility=replace(m.visibility, bounds=(r[0], r[1], r[2], 750))
                ),
            ),
        )
    elif mutation in {"quote_header_visible", "quote_body_visible"}:
        name = (
            "header_visibility"
            if mutation == "quote_header_visible"
            else "body_visibility"
        )
        v = getattr(q, name)
        r = v.bounds
        q = replace(q, **{name: replace(v, bounds=(r[0], r[1], r[2], 750))})
        p = replace(p, quoted_post=q)
    elif mutation == "outer_body_visible":
        p = replace(p, body="Retained", body_visibility=q.body_visibility)
        p = replace(
            p, body_visibility=replace(p.body_visibility, bounds=(176, 500, 1047, 750))
        )
    elif mutation in {"source", "horizontal"}:
        m = after.fragments[0].media[0]
        m = (
            replace(m, source_label="Changed")
            if mutation == "source"
            else replace(m, visibility=replace(m.visibility, bounds=(200, 0, 401, 190)))
        )
        after = replace(after, fragments=(replace(after.fragments[0], media=(m,)),))
    before = replace(before, fragments=(p, p) if mutation == "duplicate" else (p,))
    if mutation == "missing_neighbors":
        before, after = replace(before, posts=()), replace(after, posts=())
    with pytest.raises(XError):
        _alignment(before, after, scrolling=mutation != "uncommanded")
