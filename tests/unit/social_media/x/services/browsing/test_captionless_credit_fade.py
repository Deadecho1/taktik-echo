"""An ephemeral video credit can disappear while the same post keeps moving."""

from dataclasses import replace

import pytest
from unit.x_fixtures import xml_fixture as document

from taktik.core.social_media.x.services.browsing.navigation import XError, _alignment
from taktik.core.social_media.x.ui.screen import read_screen


def screen(stage):
    return read_screen(document(f"captionless-credit-fade-{stage}"), (1080, 2340))


def test_captured_credit_fade_and_entry_retain_alignment():
    assert _alignment(screen("before"), screen("after"), scrolling=True) == (0, True)
    assert screen("after").posts[0].media[0].source_label is None


@pytest.mark.parametrize(
    "mutation", ["author", "source", "video", "footer", "header", "body", "uncommanded"]
)
def test_credit_fade_requires_retained_identity_media_and_footer(mutation):
    before, after = screen("before"), screen("after")
    p = after.posts[0]
    m = p.media[0]
    if mutation == "author":
        p = replace(p, author="@changed")
    elif mutation == "source":
        p = replace(p, media=(replace(m, source_label="Changed credit"),))
    elif mutation == "video":
        p = replace(
            p,
            media=(
                replace(
                    m, visibility=replace(m.visibility, bounds=(176, 187, 1047, 1028))
                ),
            ),
        )
    elif mutation == "footer":
        t = p.actions[0]
        x1, y1, x2, y2 = t.visibility.bounds
        p = replace(
            p,
            actions=(
                replace(
                    t, visibility=replace(t.visibility, bounds=(x1, y1 + 20, x2, y2))
                ),
                *p.actions[1:],
            ),
        )
    elif mutation == "header":
        p = replace(
            p,
            header_visibility=replace(p.header_visibility, bounds=(176, 99, 876, 148)),
        )
    elif mutation == "body":
        p = replace(p, body="Unexpected text")
    after = replace(after, posts=(p, *after.posts[1:]))
    with pytest.raises(XError):
        _alignment(before, after, scrolling=mutation != "uncommanded")
