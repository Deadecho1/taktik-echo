"""Retained article text supplies travel after its quote header approaches the inset."""

from pathlib import Path
from unittest.mock import Mock

from unit.x_fixtures import xml_fixture

from taktik.core.shared.behavior.gesture import SWIPE_FLOOR_H
from taktik.core.shared.phone_interaction import Phone
from taktik.core.social_media.x.services.browsing.navigation import X
from taktik.core.social_media.x.ui.screen import read_screen

FIXTURES = Path(__file__).with_name("fixtures")


def document(name):
    return xml_fixture(FIXTURES / f"{name}.xml")


def test_quote_preview_text_preserves_a_reachable_scroll_budget():
    phone = Mock(spec=Phone)
    app = X(phone)
    before = read_screen(document("quote-preview-budget-before"), (1080, 2340))
    app._gesture(before, "up")
    call = phone.gesture.call_args
    region = call.args[2]
    distance = call.kwargs["distance"]
    summary = before.fragments[0].quoted_post.media[0].preview_text_visibility
    assert SWIPE_FLOOR_H * (region[3] - region[1]) <= distance
    assert distance <= (summary.bounds[3] - before.content_viewport[1]) * 0.75
