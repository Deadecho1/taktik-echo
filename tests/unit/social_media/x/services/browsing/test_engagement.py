"""Native fixture replays verify single-attempt X engagements through Phone."""

import pytest
from lxml import etree
from taktik.core.shared.phone_interaction import (
    InteractionCancelled,
    InteractionError,
    Status,
)
from taktik.core.social_media.x.services.browsing.browser import XBrowser, post_context
from taktik.core.social_media.x.services.browsing.navigation import (
    X,
    XError,
    _alignment,
)
from taktik.core.social_media.x.ui.screen import read_screen
from unit.paths import CORE
from unit.social_media.x.services.browsing.test_search import SearchReplay
from unit.social_media.x.ui.test_inspection_screen import SIZE
from unit.social_media.x.ui.test_inspection_screen import (
    engagement_document as document,
)

QUERY = "from:NASA -filter:replies"


class EngagementReplay(SearchReplay):
    def __init__(self):
        super().__init__()
        self.results = self.latest = document("source")
        self.after = {"Like": document("liked"), "Bookmark": document("bookmarked")}
        self.engagement_error = None
        self.pending = []
        self.intermediate = None
        self.following = False
        self.menu_author = "@NASA"
        self.timeline_xml = None
        self.menu_error = None
        self.removal = None
        self.home_menu = document("home-options")

    def read(self, what):
        if what == "hierarchy" and self.pending:
            self.xml = self.pending.pop(0)
        return super().read(what)

    def tap(self, target, exclude, kind):
        screen = read_screen(self.xml, SIZE)
        if screen.kind == "post_options":
            labels = [
                t.label
                for t in screen.controls
                if t.visibility.visible_bounds is not None
                and t.visibility.visible_bounds[0]
                <= target[0]
                < target[2]
                <= t.visibility.visible_bounds[2]
                and t.visibility.visible_bounds[1]
                <= target[1]
                < target[3]
                <= t.visibility.visible_bounds[3]
            ]
            assert len(labels) == 1
            label = labels[0]
            if label == "Close sheet":
                self.events.append(("menu", "close"))
                self.xml = self.timeline_xml
            else:
                if label == "Not interested in Post":
                    self.events.append(("engage", "not_interested"))
                    self.xml = self.removal or document("feedback")
                    if self.engagement_error:
                        raise self.engagement_error
                    return
                assert label in {"Follow @NASA", "Unfollow @NASA"}
                self.events.append(("engage", label.split()[0].lower()))
                self.following = label.startswith("Follow ")
                self.xml = (
                    self.timeline_xml
                    if self.following
                    else self.removal or document("unfollowed")
                )
                if self.engagement_error:
                    raise self.engagement_error
            return
        options = [
            t
            for p in screen.posts
            for t in p.targets
            if t.label == "Post options"
            and t.visibility.visible_bounds is not None
            and t.visibility.visible_bounds[0]
            <= target[0]
            < target[2]
            <= t.visibility.visible_bounds[2]
            and t.visibility.visible_bounds[1]
            <= target[1]
            < target[3]
            <= t.visibility.visible_bounds[3]
        ]
        if options:
            assert len(options) == 1
            left, _, right, _ = options[0].visibility.bounds
            assert target[0] >= (left + right) // 2
            self.events.append(("menu", "open"))
            self.timeline_xml = self.xml
            self.xml = (
                self.home_menu
                if screen.kind == "home"
                else document(
                    "followed-options" if self.following else "search-options"
                ).replace("@NASA", self.menu_author)
            )
            if self.menu_error:
                raise self.menu_error
            return
        matches = [
            t
            for p in screen.posts
            for t in p.actions
            if t.visibility.visible_bounds == target
        ]
        if not matches:
            return super().tap(target, exclude, kind)
        assert len(matches) == 1
        action = matches[0]
        assert tuple(exclude) == action.visibility.overlaps
        self.events.append(("engage", action.label))
        self.xml = self.after[action.label]
        if self.intermediate:
            self.pending = [self.intermediate, self.xml]
        if self.engagement_error:
            raise self.engagement_error


def started(name="source"):
    replay = EngagementReplay()
    replay.results = replay.latest = document(name)
    app = X(replay.phone)
    app.start("fixture_owner", "search", query=QUERY, result_tab="latest")
    return replay, app


@pytest.mark.parametrize(
    "label,method,initial,after,intermediate",
    [
        ("Like", "set_liked", "source", "liked", "like-animation"),
        ("Bookmark", "set_bookmarked", "liked", "bookmarked", "bookmark-toast"),
    ],
)
def test_engagement_waits_through_native_transition_and_preserves_occurrence(
    label, method, initial, after, intermediate
):
    replay, app = started(initial)
    source = app.observe()
    replay.intermediate = document(intermediate)
    result = getattr(app, method)()
    assert result.changed and result.selected and not result.advanced
    assert result.source_key == source.content_key == app.observe().content_key
    assert replay.events.count(("engage", label)) == 1
    assert app.observe() == read_screen(document(after), SIZE).posts[0]
    assert app.verified_account == "@fixture_owner"


@pytest.mark.parametrize("method", ["set_liked", "set_bookmarked"])
def test_already_selected_states_are_never_toggled(method):
    replay, app = started("bookmarked")
    result = getattr(app, method)()
    assert result.selected and not result.changed
    assert not any(e[0] == "engage" for e in replay.events)


@pytest.mark.parametrize(
    "label,method,initial,after",
    [
        ("Like", "set_liked", "liked", "source"),
        ("Bookmark", "set_bookmarked", "bookmarked", "liked"),
    ],
)
def test_explicit_state_restoration_requires_verified_active_state(
    label, method, initial, after
):
    replay, app = started(initial)
    replay.after[label] = document(after)
    result = getattr(app, method)(False)
    assert result.changed and not result.selected
    assert replay.events.count(("engage", label)) == 1


@pytest.mark.parametrize(
    "problem", ["transport", "no_change", "other_post", "query", "cancel"]
)
def test_uncertain_engagement_is_never_retried_and_invalidates_browsing(problem):
    replay, app = started()
    if problem == "transport":
        replay.engagement_error = OSError("tap response lost")
    elif problem == "cancel":
        replay.engagement_error = InteractionCancelled("cancelled")
    elif problem == "no_change":
        replay.after["Like"] = document("source")
    elif problem == "query":
        replay.after["Like"] = document("liked").replace(QUERY, "another query")
    else:
        replay.after["Like"] = document("liked").replace("@NASA", "@other")
    with pytest.raises(
        InteractionCancelled if problem == "cancel" else InteractionError
    ) as caught:
        app.set_liked()
    if problem != "cancel":
        assert caught.value.result.status == Status.UNCERTAIN
    assert app.verified_account is None
    assert replay.events.count(("engage", "Like")) == 1
    with pytest.raises(XError):
        app.set_liked()
    assert replay.events.count(("engage", "Like")) == 1
    replay.phone.close().require()
    assert replay.closed


def test_changed_source_stops_before_engagement():
    replay, app = started()
    replay.xml = replay.xml.replace("@NASA", "@other")
    with pytest.raises(XError):
        app.set_liked()
    assert not any(e[0] == "engage" for e in replay.events)


def test_disabled_action_is_not_tapped():
    replay, app = started()
    root = etree.fromstring(replay.xml.encode())
    root.xpath('.//*[@content-desc="Like"]')[0].getparent().set("enabled", "false")
    replay.xml = etree.tostring(root, encoding="unicode")
    with pytest.raises(XError):
        app.set_liked()
    assert not any(e[0] == "engage" for e in replay.events)


@pytest.mark.parametrize(
    "following,selected", [(False, True), (True, True), (False, False), (True, False)]
)
def test_follow_state_and_unfollow_receipt_are_verified(following, selected):
    replay, app = started("bookmarked")
    replay.following = following
    source = app.observe()
    result = app.follow() if selected else app.unfollow()
    assert result.selected == selected
    assert result.changed == (following != selected)
    if following and not selected:
        assert result.advanced
        assert app.observe().content_key != source.content_key
        assert app.navigation_gaps[-1]["action"] == "unfollow"
    else:
        assert not result.advanced
        assert app.observe().content_key == source.content_key
    assert sum(e[0] == "engage" for e in replay.events) == int(following != selected)
    assert app.verified_account == "@fixture_owner"


def test_wrong_menu_author_stops_before_following():
    replay, app = started()
    replay.menu_author = "@other"
    with pytest.raises(XError, match="selected author"):
        app.follow()
    assert not any(e[0] == "engage" for e in replay.events)


def test_follow_transport_uncertainty_is_not_retried():
    replay, app = started()
    replay.engagement_error = OSError("tap outcome unknown")
    with pytest.raises(InteractionError) as caught:
        app.follow()
    assert caught.value.result.status == Status.UNCERTAIN
    assert replay.events.count(("engage", "follow")) == 1
    assert app.verified_account is None


def home_started(wrapper=False):
    replay, app = started()
    replay.xml = document("home-source")
    screen = read_screen(replay.xml, SIZE)
    app.timeline, app.query = "for_you", None
    app._select(screen, screen.posts.index(screen.observable_posts[0]))
    # Remove the clipped quote to model an already observable successor.
    root = etree.fromstring(document("feedback").encode())
    container = root.xpath('.//*[@resource-id="timeline_post"]')[0].getparent()
    quote = container.xpath('.//*[@content-desc="Quote"]')[0]
    while quote.getparent() is not container:
        quote = quote.getparent()
    container.remove(quote)
    replay.removal = etree.tostring(root, encoding="unicode")
    if wrapper:
        browser = XBrowser(replay.phone, {"for_you"})
        browser.browser = app
        browser.workflow, browser._username, browser._valid = (
            "for_you",
            "fixture_owner",
            True,
        )
        return replay, browser
    return replay, app


def test_not_interested_verifies_native_receipt_and_advances_without_an_extra_swipe():
    replay, app = home_started()
    source = app.observe()
    result = app.not_interested()
    assert result.changed and result.advanced and result.action == "not_interested"
    assert result.source_key == source.content_key
    assert app.observe().content_key != source.content_key
    assert replay.events.count(("engage", "not_interested")) == 1
    assert not any(e[0] == "gesture" for e in replay.events)


@pytest.mark.parametrize(
    "problem", ["receipt", "author", "position", "transport", "cancel"]
)
def test_feedback_without_an_exact_positive_receipt_remains_uncertain(problem):
    replay, app = home_started()
    if problem in {"transport", "cancel"}:
        replay.engagement_error = (
            OSError("lost reply")
            if problem == "transport"
            else InteractionCancelled("cancelled")
        )
    else:
        root = etree.fromstring(document("feedback").encode())
        node = root.xpath(
            './/*[@text="Thanks. X will use this to make your timeline better."]'
        )[0]
        if problem == "receipt":
            node.set("text", "Something else happened.")
        elif problem == "author":
            root.xpath('.//*[@text="Show fewer posts from astrooalert"]')[0].set(
                "text", "Show fewer posts from other"
            )
        else:
            node.getparent().set("bounds", "[33,464][1047,929]")
        replay.removal = etree.tostring(root, encoding="unicode")
    with pytest.raises(
        InteractionCancelled if problem == "cancel" else InteractionError
    ) as caught:
        app.not_interested()
    if problem != "cancel":
        assert caught.value.result.status == Status.UNCERTAIN
    assert replay.events.count(("engage", "not_interested")) == 1
    assert app.verified_account is None


def test_unavailable_search_feedback_is_dismissed_without_engagement():
    replay, app = started()
    with pytest.raises(XError) as caught:
        app.not_interested()
    assert caught.value.result.status == Status.UNSUPPORTED
    assert replay.events[-1] == ("menu", "close")
    assert not any(e[0] == "engage" for e in replay.events)


def test_browser_reports_automatic_advancement_and_rejects_the_old_decision():
    replay, browser = home_started(wrapper=True)
    observation = browser.observe()
    result = browser.act("not_interested", observation)
    assert result.advanced
    assert browser.observe().identity != observation.identity
    assert browser.browsing_valid
    with pytest.raises(XError, match="current post"):
        browser.act("like", observation)
    assert replay.events.count(("engage", "not_interested")) == 1
    assert not any(e == ("engage", "Like") for e in replay.events)


def test_browser_like_dispatch_and_native_states_preserve_identity():
    replay, app = started()
    browser = XBrowser(replay.phone, {"search"})
    browser.browser = app
    browser.workflow, browser.target, browser._valid = "search", QUERY, True
    source = browser.observe()
    assert source.post_context["available_engagement_actions"] == [
        "like",
        "save",
        "follow",
        "unfollow",
    ]
    assert source.post_context["engagement"] == {"liked": False, "bookmarked": False}
    assert not browser.act("like", source).advanced
    current = browser.observe()
    assert current.identity == source.identity
    assert current.post_context["engagement"]["liked"]
    assert not browser.act("like", current).advanced
    assert replay.events.count(("engage", "Like")) == 1


def test_feedback_retains_verified_collapsed_home_during_captured_successor_framing():
    replay, app = home_started()
    replay.xml = document("feedback-scrolling-source")
    screen = read_screen(replay.xml, SIZE)
    source = screen.observable_posts[0]
    app._select(screen, screen.posts.index(source))
    replay.home_menu = document("home-options").replace("@astrooalert", source.author)
    replay.removal = document("feedback-scrolling-receipt")
    replay.scrolls = [document(f"feedback-scroll-{i}") for i in (1, 2, 3)]
    result = app.not_interested()
    assert result.advanced and app.observe().author == "@Yatesedls"
    gestures = [e for e in replay.events if e[0] == "gesture"]
    assert len(gestures) == 3 and all(e[2] == "up" for e in gestures)
    assert replay.events.count(("engage", "not_interested")) == 1
    assert app.verified_account == "@fixture_owner"


def test_observation_keeps_offscreen_engagement_states_unknown():
    xml = (
        CORE / "tests/unit/social_media/x/fixtures/live-badge-tail-ready.xml"
    ).read_text()
    screen = read_screen(xml, SIZE)
    post = next(p for p in screen.observable_posts if p.author == "@fixture_1")
    states = {t.label: t for t in post.actions}
    assert states["Like"].state_visibility.visible_bounds is None
    assert states["Bookmark"].state_visibility.visible_bounds is None
    assert post_context(post)["engagement"] == {"liked": None, "bookmarked": None}


def test_browser_does_not_offer_offscreen_footer_actions():
    replay, app = started()
    replay.xml = (
        CORE / "tests/unit/social_media/x/fixtures/live-badge-tail-ready.xml"
    ).read_text()
    screen = read_screen(replay.xml, SIZE)
    source = next(p for p in screen.observable_posts if p.author == "@fixture_1")
    app.timeline, app.query = "for_you", None
    app._select(screen, screen.posts.index(source))
    browser = XBrowser(replay.phone, {"for_you"})
    browser.browser = app
    browser.workflow, browser._valid = "for_you", True
    events = list(replay.events)
    available = browser.observe().post_context["available_engagement_actions"]
    assert "like" not in available and "save" not in available
    assert "follow" in available and "unfollow" in available
    assert replay.events == events


@pytest.mark.parametrize("problem", ["own_account", "no_menu", "receipt", "following"])
def test_menu_action_availability_uses_observed_context(problem):
    from dataclasses import replace

    from taktik.core.social_media.x.services.browsing.engagement import (
        available_actions,
    )

    _, app = home_started()
    source = app.observe()
    screen = app._screen
    account = app.verified_account
    assert "not_interested" in available_actions(source, screen, account, app.timeline)
    if problem == "own_account":
        account = source.author
    elif problem == "no_menu":
        source = replace(source, targets=())
    elif problem == "receipt":
        screen = replace(
            screen,
            removal_notices=read_screen(document("feedback"), SIZE).removal_notices,
        )
    else:
        screen = replace(screen, tab="Following")
    actions = available_actions(source, screen, account, app.timeline)
    assert "not_interested" not in actions
    assert ("follow" in actions) == (problem in {"receipt", "following"})
    assert ("unfollow" in actions) == (problem in {"receipt", "following"})


def test_collapsed_for_you_retains_feedback_availability():
    replay, browser = home_started(wrapper=True)
    replay.xml = document("feedback-scrolling-source")
    screen = read_screen(replay.xml, SIZE)
    assert screen.kind == "home" and screen.tab is None
    browser.browser._select(screen, screen.posts.index(screen.observable_posts[0]))
    assert (
        "not_interested"
        in browser.observe().post_context["available_engagement_actions"]
    )


@pytest.mark.parametrize(
    "name,offset",
    [("covered-partial-handle", 1), ("footer-gif-padding", 0), ("covered-bookmark", 1)],
)
@pytest.mark.parametrize(
    "label,native", [("Like", "Undo Like"), ("Bookmark", "Delete Bookmark")]
)
def test_selected_action_aliases_preserve_clipped_post_continuity(
    name, offset, label, native
):
    screens = []
    for stage in ("before", "after"):
        xml = (
            CORE / f"tests/unit/social_media/x/fixtures/{name}-{stage}.xml"
        ).read_text()
        xml = xml.replace(f'content-desc="{label}"', f'content-desc="{native}"')
        screens.append(read_screen(xml, SIZE))
    assert _alignment(*screens, scrolling=True) == (offset, True)


def test_liking_a_post_with_a_covered_empty_bookmark_slot_preserves_observability():
    replay, app = started()
    replay.xml = (
        CORE / "tests/unit/social_media/x/fixtures/ai-covered-footer-after.xml"
    ).read_text()
    screen = read_screen(replay.xml, SIZE)
    source = next(p for p in screen.observable_posts if p.author == "@fixture_1")
    app.timeline, app.query = "for_you", None
    app._select(screen, screen.posts.index(source))
    replay.after["Like"] = replay.xml.replace(
        'content-desc="Like"', 'content-desc="Undo Like"'
    )
    assert app.set_liked().selected
    assert app.observe().content_key == source.content_key
    assert replay.events.count(("engage", "Like")) == 1
