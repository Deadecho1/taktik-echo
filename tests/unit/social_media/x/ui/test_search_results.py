"""Standalone search results retain query, tabs, Back, and safe viewport evidence."""

import pytest
from lxml import etree
from unit.paths import CORE

from taktik.core.social_media.x.services.browsing.navigation import scroll_region
from taktik.core.social_media.x.ui.screen import read_screen

FIXTURE = CORE / "tests/unit/social_media/x/fixtures/search/results-standalone.xml"
SIZE = (1080, 2340)


def test_captured_standalone_results_have_observable_posts_and_a_bounded_viewport():
    screen = read_screen(FIXTURE.read_text(), SIZE)
    assert screen.kind == "search_results", screen.reason
    assert screen.query == "astronomy" and screen.tab == "Top"
    assert screen.content_viewport == (0, 444, 1080, 2230)
    assert screen.observable_posts
    controls = {c.label for c in screen.controls}
    assert {"Search", "Back", "Latest"} <= controls
    assert "Home" not in controls
    region, _, exclusions = scroll_region(screen)
    assert 444 <= region[1] < region[3] <= 2230
    assert (0, 2230, 1080, 2340) in exclusions


@pytest.mark.parametrize(
    "mutation", ["composer", "back", "covered_back", "duplicate_marker"]
)
def test_standalone_result_shell_requires_captured_navigation_evidence(mutation):
    root = etree.parse(str(FIXTURE)).getroot()
    if mutation in {"composer", "back"}:
        node = root.xpath(
            ".//*[@content-desc=$label]",
            label="Post" if mutation == "composer" else "Back",
        )[0]
        node.getparent().remove(node)
    elif mutation == "covered_back":
        back = root.xpath('.//*[@content-desc="Back"]')[0]
        back.getparent().set("bounds", "[0,0][132,136]")
    else:
        scope = root.xpath('.//*[@resource-id="Search"]')[0]
        scope.getparent().set("resource-id", "SearchQuery")
    assert read_screen(etree.tostring(root), SIZE).kind == "unsupported"
