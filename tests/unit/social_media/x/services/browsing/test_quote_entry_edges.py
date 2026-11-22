"""Quote entry retains clear body starts and may follow newly revealed media."""

from dataclasses import replace

import pytest
from unit.paths import CORE
from unit.x_fixtures import xml_fixture

from taktik.core.social_media.x.services.browsing.navigation import XError, _alignment
from taktik.core.social_media.x.ui.screen import read_screen


def document(name):
    return xml_fixture(CORE / "tests/unit/social_media/x/fixtures" / f"{name}.xml")


def screens(case):
    return tuple(
        read_screen(document(f"{case}-{s}"), (1080, 2340)) for s in ("before", "after")
    )


@pytest.mark.parametrize("case", ["quote-header-body-edge", "video-and-quote-entry"])
def test_recorded_verified_quote_entry_remains_supported(case):
    assert _alignment(*screens(case), scrolling=True)[1]


@pytest.mark.parametrize("case", ["quote-header-body-edge", "video-and-quote-entry"])
@pytest.mark.parametrize("mutation", ["body", "header", "quote_entry"])
def test_quote_entry_requires_original_body_header_and_projected_new_content(
    case, mutation
):
    before, after = screens(case)
    p = after.posts[-1]
    if mutation == "body":
        p = replace(p, body="Changed", content_key="changed")
    elif mutation == "header":
        x1, y1, x2, y2 = p.header_visibility.bounds
        p = replace(
            p,
            header_visibility=replace(
                p.header_visibility, bounds=(x1, y1 + 20, x2, y2 + 20)
            ),
        )
    else:
        q = p.quoted_post
        if q.body_visibility:
            q = replace(
                q,
                body_visibility=replace(
                    q.body_visibility, bounds=(209, 1400, 1014, 2100)
                ),
            )
        else:
            q = replace(
                q,
                visibility=replace(
                    q.visibility,
                    bounds=(176, 1300, 1047, 2340),
                    visible_bounds=(176, 1300, 1047, 2230),
                ),
            )
        p = replace(p, quoted_post=q)
    with pytest.raises(XError):
        _alignment(before, replace(after, posts=(*after.posts[:-1], p)), scrolling=True)
