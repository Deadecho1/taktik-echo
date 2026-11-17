"""Scrolling can cross rejected content without promoting it to an observation."""

from dataclasses import replace
from pathlib import Path
from unittest.mock import Mock

import pytest
from taktik.core.shared.phone_interaction import Phone, Result, SessionExpired, Status
from taktik.core.social_media.x.services.browsing.browser import XBrowser
from taktik.core.social_media.x.services.browsing.navigation import (
    X,
    XError,
    _scroll_motion,
)
from taktik.core.social_media.x.ui.screen import read_screen

SIZE = (1080, 2340)


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


FIXTURES = Path(__file__).parent / "fixtures"


def document(stage):
    return (FIXTURES / f"navigation-evidence-{stage}.xml").read_text()


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
        x1, y1, x2, y2 = anchor.visibility.bounds
        changed = replace(
            anchor,
            visibility=replace(anchor.visibility, bounds=(x1, y1 + 20, x2, y2 + 20)),
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
