"""Scheduled native sports cards preserve their date label without inference."""

import pytest
from lxml import etree
from unit.x_fixtures import xml_fixture as document

from taktik.core.social_media.x.services.browsing.navigation import _alignment
from taktik.core.social_media.x.ui.screen import read_screen


def screen():
    return read_screen(document("scheduled-sports-card-after"), (1080, 2340))


def test_scheduled_card_preserves_literal_teams_and_date_label():
    p = screen().posts[0]
    assert p.sports_card.teams == ("PHI", "BKN")
    assert p.sports_card.status == "Tue, Nov 17"
    assert p.advertising == "unknown"


def test_captured_schedule_entry_keeps_movement():
    before = read_screen(document("scheduled-sports-card-before"), (1080, 2340))
    assert _alignment(before, screen(), scrolling=True)[1]


@pytest.mark.parametrize(
    "status", ["Tue, Nov 0", "Tue, Nov 32", "Tuesday", "Tue, Nope 17"]
)
def test_unrecognized_schedule_labels_are_rejected(status):
    root = etree.fromstring(document("scheduled-sports-card-after").encode())
    root.xpath('//*[@text="Tue, Nov 17"]')[0].set("text", status)
    assert not read_screen(etree.tostring(root), (1080, 2340)).posts
