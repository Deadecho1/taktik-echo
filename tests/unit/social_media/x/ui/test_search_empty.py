"""An exact native no-results panel proves emptiness; absent posts alone do not."""

import pytest
from lxml import etree
from unit.paths import CORE

from taktik.core.social_media.x.ui.screen import read_screen

FIXTURE = CORE / "tests/unit/social_media/x/fixtures/search/no-results.xml"
SIZE = (1080, 2340)
QUERY = "zzqtaktiksearch20261117qxzz"


def test_captured_native_no_results_state_is_bound_to_the_displayed_query():
    screen = read_screen(FIXTURE.read_text(), SIZE)
    assert screen.kind == "search_results", screen.reason
    assert screen.query == QUERY and screen.tab == "Top"
    assert screen.empty
    assert not screen.posts and not screen.rejected_posts


@pytest.mark.parametrize(
    "problem", ["query", "explanation", "structure", "interactive", "covered", "post"]
)
def test_no_results_claim_requires_exact_native_content_and_visibility(problem):
    root = etree.parse(str(FIXTURE)).getroot()
    title = root.xpath(".//*[@text=$text]", text=f"No results for “{QUERY}”")[0]
    panel = title.getparent()
    if problem == "query":
        title.set("text", "No results for “different query”")
    elif problem == "explanation":
        panel.remove(panel[1])
    elif problem == "structure":
        panel.set("class", "android.view.View")
    elif problem == "interactive":
        panel.set("clickable", "true")
    elif problem == "covered":
        title.set("bounds", "[66,2100][1014,2230]")
    else:
        etree.SubElement(
            panel,
            "node",
            attrib={
                "resource-id": "timeline_post",
                "package": "com.twitter.android",
                "bounds": "[0,500][1080,600]",
                "enabled": "true",
            },
        )
    assert not read_screen(etree.tostring(root), SIZE).empty
