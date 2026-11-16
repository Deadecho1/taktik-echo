"""A long pending passage has its own bounded verification allowance."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from taktik.core.shared.phone_interaction import Phone, Result, SessionExpired, Status
from taktik.core.social_media.x.services.browsing.navigation import (
    ADVANCE_SCROLL_ATTEMPTS,
    X,
    XError,
)
from taktik.core.social_media.x.ui.screen import read_screen


def document(name):
    return (Path(__file__).with_name("fixtures") / f"{name}.xml").read_text()


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


def synthetic_endpoint(bottom=1600):
    return document(f"late-pending-text-exit-{bottom}")


def prepared():
    app, device = captured_app("late-pending-text-selected")
    device.scrolls = [document(f"late-pending-text-{n}") for n in range(20, 28)]
    return app, device


def test_captured_approach_leaves_bounded_time_for_pending_text_exit():
    app, device = prepared()
    device.scrolls += [synthetic_endpoint(), synthetic_endpoint(1300)]
    post = app.advance()
    assert (
        post.author
        == read_screen(synthetic_endpoint(1300), (1080, 2340)).posts[0].author
    )
    assert app.observe() == post
    assert device.phone.gesture.call_count == 10
    assert app.verified_account == "@fixture_owner"


def test_repeated_clipped_text_still_exhausts_a_bounded_allowance():
    app, device = prepared()
    with pytest.raises(XError, match="scrolling limit"):
        app.advance()
    assert (
        ADVANCE_SCROLL_ATTEMPTS
        < device.phone.gesture.call_count
        <= 2 * ADVANCE_SCROLL_ATTEMPTS
    )
    assert app.verified_account is None


def test_deadline_stops_the_extended_pending_phase():
    app, device = prepared()
    original = device.phone.wait.side_effect

    def expire(*args, **kwargs):
        if device.phone.gesture.call_count == 9:
            raise SessionExpired("session deadline")
        if original:
            return original(*args, **kwargs)

    device.phone.wait.side_effect = expire
    with pytest.raises(SessionExpired):
        app.advance()
    assert device.phone.gesture.call_count == 9
    assert app.verified_account is None
