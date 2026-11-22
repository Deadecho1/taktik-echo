"""Partially covered handle evidence survives while a quoted title enters."""

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
        read_screen(document(f"covered-handle-preview-{s}"), (1080, 2340))
        for s in ("before", "after")
    )


def test_partial_handle_proves_covered_header_during_quote_title_entry():
    before, after = screens()
    assert _alignment(before, after, scrolling=True) == (1, True)
    p = after.fragments[1]
    assert p.covered_handle.text == before.posts[0].author
    assert not hasattr(p, "author")
    assert not after.observable_posts


@pytest.mark.parametrize(
    "mutation",
    [
        "handle_text",
        "handle_start",
        "handle_end",
        "handle_vertical",
        "no_handle",
        "no_cover",
        "header",
        "quote",
        "footer_count",
        "uncommanded",
    ],
)
def test_partial_handle_requires_exact_retained_text_geometry_and_known_cover(mutation):
    before, after = screens()
    footer, p = after.fragments
    h = p.covered_handle
    if mutation == "handle_text":
        p = replace(p, covered_handle=replace(h, text="@changed"))
    elif mutation.startswith("handle_"):
        box = {
            "handle_start": (359, 221, 389, 270),
            "handle_end": (339, 221, 379, 270),
            "handle_vertical": (339, 231, 389, 280),
        }[mutation]
        p = replace(
            p, covered_handle=replace(h, visibility=replace(h.visibility, bounds=box))
        )
    elif mutation == "no_handle":
        p = replace(p, covered_handle=None)
    elif mutation == "no_cover":
        after = replace(after, overlaps=())
    elif mutation == "header":
        p = replace(
            p,
            covered_header_visibility=replace(
                p.covered_header_visibility, bounds=(176, 241, 876, 290)
            ),
        )
    elif mutation == "quote":
        p = replace(p, quoted_post=replace(p.quoted_post, author="@changed"))
    elif mutation == "footer_count":
        action, *rest = footer.actions
        footer = replace(footer, actions=(replace(action, count="Changed"), *rest))
    with pytest.raises(XError):
        _alignment(
            before,
            replace(after, fragments=(footer, p)),
            scrolling=mutation != "uncommanded",
        )
