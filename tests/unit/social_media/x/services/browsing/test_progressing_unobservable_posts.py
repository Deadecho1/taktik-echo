"""Bound search between verified post-position changes; preserve session limits."""

import hashlib
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from lxml import etree
from unit.paths import CORE

from taktik.core.shared.phone_interaction import (
    InteractionCancelled,
    InteractionError,
    Phone,
    Result,
    SessionExpired,
    Status,
)
from taktik.core.shared.phone_interaction._device import TaktikDevice
from taktik.core.shared.ui.geometry import bounds
from taktik.core.social_media.x.services.browsing.browser import XBrowser
from taktik.core.social_media.x.services.browsing.navigation import (
    ADVANCE_SCROLL_ATTEMPTS,
    X,
    XError,
    _alignment,
)
from taktik.core.social_media.x.ui.screen import PACKAGE, read_screen


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


FIXTURES = CORE / "tests/unit/social_media/x/fixtures/navigation"
SIZE = (1080, 2340)


def preceding_document(number):
    return (FIXTURES / f"preceding-posts-{number}.xml").read_text()


def synthetic_continuation():
    """Construct a separate 500px progression, including complete synthetic text."""
    root = etree.fromstring(preceding_document(8).encode())
    timeline = root.xpath('.//*[@text="Who to follow"]')[0].getparent()
    for container in list(timeline):
        if bounds(container)[3] <= 636:
            timeline.remove(container)
            continue
        for node in container.iter():
            x1, y1, x2, y2 = bounds(node)
            node.set("bounds", f"[{x1},{max(0, y1 - 500)}][{x2},{max(0, y2 - 500)}]")
    return etree.tostring(root, encoding="unicode")


class RawReplay:
    def __init__(self, documents):
        self.documents = documents
        self.stage = 0
        self.paths = []
        self.now = 0

    def app_current(self):
        return {"package": PACKAGE}

    def window_size(self):
        return SIZE

    def dump_hierarchy(self):
        return self.documents[self.stage]

    def sleep(self, seconds):
        self.now += seconds

    def swipe_points(self, path, duration):
        self.paths.append((path, duration))
        self.stage = min(self.stage + 1, len(self.documents) - 1)


@pytest.fixture
def replay():
    raw = RawReplay([preceding_document(i) for i in range(9)])
    phone = Phone(
        TaktikDevice(raw, "fixture"), seed=0, clock=lambda: raw.now, sleep=raw.sleep
    )
    browser = XBrowser(phone, {"for_you"})
    app = browser.browser
    app.timeline = "for_you"
    app.verified_account = app._expected = "@fixture_owner"
    screen = read_screen(raw.documents[0], SIZE)
    app._select(screen, 3)
    browser.workflow, browser._username, browser._valid = (
        "for_you",
        "fixture_owner",
        True,
    )
    yield raw, browser
    phone.close(home=False).require()


def test_verified_preceding_post_traversal_can_frame_a_later_successor(replay):
    raw, browser = replay
    before = browser.observe()
    raw.documents.append(synthetic_continuation())
    browser.advance()
    after = browser.observe()
    assert after.username == "writer_49"
    assert after.identity != before.identity
    assert after.caption_type == "full"
    assert len(raw.paths) == 9
    assert browser.browsing_valid


def test_stopped_sequence_does_not_invent_a_successor_and_keeps_no_progress_bound(
    replay,
):
    raw, browser = replay
    with pytest.raises(
        XError, match="Cannot verify a next X post within the scrolling limit"
    ):
        browser.advance()
    assert len(raw.paths) == 16
    assert not browser.browsing_valid
    assert browser.browser.verified_account is None


def without_preceding(xml):
    root = etree.fromstring(xml.encode())
    source = root.xpath('.//*[@text="@writer_31"]')[0].getparent().getparent()
    timeline = source.getparent()
    for node in list(timeline):
        if node is source:
            break
        timeline.remove(node)
    return etree.tostring(root, encoding="unicode")


def test_pixel_motion_without_passing_other_posts_keeps_eight_attempt_limit(replay):
    raw, browser = replay
    raw.documents = [without_preceding(xml) for xml in raw.documents]
    browser.browser._select(read_screen(raw.documents[0], SIZE), 0)
    with pytest.raises(XError, match="scrolling limit"):
        browser.advance()
    assert len(raw.paths) == 8
    assert not browser.browsing_valid


def test_stationary_source_keeps_eight_attempt_limit(replay):
    raw, browser = replay
    raw.documents = raw.documents[:1]
    with pytest.raises(XError, match="scrolling limit"):
        browser.advance()
    assert len(raw.paths) == 8
    assert not browser.browsing_valid


@pytest.mark.parametrize("change", ["author", "body", "geometry", "duplicate"])
def test_preceding_exit_does_not_repair_changed_or_ambiguous_source(replay, change):
    raw, browser = replay
    root = etree.fromstring(raw.documents[4].encode())
    handle = root.xpath('.//*[@text="@writer_31"]')[0]
    source = handle.getparent().getparent()
    body = next(
        n for n in source if n.get("text", "").startswith("Synthetic paragraph")
    )
    if change == "author":
        handle.set("text", "@another_writer")
    elif change == "body":
        body.set("text", "A different synthetic statement replaces the selected text.")
    elif change == "geometry":
        x1, y1, x2, y2 = bounds(body)
        body.set("bounds", f"[{x1},{y1 + 20}][{x2},{y2 + 20}]")
    else:
        earlier = root.xpath('.//*[@text="@writer_23"]')[0]
        earlier.set("text", handle.get("text"))
        previous = earlier.getparent().getparent()
        for node in previous:
            if node.get("text", "").startswith("Synthetic paragraph"):
                node.set("text", body.get("text"))
    raw.documents[4] = etree.tostring(root, encoding="unicode")
    with pytest.raises(XError):
        browser.advance()
    if change in {"body", "geometry"}:
        assert len(raw.paths) == 4
        assert not browser.browser.navigation_gaps
    else:
        assert len(raw.paths) == 16
        assert browser.browser.navigation_gaps
        assert all(
            g["basis"] == "native_timeline_text"
            for g in browser.browser.navigation_gaps
        )
    assert not browser.browsing_valid


def test_complete_sequence_reaches_successor_then_continues_with_explicit_gaps(replay):
    raw, browser = replay
    raw.documents = [
        (FIXTURES / f"preceding-complete-{i}.xml").read_text() for i in range(11)
    ]
    browser.browser._select(read_screen(raw.documents[0], SIZE), 2)
    source = browser.observe()
    browser.advance()
    successor = browser.observe()
    assert successor.username == "writer_49"
    assert successor.identity != source.identity
    assert len(raw.paths) == 9
    assert browser.browser.navigation_gaps
    assert browser.browsing_valid
    browser.advance()
    assert browser.observe().username == "writer_65"
    assert len(raw.paths) == 10
    with pytest.raises(XError, match="additional observations"):
        browser.observe(previous=source)


@pytest.mark.parametrize("interruption", ["cancel", "deadline", "uncertain"])
def test_preceding_progress_preserves_phone_interruption_without_retry(
    replay, interruption
):
    raw, browser = replay
    phone = browser.browser.phone
    if interruption == "cancel":
        phone.configure(cancelled=lambda: raw.stage == 4)
        error = InteractionCancelled
    elif interruption == "deadline":
        phone.configure(deadline=100)
        original = raw.sleep

        def expire(seconds):
            original(seconds)
            if raw.stage == 4:
                raw.now = 100

        phone._sleep = expire
        error = SessionExpired
    else:
        original = raw.swipe_points

        def uncertain(path, duration):
            original(path, duration)
            if raw.stage == 5:
                raise OSError("Synthetic transport response lost.")

        raw.swipe_points = uncertain
        error = InteractionError
    with pytest.raises(error) as caught:
        browser.advance()
    if interruption == "uncertain":
        assert caught.value.result.status == Status.UNCERTAIN
    assert len(raw.paths) == (5 if interruption == "uncertain" else 4)
    assert not browser.browsing_valid
    assert browser.browser.verified_account is None


def test_preceding_fixture_integrity():
    manifest = json.loads((FIXTURES / "manifest.json").read_text())
    assert manifest["kind"] == "synthetic_native_layout"
    for item in manifest["fixtures"]:
        assert (
            hashlib.sha256((FIXTURES / item["file"]).read_bytes()).hexdigest()
            == item["sha256"]
        )


def test_temporary_source_loss_cannot_credit_preceding_exit(replay):
    raw, browser = replay
    raw.documents = raw.documents[:5]
    root = etree.fromstring(raw.documents[3].encode())
    source = root.xpath('.//*[@text="@writer_31"]')[0].getparent().getparent()
    source.getparent().remove(source)
    raw.documents[3] = etree.tostring(root, encoding="unicode")
    with pytest.raises(XError, match="scrolling limit"):
        browser.advance()
    assert len(raw.paths) == 8
    assert not browser.browsing_valid
