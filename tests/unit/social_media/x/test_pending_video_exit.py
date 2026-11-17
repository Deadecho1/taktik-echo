"""Reverified pending text leaves a bounded allowance to exit its video tail."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from taktik.core.shared.phone_interaction import Phone, Result, SessionExpired, Status
from taktik.core.social_media.x.services.browsing.navigation import X, XError
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
