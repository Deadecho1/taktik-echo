"""A hidden search header retains context only across verified adapter scrolling."""

from dataclasses import replace
from unittest.mock import Mock

import pytest
from lxml import etree
from unit.paths import CORE
from unit.x_fixtures import SIZE, xml_fixture

from taktik.core.shared.phone_interaction import Phone, Result, Status
from taktik.core.social_media.x.services.browsing.navigation import (
    X,
    XError,
    _alignment,
)
from taktik.core.social_media.x.ui.screen import PACKAGE, read_screen

FIXTURES = CORE / "tests/unit/social_media/x/fixtures/search"


def document(stage):
    return xml_fixture(FIXTURES / f"results-{stage}-scroll.xml")


def app_at_expanded_results():
    before = read_screen(document("expanded-before"), SIZE)
    phone = Mock(spec=Phone)
    app = X(phone)
    app.timeline, app.query, app.result_tab = "search", "astronomy", "top"
    app.verified_account, app._expected = "@fixture_owner", "@fixture_owner"
    app._select(before, 0)
    return app, before


def test_captured_search_collapse_keeps_visible_tab_but_does_not_invent_query():
    screen = read_screen(document("collapsed-after"), SIZE)
    assert screen.kind == "search_results", screen.reason
    assert screen.collapsed and screen.query is None
    assert screen.tab == "Top"
    # The captured tab indicator extends below the row to y=331.
    assert screen.content_viewport == (0, 331, 1080, 2230)
    assert screen.observable_posts


def test_captured_collapse_requires_measured_movement_before_context_is_retained():
    app, before = app_at_expanded_results()
    after = read_screen(document("collapsed-after"), SIZE)
    result = app._advance_alignment(before, after, False)
    assert result[2] is True
    app._select(after, next(i for i, p in enumerate(after.posts) if p.observable))
    app.phone.read.side_effect = lambda what: {
        "app": {"package": PACKAGE},
        "size": SIZE,
        "hierarchy": document("collapsed-after"),
    }[what]
    assert app.observe().observable
    assert app.query == "astronomy"


@pytest.mark.parametrize(
    "problem", ["uncommanded", "tab", "query", "account", "stationary"]
)
def test_search_context_is_not_carried_into_an_unverified_collapse(problem):
    app, before = app_at_expanded_results()
    after = read_screen(document("collapsed-after"), SIZE)
    if problem == "uncommanded":
        with pytest.raises(XError):
            app._check_timeline(after, before)
        return
    if problem == "tab":
        after = replace(after, tab="Latest")
    elif problem == "query":
        before = replace(before, query="other query")
    elif problem == "account":
        app.verified_account = None
    else:
        after = replace(before, collapsed=True, query=None)
    with pytest.raises(XError):
        app._advance_alignment(before, after, False)


def test_expanded_tab_geometry_without_header_does_not_claim_collapse():
    root = etree.fromstring(document("expanded-before").encode())
    for label in ("Back", "Search"):
        node = root.xpath(".//*[@content-desc=$label]", label=label)[0]
        node.getparent().remove(node)
    assert read_screen(etree.tostring(root), SIZE).kind == "unsupported"


def test_reaching_home_from_collapsed_search_reveals_and_uses_back():
    app, before = app_at_expanded_results()
    collapsed = read_screen(document("collapsed-after"), SIZE)
    home = read_screen(xml_fixture(FIXTURES / "for-you.xml"), SIZE)
    app.phone.gesture.return_value = Result(Status.SUCCESS)
    app.phone.tap.return_value = Result(Status.SUCCESS)
    app._wait_for = Mock(side_effect=[before, home])
    assert app._reach_home(collapsed) == home
    app.phone.gesture.assert_called_once()
    assert app.phone.gesture.call_args.args[1] == "down"
    app.phone.tap.assert_called_once()


COVERAGE_FIXTURES = CORE / "tests/unit/social_media/x/fixtures/coverage"


def test_captured_clipped_video_reaches_a_verified_successor():
    documents = [
        xml_fixture(COVERAGE_FIXTURES / f"search-video-{name}.xml")
        for name in ("source", "move-1", "move-2", "successor")
    ]
    screens = [read_screen(xml, SIZE) for xml in documents]
    source = next(p for p in screens[0].posts if p.author == "@slash1sol")
    assert source.observable and source.body_visibility.unobscured
    assert source.media[0].visibility.bounds[3] > screens[0].content_viewport[3]
    for before, after, offset in zip(screens, screens[1:], (1, 0, 1)):
        assert _alignment(before, after, scrolling=True) == (offset, True)

    phone = Mock(spec=Phone)
    current = 0

    def read(what):
        return {
            "app": {"package": "com.twitter.android"},
            "size": SIZE,
            "hierarchy": documents[current],
        }[what]

    def gesture(*args, **kwargs):
        nonlocal current
        current += 1
        assert current < len(documents)
        return Result(Status.SUCCESS)

    phone.read.side_effect = read
    phone.gesture.side_effect = gesture
    app = X(phone)
    app.timeline, app.result_tab = "search", "top"
    app.query, app.verified_account = "astronomy filter:videos", "@fixture_owner"
    app._select(screens[0], screens[0].posts.index(source))

    successor = app.advance()

    assert successor.author == "@NightSkyToday"
    assert app.observe() == successor
    assert not app.navigation_gaps
    assert phone.gesture.call_count == 3
