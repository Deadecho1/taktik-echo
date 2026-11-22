"""Scrolling can cross rejected content without promoting it to an observation."""

from dataclasses import replace
from unittest.mock import Mock

import pytest
from PIL import Image
from unit.paths import CORE
from unit.shared.phone_interaction.recording import recording_session
from unit.social_media.x.services.search_replay import SearchReplay, shifted_results
from unit.social_media.x.services.search_replay import document as search_document
from unit.x_fixtures import SIZE, fixture_manifest, xml_fixture

from scripts.eval.x_caption_validation import check_caption
from taktik.core.shared.phone_interaction import (
    InteractionCancelled,
    InteractionError,
    Phone,
    Result,
    SessionExpired,
    Status,
)
from taktik.core.social_media.x.services.browsing import expansion
from taktik.core.social_media.x.services.browsing.browser import XBrowser
from taktik.core.social_media.x.services.browsing.navigation import (
    X,
    XError,
    _scroll_motion,
)
from taktik.core.social_media.x.ui.screen import read_screen


def test_unlabeled_inline_content_does_not_supply_missing_movement_evidence():
    fixtures = CORE / "tests/unit/social_media/x/fixtures/coverage"
    before, after = [
        read_screen(xml_fixture(fixtures / f"unlabeled-inline-{stage}.xml"), SIZE)
        for stage in ("before", "after")
    ]
    for screen in (before, after):
        assert not screen.observable_posts
        assert not screen.fragments
        assert screen.rejected_posts[0].reason == "Unrecognized inline body annotation."
    app = X(Mock(spec=Phone))
    app.timeline, app.verified_account = "for_you", "@fixture_owner"

    with pytest.raises(XError, match="no overlapping candidates"):
        app._advance_alignment(before, after, False)


class TimelinePhone:
    def __init__(self):
        self.document = ""
        self.scrolls = []
        self.phone = Mock(spec=Phone)
        self.phone.read.side_effect = self.read
        self.phone.gesture.side_effect = self.gesture

    def read(self, what):
        return {
            "app": {"package": "com.twitter.android"},
            "size": SIZE,
            "hierarchy": self.document,
        }[what]

    def gesture(self, *args, **kwargs):
        if self.scrolls:
            self.document = self.scrolls.pop(0)
        return Result(Status.SUCCESS)


FIXTURES = CORE / "tests/unit/social_media/x/fixtures"


def document(stage):
    return xml_fixture(FIXTURES / f"navigation-evidence-{stage}.xml")


def test_rejected_post_does_not_exhaust_the_scroll_distance():
    device = TimelinePhone()
    device.document = document("before")
    screen = read_screen(device.document, SIZE)
    assert screen.rejected_posts
    assert not screen.observable_posts
    device.phone.gesture.return_value = Result(Status.SUCCESS)
    X(device.phone)._gesture(screen, "up")
    assert device.phone.gesture.call_args.kwargs["distance"] > 400


def test_native_text_verifies_motion_without_parsing_the_rejected_post():
    before = read_screen(document("before"), SIZE)
    after = read_screen(document("after"), SIZE)
    assert before.rejected_posts and after.rejected_posts
    assert _scroll_motion(before, after) == -400
    assert not before.observable_posts and not after.observable_posts


def test_uncovered_edges_verify_motion_when_a_floating_control_covers_the_body():
    before = read_screen(document("covered-before"), SIZE)
    after = read_screen(document("covered-after"), SIZE)
    assert before.rejected_posts and after.rejected_posts
    assert _scroll_motion(before, after) == -607
    app = X(TimelinePhone().phone)
    app.timeline, app.verified_account = "for_you", "@fixture_owner"
    assert app._advance_alignment(before, after, False) == (after, None, True)
    assert app.last_scroll_evidence["post_continuity"] == "not_established"


def test_native_motion_can_bridge_an_unmodeled_quote_video_transition():
    before = read_screen(document("metadata-before"), SIZE)
    after = read_screen(document("metadata-after"), SIZE)
    assert not before.rejected_posts and not after.rejected_posts
    assert _scroll_motion(before, after) == -589
    app = X(TimelinePhone().phone)
    app.timeline, app.verified_account = "for_you", "@fixture_owner"
    assert app._advance_alignment(before, after, False) == (after, None, True)
    assert app.last_scroll_evidence["post_continuity"] == "not_established"


def test_reused_short_label_does_not_override_a_long_exact_content_anchor():
    before = read_screen(document("reused-label-before"), SIZE)
    after = read_screen(document("reused-label-after"), SIZE)
    assert _scroll_motion(before, after) == -601
    app = X(TimelinePhone().phone)
    app.timeline, app.verified_account = "for_you", "@fixture_owner"
    assert app._advance_alignment(before, after, False) == (after, None, True)


def test_two_short_anchors_can_survive_exact_clipping_at_a_floating_control():
    before = read_screen(document("clipped-label-before"), SIZE)
    after = read_screen(document("clipped-label-after"), SIZE)
    assert after.rejected_posts
    assert _scroll_motion(before, after) == -606
    app = X(TimelinePhone().phone)
    app.timeline, app.verified_account = "for_you", "@fixture_owner"
    assert app._advance_alignment(before, after, False) == (after, None, True)


@pytest.mark.parametrize("mutation", ["no_cover", "width", "left", "text", "credit"])
def test_short_anchor_clipping_requires_exact_cover_geometry_and_two_texts(mutation):
    before = read_screen(document("clipped-label-before"), SIZE)
    after = read_screen(document("clipped-label-after"), SIZE)
    if mutation == "no_cover":
        after = replace(after, overlaps=())
    else:
        changed = []
        for anchor in after.scroll_anchors:
            x1, y1, x2, y2 = anchor.visibility.bounds
            if (x1, x2) == (349, 389):
                if mutation == "width":
                    anchor = replace(
                        anchor,
                        visibility=replace(
                            anchor.visibility, bounds=(x1, y1, x2 + 1, y2)
                        ),
                    )
                elif mutation == "left":
                    anchor = replace(
                        anchor,
                        visibility=replace(
                            anchor.visibility, bounds=(x1 + 1, y1, x2, y2)
                        ),
                    )
                elif mutation == "text":
                    anchor = replace(anchor, text="@changed")
            if mutation == "credit" and (x1, x2) == (264, 524):
                anchor = replace(anchor, text="Changed credit")
            changed.append(anchor)
        after = replace(after, scroll_anchors=tuple(changed))
    with pytest.raises(XError):
        _scroll_motion(before, after)


def test_fully_covered_text_edges_do_not_supply_movement_evidence():
    before = read_screen(document("covered-before"), SIZE)
    after = read_screen(document("covered-after"), SIZE)
    after = replace(
        after,
        scroll_anchors=tuple(
            replace(
                a, visibility=replace(a.visibility, overlaps=(a.visibility.bounds,))
            )
            if len(a.text) > 32
            else a
            for a in after.scroll_anchors
        ),
    )
    with pytest.raises(XError):
        _scroll_motion(before, after)


def test_advance_collects_fresh_attributed_evidence_after_unsupported_content():
    device = TimelinePhone()
    device.document = document("selected")
    app = X(device.phone)
    app.timeline, app.verified_account = "for_you", "@fixture_owner"
    app._select(read_screen(device.document, SIZE), 0)
    device.scrolls = [document(stage) for stage in ("before", "after", "next")]
    post = app.advance()
    assert post.author == "@fixture_next"
    assert post.observable
    assert app.observe() == post
    assert device.phone.gesture.call_count == 3
    assert app.verified_account == "@fixture_owner"
    assert app.navigation_gaps
    assert all(
        gap["post_continuity"] == "not_established" for gap in app.navigation_gaps
    )
    browser = XBrowser(device.phone, {"for_you"})
    browser.browser, browser.workflow, browser._valid = app, "for_you", True
    observation = browser.observe()
    assert observation.username == post.author.removeprefix("@")
    assert observation.caption == post.body
    assert observation.post_context["navigation_gaps"] == app.navigation_gaps


def test_deadline_interrupts_navigation_past_rejected_content():
    device = TimelinePhone()
    device.document = document("selected")
    app = X(device.phone)
    app.timeline, app.verified_account = "for_you", "@fixture_owner"
    app._select(read_screen(device.document, SIZE), 0)
    device.scrolls = [document("before"), document("after")]
    device.phone.wait.side_effect = [None, SessionExpired("deadline")]
    with pytest.raises(SessionExpired):
        app.advance()
    assert app.verified_account is None
    assert device.phone.gesture.call_count == 2


@pytest.mark.parametrize(
    "case", ["stationary", "reverse", "conflicting", "duplicate", "missing"]
)
def test_native_motion_never_invents_forward_progress(case):
    before = read_screen(document("before"), SIZE)
    after = read_screen(document("after"), SIZE)
    if case == "stationary":
        assert _scroll_motion(before, before) == 0
        return
    if case == "reverse":
        before, after = after, before
    elif case == "conflicting":
        anchor = next(
            a
            for a in after.scroll_anchors
            if a.visibility.bounds[1] > 1500
            and any(b.text == a.text for b in before.scroll_anchors)
        )
        x1, y1, _x2, y2 = anchor.visibility.bounds
        # Two distinct, long text anchors must agree even when short labels
        # elsewhere would be ignored. This mutation is explicitly synthetic.
        long_text = (
            "A separate long content anchor with independently measured geometry."
        )
        before = replace(
            before,
            scroll_anchors=tuple(
                replace(
                    a,
                    text=long_text,
                    visibility=replace(
                        a.visibility,
                        bounds=(
                            x1,
                            a.visibility.bounds[1],
                            1047,
                            a.visibility.bounds[3],
                        ),
                    ),
                )
                if a.text == anchor.text
                else a
                for a in before.scroll_anchors
            ),
        )
        changed = replace(
            anchor,
            text=long_text,
            visibility=replace(anchor.visibility, bounds=(x1, y1 + 20, 1047, y2 + 20)),
        )
        after = replace(
            after,
            scroll_anchors=tuple(
                changed if a == anchor else a for a in after.scroll_anchors
            ),
        )
    elif case == "duplicate":
        before = replace(before, scroll_anchors=before.scroll_anchors * 2)
    else:
        after = replace(after, scroll_anchors=())
    with pytest.raises(XError):
        _scroll_motion(before, after)


STARTUP_FIXTURES = CORE / "tests/unit/social_media/x/fixtures/startup"
TAP = (568, 1478, 660, 1500)


def startup_document(name):
    return xml_fixture(STARTUP_FIXTURES / f"{name}.xml")


class StartupReplay(SearchReplay):
    def __init__(self):
        super().__init__()
        self.xml = startup_document("launch")
        self.drawer = startup_document("drawer")
        self.reset = startup_document("reset")
        self.up = [startup_document(f"frame-{i}") for i in range(1, 5)]
        self.down = [startup_document(f"reveal-{i}") for i in range(1, 3)]
        self.home_error = None
        self.interrupt_gesture = None

    def read(self, what):
        if what == "screenshot":
            return Image.new("RGB", SIZE)
        return super().read(what)

    def command(self, name, value):
        super().command(name, value)
        if name == "launch":
            self.xml = startup_document("launch")

    def tap(self, target, exclude, kind):
        if target == TAP:
            self.events.append(("expand", target))
            self.xml = startup_document("expanded")
            return
        screen = read_screen(self.xml, SIZE)
        matches = [
            c.label for c in screen.controls if c.visibility.visible_bounds == target
        ]
        assert len(matches) == 1, matches
        label = matches[0]
        self.events.append(("tap", label))
        self.xml = {
            "Show navigation drawer": self.drawer,
            "Close navigation menu": startup_document("returned"),
            "Home": self.reset,
        }[label]
        if label == "Home" and self.home_error:
            raise self.home_error

    def gesture(self, intent, direction, region, distance, exclude):
        super().gesture(intent, direction, region, distance, exclude)
        if self.interrupt_gesture:
            self.interrupt_gesture()
        captures = self.up if direction == "up" else self.down
        if captures:
            self.xml = captures.pop(0)


def test_startup_fixture_hashes():
    manifest = fixture_manifest(STARTUP_FIXTURES / "manifest.json")
    assert manifest["size"] == list(SIZE)


def test_captured_short_framing_scroll_executes_with_its_safe_requested_travel():
    screen = read_screen(startup_document("short-scroll"), SIZE)
    assert not screen.observable_posts
    for seed in range(20):
        phone, raw, _ = recording_session(seed)
        events = []
        phone.configure(diagnostic=events.append)
        X(phone)._gesture(screen, "up")
        raw.swipe_points.assert_called_once()
        path = raw.swipe_points.call_args.args[0]
        travel = abs(path[-1][1] - path[0][1])
        assert 96.325 <= travel <= 105.5
        assert all(0 <= x < 137 and 598 <= y < 2004 for x, y in path)
        assert sum(e["action"] == "gesture_geometry" for e in events) == 1
        phone.close(home=False).require()


def test_startup_resets_home_once_after_captured_framing_exhaustion():
    replay = StartupReplay()
    browser = XBrowser(replay.phone, {"for_you"})
    browser.start("fixture_owner", "for_you")
    observation = browser.observe()
    assert observation.username == "rubana_kh"
    assert browser.browser.verified_account == "@fixture_owner"
    assert replay.events.count(("tap", "Home")) == 1
    assert [e[2] for e in replay.events if e[0] == "gesture"] == ["up"] * 4 + [
        "down"
    ] * 2
    assert observation.post_context["navigation_gaps"] == [
        {
            "basis": "home_reset",
            "reason": "initial_framing_limit",
            "post_continuity": "not_established",
        }
    ]
    replay.phone.close().require()
    assert replay.closed


def test_same_capture_sequence_recovers_after_inline_limit_without_read_credit(
    monkeypatch,
):
    replay = StartupReplay()
    replay.xml = startup_document("source")
    browser = XBrowser(replay.phone, {"for_you"})
    app = browser.browser
    app.timeline = "for_you"
    app.verified_account = app._expected = "@fixture_owner"
    screen = read_screen(replay.xml, SIZE)
    app._select(screen, next(i for i, p in enumerate(screen.posts) if p.observable))
    browser.workflow, browser._username, browser._valid = (
        "for_you",
        "fixture_owner",
        True,
    )
    monkeypatch.setattr(expansion, "_target", lambda *_: TAP)
    source = browser.observe()
    events = []
    result = check_caption(
        browser, source, features={}, covered=lambda *event: events.append(event)
    )
    current = browser.observe()
    assert (
        current.identity != source.identity and current.source_key != source.source_key
    )
    assert current.username == "rubana_kh"
    assert result["original_text_complete"] is False
    assert [name for name, _ in events] == [
        "inline_caption_attempt",
        "inline_limit",
        "recovery",
    ]
    assert replay.events.count(("expand", TAP)) == 1
    assert replay.events.count(("tap", "Home")) == 1
    with pytest.raises(XError):
        browser.act("skip", source)


def test_reset_that_retains_clipped_text_stops_after_one_attempt():
    replay = StartupReplay()
    replay.reset = startup_document("reveal-2")
    browser = XBrowser(replay.phone, {"for_you"})
    with pytest.raises(XError, match="framing limit"):
        browser.start("fixture_owner", "for_you")
    assert replay.events.count(("tap", "Home")) == 1
    assert len([e for e in replay.events if e[0] == "gesture"]) == 10
    assert not browser.browsing_valid


@pytest.mark.parametrize("stage", ["account", "framing", "reveal", "reset"])
def test_changed_context_cannot_be_hidden_by_home_reset(stage):
    replay = StartupReplay()
    if stage == "account":
        replay.drawer = replay.drawer.replace("@fixture_owner", "@different_owner")
    elif stage == "framing":
        replay.up[0] = search_document("explore")
    elif stage == "reveal":
        replay.down[-1] = replay.down[-1].replace('text="For you"', 'text="Following"')
    else:
        replay.reset = search_document("explore")
    browser = XBrowser(replay.phone, {"for_you"})
    with pytest.raises(XError):
        browser.start("fixture_owner", "for_you")
    assert not browser.browsing_valid
    assert replay.events.count(("tap", "Home")) == (1 if stage == "reset" else 0)


@pytest.mark.parametrize(
    "error", [InteractionCancelled("cancelled"), OSError("lost tap")]
)
def test_interrupted_or_uncertain_home_tap_is_never_repeated(error):
    replay = StartupReplay()
    replay.home_error = error
    browser = XBrowser(replay.phone, {"for_you"})
    expected = (
        InteractionCancelled
        if isinstance(error, InteractionCancelled)
        else InteractionError
    )
    with pytest.raises(expected) as raised:
        browser.start("fixture_owner", "for_you")
    if isinstance(error, InteractionCancelled):
        assert isinstance(raised.value, InteractionCancelled)
    else:
        assert raised.value.result.status == Status.UNCERTAIN
    assert replay.events.count(("tap", "Home")) == 1
    assert not browser.browsing_valid
    replay.phone.close().require()
    assert replay.closed


def test_deadline_stops_framing_before_reset():
    replay = StartupReplay()
    replay.interrupt_gesture = lambda: replay.phone.configure(deadline=replay.now)
    browser = XBrowser(replay.phone, {"for_you"})
    with pytest.raises(SessionExpired):
        browser.start("fixture_owner", "for_you")
    assert not browser.browsing_valid
    assert ("tap", "Home") not in replay.events


def test_generic_error_with_same_message_does_not_trigger_reset(monkeypatch):
    replay = StartupReplay()
    app = X(replay.phone)

    def fail(*_):
        raise XError("No observable X post within the framing limit.")

    monkeypatch.setattr(app, "_frame", fail)
    with pytest.raises(XError, match="framing limit"):
        app.start("fixture_owner", "for_you")
    assert ("tap", "Home") not in replay.events


def test_search_framing_failure_does_not_reset_home():
    replay = SearchReplay()
    replay.results = shifted_results(1400)
    app = X(replay.phone)
    with pytest.raises(XError, match="framing limit"):
        app.start("fixture_owner", "search", query="astronomy", result_tab="latest")
    assert ("tap", "Home") not in replay.events
