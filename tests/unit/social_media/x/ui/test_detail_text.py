"""Captured Android character positions distinguish visible text from full text."""

import pytest
from lxml import etree
from unit.social_media.x.ui.test_main_detail import SIZE, document

from taktik.core.social_media.x.services.browsing.inspection import _TextCoverage
from taktik.core.social_media.x.ui.screen import read_screen


def test_native_character_positions_expose_only_the_uncovered_caption_prefix():
    screen = read_screen(document("long-character-locations"), SIZE)
    detail = screen.detail
    coverage = _TextCoverage(detail)
    coverage.add(detail)
    text, complete = coverage.result()
    assert len(text) == 727 and not complete
    assert text == detail.main_post.body[:727]
    assert not detail.main_post.body_complete and not detail.main_post.observable
    assert len(detail.text.ranges) == 20
    assert all(
        r.visibility.unobscured and r.visibility.bounds[3] <= 2098
        for r in detail.text.ranges
    )
    assert detail.text.anchors[0] in screen.scroll_anchors


@pytest.mark.parametrize("change", ["length", "nan", "shape"])
def test_invalid_native_character_metadata_is_not_a_text_observation(change):
    root = etree.fromstring(document("long-character-locations").encode())
    body = next(n for n in root.iter() if len(n.get("text", "")) == 1857)
    values = body.get("taktik-character-locations").split(";")
    if change == "length":
        values.pop()
    elif change == "nan":
        values[0] = "nan,499,40,555"
    else:
        values[0] = "22,499"
    body.set("taktik-character-locations", ";".join(values))
    screen = read_screen(etree.tostring(root), SIZE)
    assert screen.detail is None


def test_utf16_surrogate_pairs_are_kept_as_one_character_range():
    root = etree.fromstring(document("long-character-locations").encode())
    body = next(n for n in root.iter() if len(n.get("text", "")) == 1857)
    body.set("text", "🚀" + body.get("text")[1:])
    values = body.get("taktik-character-locations").split(";")
    values.insert(0, values[0])
    body.set("taktik-character-locations", ";".join(values))
    detail = read_screen(etree.tostring(root), SIZE).detail
    coverage = _TextCoverage(detail)
    coverage.add(detail)
    assert len(coverage.result()[0]) == 727
    assert coverage.result()[0].startswith("🚀his")
