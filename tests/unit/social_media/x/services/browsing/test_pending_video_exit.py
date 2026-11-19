"""Reverified pending text leaves a bounded allowance to exit its video tail."""

import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from unit.paths import CORE

from taktik.core.shared.phone_interaction import (
    InteractionCancelled,
    Phone,
    Result,
    SessionExpired,
    Status,
)
from taktik.core.social_media.x.services.browsing.navigation import (
    ADVANCE_MAX_SCROLLS,
    X,
    XError,
)
from taktik.core.social_media.x.ui.screen import read_screen


def document(name):
    return ((CORE / "tests/unit/social_media/x/fixtures") / f"{name}.xml").read_text()


def captured_app(name):
    device = SimpleNamespace(
        document=document(name), scrolls=[], phone=Mock(spec=Phone)
    )

    def read(what):
        return {
            "app": {"package": "com.twitter.android"},
            "size": (1080, 2340),
            "hierarchy": device.document,
        }[what]

    def gesture(*args, **kwargs):
        if device.scrolls:
            device.document = device.scrolls.pop(0)
        return Result(Status.SUCCESS)

    device.phone.read.side_effect = read
    device.phone.gesture.side_effect = gesture
    app = X(device.phone)
    app.timeline, app.verified_account = "for_you", "@fixture_owner"
    app._select(read_screen(device.document, (1080, 2340)), 0)
    return app, device


def prepared(end=41):
    app, device = captured_app("pending-video-exit-selected")
    device.scrolls = [document(f"pending-video-exit-{n}") for n in range(28, end)]
    return app, device


def test_captured_pending_exit_can_reach_a_synthetic_next_observation():
    app, device = prepared()
    device.scrolls.append(document("pending-video-exit-synthetic"))
    post = app.advance()
    assert (
        post.author
        == read_screen(document("pending-video-exit-synthetic"), (1080, 2340))
        .posts[0]
        .author
    )
    assert app.observe() == post
    assert device.phone.gesture.call_count == 14
    assert app.verified_account == "@fixture_owner"


def test_stationary_video_tail_still_exhausts_bounded_exit_allowance():
    app, device = prepared()
    with pytest.raises(XError, match="scrolling limit"):
        app.advance()
    assert device.phone.gesture.call_count == 20
    assert app.verified_account is None


def test_still_pending_text_cannot_reset_its_allowance():
    app, device = prepared(end=38)
    with pytest.raises(XError, match="scrolling limit"):
        app.advance()
    assert device.phone.gesture.call_count == 13
    assert app.verified_account is None


def test_session_deadline_interrupts_exit_allowance():
    app, device = prepared()
    original = device.phone.wait.side_effect

    def expire(*args, **kwargs):
        if device.phone.gesture.call_count == 14:
            raise SessionExpired("session deadline")
        if original:
            return original(*args, **kwargs)

    device.phone.wait.side_effect = expire
    with pytest.raises(SessionExpired):
        app.advance()
    assert device.phone.gesture.call_count == 14
    assert app.verified_account is None


FIXTURES = CORE / "tests/unit/social_media/x/fixtures/coverage"


def test_captured_search_header_loss_enters_pending_without_a_new_observation():
    before, after = [
        read_screen((FIXTURES / f"pending-search-{name}.xml").read_text(), (1080, 2340))
        for name in ("before", "hidden-header")
    ]
    app = X(Mock(spec=Phone))
    app.timeline, app.result_tab = "search", "latest"
    app.query = '(from:NASA "stellar merger") OR (from:Sai60012 "BHOLE")'
    app.verified_account = "@fixture_owner"

    _, offset, moved = app._advance_alignment(before, after, False)

    assert offset == 1 and moved is None
    assert not after.posts and not after.rejected_posts
    (passage,) = after.fragments
    assert passage.body == before.posts[0].body
    assert not hasattr(passage, "author")
    assert passage.translation == "Translated from Hindi"


class PassageReplay:
    def __init__(self):
        self.case = json.loads((FIXTURES / "long-text-traversal.json").read_text())
        self.documents = [(FIXTURES / name).read_text() for name in self.case["files"]]
        self.index = 0
        self.now = 0
        self.phone = Phone(self, clock=lambda: self.now, sleep=self.sleep)
        self.app = X(self.phone)
        self.app.timeline, self.app.result_tab = "search", self.case["tab"]
        self.app.query, self.app.verified_account = self.case["query"], "@fixture_owner"
        screen = read_screen(self.documents[0], (1080, 2340))
        selected = next(
            i
            for i, post in enumerate(screen.posts)
            if post.content_key == self.case["source_key"]
        )
        self.app._select(screen, selected)

    def bind(self, phone):
        pass

    def sleep(self, seconds):
        self.now += seconds

    def read(self, what):
        return {
            "app": {"package": "com.twitter.android"},
            "size": (1080, 2340),
            "hierarchy": self.documents[self.index],
        }[what]

    def gesture(self, intent, direction, region, distance, exclude):
        assert intent == "scroll" and direction == "up"
        self.index += 1
        assert self.index < len(self.documents)


def test_physical_long_text_and_video_exit_reaches_a_real_successor():
    replay = PassageReplay()
    outcomes = []
    alignment = replay.app._advance_alignment

    def recorded(before, after, pending):
        result = alignment(before, after, pending)
        outcomes.append(
            {"before_pending": pending, "offset": result[1], "moved": result[2]}
        )
        return result

    replay.app._advance_alignment = recorded
    successor = replay.app.advance()

    assert successor.content_key == replay.case["successor_key"]
    assert successor.content_key != replay.case["source_key"]
    assert replay.app.observe() == successor
    assert outcomes == replay.case["outcomes"]
    assert any(item["before_pending"] and item["moved"] for item in outcomes)
    assert not replay.app.navigation_gaps
    assert replay.index == 23 < ADVANCE_MAX_SCROLLS


def test_cancellation_during_captured_pending_text_stops_without_retry():
    replay = PassageReplay()
    replay.phone.configure(cancelled=lambda: replay.index >= 15)

    with pytest.raises(InteractionCancelled):
        replay.app.advance()

    assert replay.index == 15
    assert replay.app.verified_account is None
