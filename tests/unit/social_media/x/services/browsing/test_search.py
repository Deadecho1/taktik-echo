"""Captured search screens exercised through the session-owned Phone interface."""

import pytest
from lxml import etree
from unit.paths import CORE

from taktik.core.shared.browsing import FeedEmpty
from taktik.core.shared.phone_interaction import (
    InteractionCancelled,
    InteractionError,
    Phone,
    Status,
    TextField,
)
from taktik.core.shared.ui.geometry import bounds
from taktik.core.social_media.x.services.browsing.browser import XBrowser
from taktik.core.social_media.x.services.browsing.navigation import (
    X,
    XError,
    _scroll_motion,
)
from taktik.core.social_media.x.ui.screen import PACKAGE, read_screen

FIXTURES = CORE / "tests/unit/social_media/x/fixtures/search"
SIZE = (1080, 2340)


def document(name):
    return (FIXTURES / f"{name}.xml").read_text()


def changed_query(xml, query):
    root = etree.fromstring(xml.encode())
    for node in root.xpath('.//*[@text="astronomy"]'):
        node.set("text", query)
    return etree.tostring(root, encoding="unicode")


def shifted_results(distance):
    root = etree.fromstring(document("search-latest").encode())
    containers = root.xpath(
        './/*[@resource-id="Search"]/node/node[@scrollable="true"]'
        '/node[@scrollable="true"]/node'
    )
    for container in containers:
        for node in container.iter():
            left, top, right, bottom = bounds(node)
            node.set(
                "bounds", f"[{left},{top + distance}][{right},{bottom + distance}]"
            )
    return etree.tostring(root, encoding="unicode")


class SearchReplay:
    def __init__(self):
        self.xml = document("for-you")
        self.events = []
        self.results = document("search-top")
        self.query_input = document("search-empty")
        self.explore = document("explore")
        self.latest = document("search-latest")
        self.scrolls = []
        self.typing_error = None
        self.typed_transform = lambda xml: xml
        self.tap_error = None
        self.enter_error = None
        self.tab_stuck = False
        self.now = 0
        self.closed = False
        self.phone = Phone(self, clock=lambda: self.now, sleep=self.sleep)

    def bind(self, phone):
        self.phone = phone

    def sleep(self, seconds):
        self.now += seconds

    def read(self, what):
        return {"hierarchy": self.xml, "size": SIZE, "app": {"package": PACKAGE}}[what]

    def tap(self, target, exclude, kind):
        screen = read_screen(self.xml, SIZE)
        matches = [
            c.label for c in screen.controls if c.visibility.visible_bounds == target
        ]
        assert len(matches) == 1, matches
        label = matches[0]
        self.events.append(("tap", label))
        if self.tap_error:
            raise self.tap_error
        transitions = {
            "Show navigation drawer": "account-drawer",
            "Close navigation menu": "for-you",
            "Home": "for-you",
            "Explore": "explore",
            "Search": "search-empty",
        }
        if label == "Latest":
            if not self.tab_stuck:
                self.xml = self.latest
        elif label in {"Search", "Back"}:
            self.xml = self.query_input
        elif label == "Explore":
            self.xml = self.explore
        else:
            self.xml = document(transitions[label])

    def command(self, name, value):
        self.events.append((name, value))
        if name == "enter":
            self.xml = self.results
            if self.enter_error:
                raise self.enter_error
        elif name == "back":
            self.xml = document("explore")

    def enter_text(self, field, text, submit):
        self.events.append(("type", field, text))
        assert field == TextField(PACKAGE, "SearchQuery")
        if self.typing_error:
            raise self.typing_error
        self.xml = self.typed_transform(
            changed_query(document("search-suggestions"), text)
        )
        submit().require()
        return text

    def gesture(self, intent, direction, region, distance, exclude):
        self.events.append(("gesture", intent, direction, region, distance, exclude))
        if self.scrolls:
            self.xml = self.scrolls.pop(0)

    def close(self):
        self.closed = True


@pytest.mark.parametrize(
    "tab,author", [("top", "@AstronomyVibes"), ("latest", "@dragonfiinch")]
)
def test_account_verified_search_types_and_verifies_exact_results(tab, author):
    replay = SearchReplay()
    app = X(replay.phone)
    post = app.start("fixture_owner", "search", query="astronomy", result_tab=tab)
    assert post.author == author
    assert app.observe() == post
    assert app.verified_account == "@fixture_owner"
    assert app.query == "astronomy" and app.result_tab == tab
    assert replay.events[:5] == [
        ("launch", PACKAGE),
        ("tap", "Show navigation drawer"),
        ("tap", "Close navigation menu"),
        ("tap", "Explore"),
        ("tap", "Search"),
    ]
    assert [event[0] for event in replay.events].count("type") == 1
    assert replay.events.count(("enter", None)) == 1
    assert not any(event[0] == "gesture" for event in replay.events)


def test_search_requires_matching_account_before_typing():
    replay = SearchReplay()
    app = X(replay.phone)
    with pytest.raises(XError, match="active X handle"):
        app.start("different_owner", "search", query="astronomy")
    assert app.verified_account is None
    assert not any(e[0] in {"type", "enter"} for e in replay.events)


@pytest.mark.parametrize(
    "query",
    [
        "",
        "   ",
        None,
        "two\nlines",
        "bad\x00query",
        "tab\tquery",
        "next\u0085line",
        "bad\u009fquery",
        "line\u2028separator",
        "paragraph\u2029separator",
    ],
)
def test_invalid_query_fails_before_device_interaction(query):
    replay = SearchReplay()
    with pytest.raises(ValueError):
        X(replay.phone).start("fixture_owner", "search", query=query)
    assert not replay.events


@pytest.mark.parametrize(
    "query", ["חתולים cats 🐈", "astronomy filter:quote", '"two words" -is:reply']
)
def test_search_preserves_unicode_and_native_query_operators(query):
    replay = SearchReplay()
    replay.results = changed_query(replay.results, query)
    app = X(replay.phone)
    assert app.start("fixture_owner", "search", query=query).observable
    assert app.query == query
    assert ("type", TextField(PACKAGE, "SearchQuery"), query) in replay.events


@pytest.mark.parametrize("problem", ["query", "tab", "home", "field"])
def test_unverified_results_never_become_browsing_context(problem):
    replay = SearchReplay()
    if problem == "query":
        replay.results = changed_query(replay.results, "another query")
    elif problem == "tab":
        replay.tab_stuck = True
    elif problem == "home":
        replay.results = document("for-you")
    elif problem == "field":
        replay.results = document("search-suggestions")
    app = X(replay.phone)
    with pytest.raises(XError):
        app.start("fixture_owner", "search", query="astronomy", result_tab="latest")
    assert app.verified_account is None and app._screen is None
    assert replay.events.count(("enter", None)) == 1
    assert [e[0] for e in replay.events].count("type") == 1
    assert not any(e[0] == "gesture" for e in replay.events)


@pytest.mark.parametrize("problem", ["focus", "scope", "query"])
def test_submission_rechecks_x_screen_context_after_typing(problem):
    replay = SearchReplay()

    def changed(xml):
        root = etree.fromstring(xml.encode())
        if problem == "scope":
            root.xpath('.//*[@resource-id="SearchQuery"]')[0].set(
                "resource-id", "Other"
            )
        else:
            field = root.xpath('.//*[@class="android.widget.EditText"]')[0]
            field.set(
                "focused" if problem == "focus" else "text",
                "false" if problem == "focus" else "other",
            )
        return etree.tostring(root, encoding="unicode")

    replay.typed_transform = changed
    app = X(replay.phone)
    with pytest.raises(InteractionError, match="nothing submitted"):
        app.start("fixture_owner", "search", query="astronomy")
    assert app.verified_account is None
    assert ("enter", None) not in replay.events


@pytest.mark.parametrize("problem", ["typing", "tap", "submission", "cancel"])
def test_search_execution_failure_is_not_retried_and_cleanup_remains_available(problem):
    replay = SearchReplay()
    if problem == "typing":
        replay.typing_error = OSError("typing transport failed")
    elif problem == "tap":
        replay.tap_error = OSError("tap reply lost")
    elif problem == "submission":
        replay.enter_error = OSError("enter reply lost")
    else:
        replay.typing_error = InteractionCancelled("cancelled")
    app = X(replay.phone)
    with pytest.raises(
        InteractionCancelled if problem == "cancel" else InteractionError
    ) as caught:
        app.start("fixture_owner", "search", query="astronomy")
    if problem != "cancel":
        assert caught.value.result.status == Status.UNCERTAIN
    assert app.verified_account is None
    assert [e[0] for e in replay.events].count("type") <= 1
    assert replay.events.count(("enter", None)) == (1 if problem == "submission" else 0)
    replay.phone.close().require()
    assert replay.closed and replay.events[-1] == ("home", None)


def test_result_advancement_reuses_observable_posts_and_verified_scroll_geometry():
    replay = SearchReplay()
    replay.latest = shifted_results(350)
    replay.scrolls = [document("search-latest")]
    app = X(replay.phone)
    assert (
        app.start(
            "fixture_owner", "search", query="astronomy", result_tab="latest"
        ).author
        == "@dragonfiinch"
    )
    assert app.advance().author == "@SzandraDMLLP"
    assert not any(e[0] == "gesture" for e in replay.events)
    assert app.advance().author == "@Astronomy1world"
    gestures = [e for e in replay.events if e[0] == "gesture"]
    assert len(gestures) == 1
    _, intent, direction, region, distance, exclusions = gestures[0]
    assert intent == "scroll" and direction == "up"
    assert region[1] >= 444 and region[3] <= 2120
    assert distance > 0 and exclusions
    assert app.observe().author == "@Astronomy1world"


@pytest.mark.parametrize("change", ["query", "tab", "screen"])
def test_uncommanded_result_context_changes_stop_before_a_gesture(change):
    replay = SearchReplay()
    app = X(replay.phone)
    app.start("fixture_owner", "search", query="astronomy")
    replay.xml = {
        "query": changed_query(replay.results, "other"),
        "tab": replay.latest,
        "screen": document("for-you"),
    }[change]
    with pytest.raises(XError, match="verified search"):
        app.advance()
    assert app.verified_account is None
    assert not any(e[0] == "gesture" for e in replay.events)


def test_stationary_result_scrolling_is_bounded_and_does_not_claim_progress():
    replay = SearchReplay()
    app = X(replay.phone)
    app.start("fixture_owner", "search", query="astronomy")
    with pytest.raises(XError):
        app.advance()
    assert app.verified_account is None
    assert 1 <= len([e for e in replay.events if e[0] == "gesture"]) <= 8


@pytest.mark.parametrize("stage", ["framing", "advancing"])
def test_leaving_search_after_a_gesture_stops_without_home_restoration(stage):
    replay = SearchReplay()
    replay.scrolls = [document("for-you")]
    app = X(replay.phone)
    if stage == "framing":
        replay.results = shifted_results(1400)
        with pytest.raises(XError, match="verified search"):
            app.start("fixture_owner", "search", query="astronomy", result_tab="latest")
    else:
        app.start("fixture_owner", "search", query="astronomy")
        with pytest.raises(XError, match="verified search"):
            app.advance()
    assert app.verified_account is None
    assert len([e for e in replay.events if e[0] == "gesture"]) == 1


def test_native_search_movement_requires_the_same_exact_query_and_tab():
    before = read_screen(shifted_results(350), SIZE)
    after = read_screen(document("search-latest"), SIZE)
    assert _scroll_motion(before, after) == -350
    for xml in (
        changed_query(document("search-latest"), "other"),
        document("search-top"),
    ):
        with pytest.raises(XError, match="same feed context"):
            _scroll_motion(before, read_screen(xml, SIZE))


def test_missing_search_results_are_not_reported_as_a_verified_empty_feed():
    replay = SearchReplay()
    root = etree.fromstring(replay.results.encode())
    posts = root.xpath(
        './/*[@resource-id="Search"]/node/node[@scrollable="true"]'
        '/node[@scrollable="true"]'
    )[0]
    for child in list(posts):
        posts.remove(child)
    replay.results = etree.tostring(root, encoding="unicode")
    app = X(replay.phone)
    with pytest.raises(XError):
        app.start("fixture_owner", "search", query="astronomy")
    assert app.verified_account is None
    assert not any(e[0] == "gesture" for e in replay.events)


def test_native_empty_search_finishes_without_scrolling_or_an_invented_post():
    replay = SearchReplay()
    replay.results = document("no-results")
    browser = XBrowser(replay.phone, {"search"})
    browser.start("fixture_owner", "search", "zzqtaktiksearch20261117qxzz")
    with pytest.raises(FeedEmpty):
        browser.observe()
    assert browser.browser.advance() is None
    assert browser.browsing_valid
    assert not any(e[0] == "gesture" for e in replay.events)


def test_explicit_recovery_reverifies_account_and_retains_query_and_tab():
    replay = SearchReplay()
    app = X(replay.phone)
    app.start("fixture_owner", "search", query="astronomy", result_tab="latest")
    replay.xml = document("for-you")
    with pytest.raises(XError):
        app.observe()
    assert app.recover().author == "@dragonfiinch"
    assert app.query == "astronomy" and app.result_tab == "latest"
    assert replay.events.count(("tap", "Show navigation drawer")) == 2


def test_standalone_search_round_trip_uses_captured_back_control_and_reverifies_account():
    replay = SearchReplay()
    replay.results = document("results-standalone")
    replay.query_input = document("search-standalone")
    replay.explore = document("explore-new-feature")
    replay.typed_transform = lambda xml: xml.replace(
        'resource-id="MainLanding"', 'resource-id=""'
    )
    app = X(replay.phone)
    assert app.start("fixture_owner", "search", query="astronomy").observable
    assert app.observe().observable
    assert app.recover().observable
    assert replay.events.count(("tap", "Back")) == 1
    assert replay.events.count(("tap", "Show navigation drawer")) == 2
    assert app.verified_account == "@fixture_owner"


@pytest.mark.parametrize("wrong_query", [False, True])
def test_submitted_search_restores_a_retained_collapsed_header_before_verifying_query(
    wrong_query,
):
    replay = SearchReplay()
    replay.results = document("results-collapsed-after-scroll")
    expanded = document("results-expanded-before-scroll")
    replay.scrolls = [changed_query(expanded, "other") if wrong_query else expanded]
    app = X(replay.phone)
    if wrong_query:
        with pytest.raises(XError, match="query"):
            app.start("fixture_owner", "search", query="astronomy")
        assert app.verified_account is None
    else:
        assert app.start("fixture_owner", "search", query="astronomy").observable
        assert app._screen.query == "astronomy"
    gestures = [e for e in replay.events if e[0] == "gesture"]
    assert len(gestures) == 1 and gestures[0][2] == "down"
    assert replay.events.count(("enter", None)) == 1


def test_search_header_restore_is_bounded_without_resubmitting_the_query():
    replay = SearchReplay()
    replay.results = document("results-collapsed-after-scroll")
    app = X(replay.phone)
    with pytest.raises(XError):
        app.start("fixture_owner", "search", query="astronomy")
    assert app.verified_account is None
    assert len([e for e in replay.events if e[0] == "gesture"]) == 8
    assert replay.events.count(("enter", None)) == 1


def test_browser_search_transitions_preserve_targets_and_observation_context():
    replay = SearchReplay()
    browser = XBrowser(replay.phone, {"for_you", "search"})
    browser.start("fixture_owner", "for_you")
    browser.transition("search", "astronomy")
    observation = browser.observe()
    assert observation.workflow == "search"
    assert observation.post_context["search_query"] == "astronomy"
    assert observation.post_context["search_tab"] == "top"
    events = list(replay.events)
    browser.transition("search", "astronomy")
    assert browser.observe().identity == observation.identity
    assert replay.events == events
    replay.results = changed_query(replay.results, "stars")
    browser.transition("search", "stars")
    assert browser.observe().identity != observation.identity
    assert browser.target == "stars"
    assert replay.events.count(("tap", "Show navigation drawer")) == 3
    browser.transition("for_you")
    assert browser.observe().workflow == "for_you"
    assert replay.events.count(("tap", "Show navigation drawer")) == 4


def test_browser_can_change_only_result_tab_and_recover_that_tab():
    replay = SearchReplay()
    browser = XBrowser(replay.phone, {"search"})
    browser.start("fixture_owner", "search", "astronomy")
    original = browser.observe()
    browser.transition("search", "astronomy", search_tab="latest")
    latest = browser.observe()
    assert latest.post_context["search_tab"] == "latest"
    assert latest.username == "dragonfiinch"
    assert latest.identity != original.identity
    events = list(replay.events)
    browser.transition("search", "astronomy", search_tab="latest")
    assert replay.events == events
    browser.recover()
    recovered = browser.observe()
    assert recovered.post_context["search_tab"] == "latest"
    assert recovered.identity != latest.identity
    assert replay.events.count(("tap", "Show navigation drawer")) == 3


@pytest.mark.parametrize("workflow,tab", [("search", "people"), ("for_you", "latest")])
def test_browser_rejects_invalid_tab_before_touching_phone(workflow, tab):
    replay = SearchReplay()
    browser = XBrowser(replay.phone, {"for_you", "search"})
    with pytest.raises(ValueError, match="result tab"):
        browser.start("fixture_owner", workflow, "astronomy", search_tab=tab)
    assert not replay.events


@pytest.mark.parametrize(
    "keyboard",
    ["com.google.android.inputmethod.latin", "com.alexal1.adbkeyboard", None],
)
def test_query_reader_handles_supported_keyboard_lifecycle(keyboard):
    root = etree.fromstring(document("search-suggestions").encode())
    window = root.xpath('./node[@package="com.google.android.inputmethod.latin"]')[0]
    if keyboard is None:
        root.remove(window)
    else:
        window.set("package", keyboard)
    screen = read_screen(etree.tostring(root), SIZE)
    assert screen.kind == "search_input"
    assert screen.query == "astronomy"
    assert screen.query_field == TextField(PACKAGE, "SearchQuery")
