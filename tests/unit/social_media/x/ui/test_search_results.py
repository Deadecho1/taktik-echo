"""Standalone search results retain query, tabs, Back, and safe viewport evidence."""

from copy import deepcopy

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


PASSAGE_FIXTURE = (
    CORE
    / "tests/unit/social_media/x/fixtures/coverage/pending-search-hidden-header.xml"
)


@pytest.mark.parametrize(
    "mutation",
    [
        "visible_header",
        "visible_control",
        "unknown_badge",
        "partial_handle",
        "interactive_name",
        "nested_name",
        "extra_content",
        "hidden_body",
        "interactive_body",
        "incomplete_translation",
        "unknown_control",
        "nonclipped_body",
        "wrapper_text",
        "wrapper_description",
    ],
)
def test_ambiguous_passage_never_enters_pending(mutation):
    root = etree.parse(str(PASSAGE_FIXTURE))
    header = root.xpath('//*[@resource-id="timeline_post"]')[0]
    container = header.getparent()
    body = container[-1]
    if mutation == "visible_header":
        header.set("bounds", "[176,301][876,350]")
    elif mutation == "visible_control":
        container[3].set("bounds", "[959,268][1080,392]")
    elif mutation == "unknown_badge":
        header[1].set("content-desc", "Unknown")
    elif mutation == "partial_handle":
        header[2].set("text", "@Sai600…")
    elif mutation == "interactive_name":
        header[0].set("clickable", "true")
    elif mutation == "nested_name":
        header[0].append(deepcopy(header[0]))
    elif mutation == "extra_content":
        container.append(deepcopy(body))
    elif mutation == "hidden_body":
        body.set("visible-to-user", "false")
    elif mutation == "interactive_body":
        body.set("clickable", "true")
    elif mutation == "incomplete_translation":
        container[5].set("text", "Translate")
    elif mutation == "unknown_control":
        container[3].set("content-desc", "Another action")
    elif mutation == "nonclipped_body":
        body.set("bounds", "[176,400][1047,2000]")
    elif mutation in {"wrapper_text", "wrapper_description"}:
        container.set(
            "text" if mutation == "wrapper_text" else "content-desc",
            "Unrecognized content",
        )

    screen = read_screen(etree.tostring(root), (1080, 2340))
    assert not screen.fragments and not screen.posts
    assert screen.rejected_posts
