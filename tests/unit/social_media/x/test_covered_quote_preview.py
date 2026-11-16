"""Retained outer text anchors preview entry while an old quoted header is covered."""

from dataclasses import replace
from pathlib import Path

import pytest
from taktik.core.social_media.x.services.browsing.navigation import XError, _alignment
from taktik.core.social_media.x.ui.screen import read_screen


def document(name):
    return (Path(__file__).parent / "fixtures" / f"{name}.xml").read_text()


def screens():
    return tuple(
        read_screen(document(f"covered-quote-preview-{s}"), (1080, 2340))
        for s in ("before", "after")
    )


def test_retained_body_and_video_prove_motion_despite_old_quote_header_cover():
    before, after = screens()
    assert not before.posts[0].quoted_post.header_visibility.unobscured
    assert before.posts[0].body == after.fragments[0].body
    assert after.fragments[0].quoted_post.media[0].description is None
    assert _alignment(before, after, scrolling=True) == (1, True)


@pytest.mark.parametrize(
    "mutation",
    [
        "body",
        "body_edge",
        "covered_edge",
        "clipped_edge",
        "video",
        "quote_body",
        "quote_header",
        "early_preview",
        "missing_body",
        "uncommanded",
    ],
)
def test_preview_entry_needs_an_independent_clear_body_edge_and_exact_video(mutation):
    before, after = screens()
    p = after.fragments[0]
    if mutation == "body":
        p = replace(p, body="Changed")
    elif mutation in {"body_edge", "covered_edge", "clipped_edge"}:
        v = p.body_visibility
        r = v.bounds
        if mutation == "body_edge":
            v = replace(v, bounds=(r[0], r[1], r[2], r[3] + 20))
        elif mutation == "covered_edge":
            v = replace(v, overlaps=(*v.overlaps, (r[0], r[3] - 2, r[2], r[3] + 10)))
        else:
            v = replace(v, visible_bounds=(r[0], 136, r[2], r[3] - 10))
        p = replace(p, body_visibility=v)
    elif mutation == "video":
        m = p.media[0]
        r = m.visibility.bounds
        p = replace(
            p,
            media=(
                replace(
                    m,
                    visibility=replace(
                        m.visibility, bounds=(r[0], r[1], r[2], r[3] + 20)
                    ),
                ),
            ),
        )
    elif mutation == "quote_body":
        p = replace(p, quoted_post=replace(p.quoted_post, body="Changed"))
    elif mutation == "quote_header":
        q = p.quoted_post
        v = q.header_visibility
        r = v.bounds
        p = replace(
            p,
            quoted_post=replace(
                q,
                header_visibility=replace(v, bounds=(r[0], r[1] + 20, r[2], r[3] + 20)),
            ),
        )
    elif mutation == "early_preview":
        q = p.quoted_post
        m = q.media[0]
        r = m.visibility.bounds
        p = replace(
            p,
            quoted_post=replace(
                q,
                media=(
                    replace(
                        m,
                        visibility=replace(
                            m.visibility, bounds=(r[0], 1700, r[2], r[3])
                        ),
                    ),
                ),
            ),
        )
    elif mutation == "missing_body":
        p = replace(p, body=None, body_visibility=None)
    after = replace(after, fragments=(p,))
    with pytest.raises(XError):
        _alignment(before, after, scrolling=mutation != "uncommanded")
