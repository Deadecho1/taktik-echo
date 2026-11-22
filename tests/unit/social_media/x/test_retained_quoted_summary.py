"""A quoted article can reveal summary text after the outer body is already gone."""

from dataclasses import replace
from pathlib import Path

import pytest
from unit.x_fixtures import xml_fixture

from taktik.core.social_media.x.services.browsing.navigation import XError, _alignment
from taktik.core.social_media.x.ui.screen import read_screen


def document(name):
    return xml_fixture(Path(__file__).parent / "fixtures" / f"{name}.xml")


def screens():
    return tuple(
        read_screen(document(f"retained-quoted-summary-{s}"), (1080, 2340))
        for s in ("before", "after")
    )


def test_summary_enters_with_retained_quoted_body_and_independent_video_motion():
    before, after = screens()
    assert before.fragments[0].body is after.fragments[0].body is None
    assert _alignment(before, after, scrolling=True) == (0, True)


@pytest.mark.parametrize(
    "mutation",
    ["quote_body", "quote_author", "video", "header", "summary_entry", "outer_body"],
)
def test_summary_entry_requires_original_quote_and_consistent_geometry(mutation):
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
                    m, visibility=replace(m.visibility, bounds=(176, 0, 1047, 780))
                ),
            ),
        )
    elif mutation == "header":
        q = replace(
            q,
            header_visibility=replace(q.header_visibility, bounds=(567, 823, 830, 872)),
        )
    elif mutation == "summary_entry":
        m = q.media[0]
        q = replace(
            q,
            media=(
                replace(
                    m,
                    preview_text_visibility=replace(
                        m.preview_text_visibility, bounds=(209, 1700, 1014, 1916)
                    ),
                ),
            ),
        )
    else:
        p = replace(p, body="Invented outer body")
    with pytest.raises(XError):
        _alignment(
            before,
            replace(after, fragments=(replace(p, quoted_post=q),)),
            scrolling=True,
        )
