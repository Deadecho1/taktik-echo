"""Current Explore chrome remains recognizable when Settings has a feature badge."""

from copy import deepcopy

import pytest
from lxml import etree
from unit.paths import CORE
from unit.x_fixtures import xml_fixture

from taktik.core.social_media.x.ui.screen import read_screen

FIXTURE = CORE / "tests/unit/social_media/x/fixtures/search/explore-new-feature.xml"
SIZE = (1080, 2340)
LABEL = "Explore Settings. New feature available"


def test_captured_explore_feature_badge_preserves_search_navigation():
    screen = read_screen(xml_fixture(FIXTURE), SIZE)
    assert screen.kind == "explore", screen.reason
    assert screen.tab == "Explore"
    assert [c for c in screen.controls if c.label == "Search"]
    assert not screen.posts and screen.query is None


@pytest.mark.parametrize("mutation", ["unknown", "duplicate", "primary_conflict"])
def test_explore_feature_badge_does_not_relax_marker_checks(mutation):
    root = etree.ElementTree(etree.fromstring(xml_fixture(FIXTURE).encode())).getroot()
    settings = root.xpath(".//*[@content-desc=$label]", label=LABEL)[0]
    if mutation == "unknown":
        settings.set("content-desc", "Explore Settings: unknown variant")
    elif mutation == "duplicate":
        settings.getparent().append(deepcopy(settings))
    else:
        settings.getparent().set("resource-id", "Search")
    assert read_screen(etree.tostring(root), SIZE).kind == "unsupported"
