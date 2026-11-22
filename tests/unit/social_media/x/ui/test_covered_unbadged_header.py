"""A retained native name/age row stays unattributed under the known cover."""

from dataclasses import replace

import pytest
from lxml import etree
from unit.x_fixtures import xml_fixture as document

from taktik.core.social_media.x.services.browsing.navigation import XError, _alignment
from taktik.core.social_media.x.ui.screen import _missing_handle_header, read_screen


def screen(stage):
    return read_screen(document(f"covered-unbadged-header-{stage}"), (1080, 2340))


def test_known_cover_does_not_turn_native_missing_handle_into_an_author():
    before, after = screen("before"), screen("after")
    assert not after.rejected_posts
    fragment = after.fragments[-1]
    assert not hasattr(fragment, "author") and fragment.covered_handle is None
    assert fragment.body == before.fragments[-1].body
    assert fragment.covered_header_visibility.overlaps
    assert not after.observable_posts
    assert _alignment(before, after, scrolling=True) == (0, True)


def test_arbitrary_overlap_cannot_use_known_header_cover_exception():
    root = etree.fromstring(document("covered-unbadged-header-after").encode())
    header = root.xpath('//*[@resource-id="timeline_post"]')[0]
    cover = (389, 143, 691, 275)
    assert not _missing_handle_header(header, (0, 136, 1080, 2230), (cover,))


@pytest.mark.parametrize("mutation", ["age", "name", "interactive", "age_geometry"])
def test_cover_preserves_native_header_structure_requirements(mutation):
    root = etree.fromstring(document("covered-unbadged-header-after").encode())
    name, age = root.xpath('//*[@resource-id="timeline_post"]')[0]
    if mutation == "age":
        age.set("text", "Unknown")
    elif mutation == "name":
        name.set("text", "@partial...")
    elif mutation == "interactive":
        name.set("clickable", "true")
    else:
        age.set("bounds", "[806,210][876,257]")
    assert read_screen(etree.tostring(root), (1080, 2340)).rejected_posts


@pytest.mark.parametrize("mutation", ["body", "translation", "movement", "uncommanded"])
def test_covered_unattributed_content_still_requires_exact_movement(mutation):
    before, after = screen("before"), screen("after")
    p = after.fragments[-1]
    if mutation == "body":
        p = replace(p, body="Different body")
    elif mutation == "translation":
        p = replace(p, translation="Translated from French")
    elif mutation == "movement":
        v = p.body_visibility
        x1, y1, x2, y2 = v.bounds
        p = replace(p, body_visibility=replace(v, bounds=(x1, y1 + 20, x2, y2)))
    after = replace(after, fragments=(*after.fragments[:-1], p))
    with pytest.raises(XError):
        _alignment(before, after, scrolling=mutation != "uncommanded")
