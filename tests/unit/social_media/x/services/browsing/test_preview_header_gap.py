"""A clipped quote header can leave a gap above its retained article preview."""

from dataclasses import replace

import pytest
from lxml import etree
from unit.paths import CORE
from unit.x_fixtures import xml_fixture

from taktik.core.social_media.x.services.browsing.navigation import XError, _alignment
from taktik.core.social_media.x.ui.screen import read_screen


def document(name):
    return xml_fixture(CORE / "tests/unit/social_media/x/fixtures" / f"{name}.xml")


def screens():
    return tuple(
        read_screen(document(f"preview-header-gap-{s}"), (1080, 2340))
        for s in ("before", "after")
    )


def test_preview_gap_retains_exact_text_and_independent_motion():
    before, after = screens()
    assert not after.rejected_posts
    assert _alignment(before, after, scrolling=True) == (0, True)
    assert len(after.fragments[0].preview_texts) == 2
    assert _alignment(after, after) == (0, False)


@pytest.mark.parametrize(
    "mutation", ["width", "bottom", "unclipped", "header_visible", "title"]
)
def test_preview_gap_still_requires_containment_and_projected_header_loss(mutation):
    before, after = screens()
    if mutation == "header_visible":
        old = before.fragments[0]
        q = old.quoted_post
        old = replace(
            old,
            quoted_post=replace(
                q,
                header_visibility=replace(
                    q.header_visibility, bounds=(567, 800, 827, 849)
                ),
            ),
        )
        with pytest.raises(XError):
            _alignment(replace(before, fragments=(old,)), after, scrolling=True)
        return
    root = etree.fromstring(document("preview-header-gap-after").encode())
    container = (
        root.xpath('//*[@resource-id="timeline_post"]')[0].getparent().getparent()[0]
    )
    preview = container[0][0][0]
    if mutation == "width":
        preview.set("bounds", "[177,86][1047,890]")
    elif mutation == "bottom":
        preview.set("bounds", "[176,86][1047,889]")
    elif mutation == "unclipped":
        preview.set("bounds", "[176,137][1047,890]")
    else:
        preview[1].set("text", "Changed")
    after = read_screen(etree.tostring(root), (1080, 2340))
    with pytest.raises(XError):
        _alignment(before, after, scrolling=True)
