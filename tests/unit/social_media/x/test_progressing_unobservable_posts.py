"""Bound search between verified post-position changes; preserve session limits."""

from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from lxml import etree
from taktik.core.shared.phone_interaction import Phone, Result, SessionExpired, Status
from taktik.core.shared.ui.geometry import bounds
from taktik.core.social_media.x.services.browsing.navigation import (
    ADVANCE_SCROLL_ATTEMPTS,
    X,
    XError,
    _alignment,
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


def captured(number):
    return document(f"progressing-unobservable-posts-{number}")


def synthetic_next():
    """Explicitly synthetic 516px forward movement, without inventing text."""
    root = etree.fromstring(captured(38).encode())
    timeline = (
        root.xpath('//*[@resource-id="timeline_post"]')[0].getparent().getparent()
    )
    for container in timeline:
        for node in container.iter():
            x1, y1, x2, y2 = bounds(node)
            node.set("bounds", f"[{x1},{max(0, y1 - 516)}][{x2},{max(0, y2 - 516)}]")
    return etree.tostring(root, encoding="unicode")


def test_captured_progress_can_reach_next_post_after_eight_verified_scrolls():
    app, device = captured_app("progressing-unobservable-posts-selected")
    after = synthetic_next()
    assert _alignment(
        read_screen(captured(38), (1080, 2340)),
        read_screen(after, (1080, 2340)),
        scrolling=True,
    )[1]
    device.scrolls = [*(captured(i) for i in range(31, 39)), after]
    post = app.advance()
    assert post.author == read_screen(after, (1080, 2340)).posts[0].author
    assert app.observe() == post
    assert device.phone.gesture.call_count == 9
    assert app.verified_account == "@fixture_owner"


def test_repeated_frame_still_exhausts_bounded_search_after_verified_progress():
    app, device = captured_app("progressing-unobservable-posts-selected")
    device.scrolls = [*(captured(i) for i in range(31, 39))]
    with pytest.raises(XError, match="scrolling limit"):
        app.advance()
    assert device.phone.gesture.call_count <= ADVANCE_SCROLL_ATTEMPTS * 2
    assert app.verified_account is None


def test_session_deadline_stops_a_progressing_search():
    app, device = captured_app("progressing-unobservable-posts-selected")
    device.scrolls = [*(captured(i) for i in range(31, 39))]
    original = device.phone.wait.side_effect

    def expire(*args, **kwargs):
        if device.phone.gesture.call_count == 7:
            raise SessionExpired("session deadline")
        if original:
            return original(*args, **kwargs)

    device.phone.wait.side_effect = expire
    with pytest.raises(SessionExpired, match="session deadline"):
        app.advance()
    assert device.phone.gesture.call_count == 7
    assert app.verified_account is None
