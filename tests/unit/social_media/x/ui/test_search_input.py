"""SearchQuery can own a standalone native window in X 12.42."""

from copy import deepcopy

import pytest
from lxml import etree
from unit.paths import CORE
from unit.x_fixtures import xml_fixture

from taktik.core.shared.phone_interaction import TextField
from taktik.core.shared.phone_interaction._fields import resolve_field
from taktik.core.social_media.x.ui.screen import PACKAGE, read_screen

FIXTURE = CORE / "tests/unit/social_media/x/fixtures/search/search-standalone.xml"
SIZE = (1080, 2340)


def test_standalone_search_capture_supplies_the_shared_scoped_field():
    xml = xml_fixture(FIXTURE)
    screen = read_screen(xml, SIZE)
    assert screen.kind == "search_input", screen.reason
    assert screen.query_field == TextField(PACKAGE, "SearchQuery")
    info = resolve_field(xml, SIZE, screen.query_field)
    assert info["text"] == screen.query == ""
    assert info["focused"]


@pytest.mark.parametrize(
    "mutation", ["duplicate", "conflict", "wrong_marker", "unfocused"]
)
def test_standalone_query_requires_unique_supported_screen_and_focused_field(mutation):
    root = etree.ElementTree(etree.fromstring(xml_fixture(FIXTURE).encode())).getroot()
    scope = root.xpath('.//*[@resource-id="SearchQuery"]')[0]
    if mutation == "duplicate":
        scope.getparent().append(deepcopy(scope))
    elif mutation == "conflict":
        other = deepcopy(scope)
        other.set("resource-id", "scaffold_home_tabbed")
        scope.getparent().append(other)
    elif mutation == "wrong_marker":
        scope.set("resource-id", "UnknownSearchQuery")
    else:
        scope.xpath('.//*[@class="android.widget.EditText"]')[0].set("focused", "false")
    assert read_screen(etree.tostring(root), SIZE).kind == "unsupported"
