"""Reverified pending text leaves a bounded allowance to exit its video tail."""

import json
from dataclasses import replace
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from unit.paths import CORE
from unit.x_fixtures import xml_fixture

from taktik.core.shared.phone_interaction import (
    InteractionCancelled,
    InteractionError,
    Phone,
    Result,
    SessionExpired,
    Status,
)
from taktik.core.shared.phone_interaction._device import TaktikDevice
from taktik.core.social_media.x.services.browsing.browser import XBrowser
from taktik.core.social_media.x.services.browsing.navigation import (
    ADVANCE_MAX_SCROLLS,
    X,
    XError,
    _scroll_motion,
    _text_continuation,
)
from taktik.core.social_media.x.ui.screen import PACKAGE, read_screen


def document(name):
    return xml_fixture((CORE / "tests/unit/social_media/x/fixtures") / f"{name}.xml")


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
        read_screen(xml_fixture(FIXTURES / f"pending-search-{name}.xml"), (1080, 2340))
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
        self.documents = [xml_fixture(FIXTURES / name) for name in self.case["files"]]
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


CAPTION_FIXTURES = CORE / "tests/unit/social_media/x/fixtures/coverage"
SIZE = (1080, 2340)


def caption_document(number):
    return xml_fixture(CAPTION_FIXTURES / f"caption-gif-{number}.xml")


class CaptionReplay:
    def __init__(self, documents=None):
        self.documents = documents or [caption_document(n) for n in range(240, 245)]
        self.stage = 0
        self.paths = []
        self.now = 0
        self.outcomes = []
        self.injection_error = None
        self.phone = Phone(
            TaktikDevice(self, "fixture"),
            seed=0,
            clock=lambda: self.now,
            sleep=self.sleep,
        )
        self.browser = XBrowser(self.phone, {"for_you"})
        app = self.browser.browser
        app.timeline = "for_you"
        app.verified_account = app._expected = "@fixture_owner"
        app._select(read_screen(self.documents[0], SIZE), 0)
        self.browser.workflow = "for_you"
        self.browser._username, self.browser._valid = "fixture_owner", True
        alignment = app._advance_alignment

        def recorded(before, after, pending):
            result = alignment(before, after, pending)
            self.outcomes.append((pending, result[1], result[2]))
            return result

        app._advance_alignment = recorded

    def app_current(self):
        return {"package": PACKAGE}

    def window_size(self):
        return SIZE

    def dump_hierarchy(self):
        return self.documents[self.stage]

    def sleep(self, seconds):
        self.now += seconds

    def swipe_points(self, path, duration):
        self.paths.append(path)
        if self.stage == 4 and self.injection_error is not None:
            raise self.injection_error
        self.stage = min(self.stage + 1, len(self.documents) - 1)


def test_captured_public_advance_enters_pending_then_stops_at_unchanged_bound():
    replay = CaptionReplay()
    source = replay.browser.observe()
    try:
        with pytest.raises(XError, match="scrolling limit"):
            replay.browser.advance()
        assert replay.outcomes[:4] == [
            (False, 0, True),
            (False, 0, True),
            (False, 1, True),
            (False, 1, None),
        ]
        assert replay.outcomes[4:] == [(True, 0, None)] * 7
        assert len(replay.paths) == 11
        assert not replay.browser.browsing_valid
        assert (
            source.source_key
            != read_screen(caption_document(243), SIZE).posts[0].content_key
        )
        assert not read_screen(caption_document(243), SIZE).posts[0].body_complete
    finally:
        replay.phone.close(home=False).require()


def test_physical_caption_gif_exit_reverifies_movement_before_selecting_successor():
    replay = CaptionReplay([caption_document(f"physical-{n}") for n in range(17, 25)])
    try:
        source = replay.browser.observe()
        replay.browser.advance()
        successor = replay.browser.observe()
        assert (
            source.source_key
            == "eb9dcdf01abe6b7cd1a596b35abef3d5898654a16423c5c9433eded2e93c5615"
        )
        assert (
            successor.source_key
            == "302cefbce0f032a8b7ebc1ad2fa897cf627ac517e68cb132975b85cdc8d214df"
        )
        assert successor.identity != source.identity
        assert replay.browser.browsing_valid
        assert replay.browser.browser.observe().observable
        assert replay.outcomes == [
            (False, 0, True),
            (False, 1, True),
            (False, 1, None),
            (True, 0, None),
            (True, 0, True),
            (False, 0, True),
            (False, 0, True),
        ]
        assert len(replay.paths) == 7
        assert not replay.browser.browser.navigation_gaps
        assert (
            _scroll_motion(
                read_screen(replay.documents[4], SIZE),
                read_screen(replay.documents[5], SIZE),
            )
            < -2
        )
        with pytest.raises(XError, match="additional observations"):
            replay.browser.observe(previous=source)
    finally:
        replay.phone.close(home=False).require()


def test_captured_pair_retains_identity_without_inventing_native_movement():
    before, after = (read_screen(caption_document(n), SIZE) for n in (243, 244))
    assert _text_continuation(before, after, entering=True) == 1
    with pytest.raises(XError, match="native timeline text"):
        _scroll_motion(before, after)
    assert not after.posts and not after.rejected_posts
    (fragment,) = after.fragments
    assert fragment.body == before.posts[0].body
    assert fragment.actions == ()
    assert fragment.advertising == "unknown"
    assert not hasattr(fragment, "author")
    assert fragment.media[0].kind == "gif"
    assert fragment.media[0].visibility.visible_bounds is None


def test_first_visible_body_edge_remains_pending_without_two_usable_frames():
    replay = CaptionReplay()
    app = replay.browser.browser
    before = read_screen(caption_document(244), SIZE)
    after = read_screen(caption_document("visible"), SIZE)
    try:
        _, offset, moved = app._advance_alignment(before, after, True)
        assert offset == 0 and moved is None
        with pytest.raises(XError, match="native timeline text"):
            _scroll_motion(before, after)
    finally:
        replay.phone.close(home=False).require()


def test_captured_entry_can_reveal_the_first_body_edge_and_gif_together():
    replay = CaptionReplay()
    before, after = (
        read_screen(caption_document(name), SIZE)
        for name in ("entry-before", "entry-visible")
    )
    try:
        _, offset, moved = replay.browser.browser._advance_alignment(
            before, after, False
        )
        assert offset == 1 and moved is None
        with pytest.raises(XError, match="native timeline text"):
            _scroll_motion(before, after)
    finally:
        replay.phone.close(home=False).require()


@pytest.mark.parametrize("mutation", ["body", "media_width", "media_shift", "context"])
def test_pending_exit_requires_unchanged_content_and_agreeing_geometry(mutation):
    replay = CaptionReplay()
    before, after = (
        read_screen(caption_document(f"physical-{n}"), SIZE) for n in (21, 22)
    )
    fragment = after.fragments[0]
    if mutation == "body":
        fragment = replace(fragment, body="changed")
    elif mutation == "context":
        after = replace(after, kind="detail")
    else:
        (media,) = fragment.media
        x1, y1, x2, y2 = media.visibility.bounds
        bounds = (
            (x1 + 1, y1, x2, y2) if mutation == "media_width" else (x1, y1 + 10, x2, y2)
        )
        fragment = replace(
            fragment,
            media=(
                replace(media, visibility=replace(media.visibility, bounds=bounds)),
            ),
        )
    after = replace(after, fragments=(fragment,))
    try:
        with pytest.raises(XError):
            replay.browser.browser._advance_alignment(before, after, True)
    finally:
        replay.phone.close(home=False).require()


def test_stationary_visible_edge_cannot_exit_pending():
    replay = CaptionReplay()
    screen = read_screen(caption_document("physical-21"), SIZE)
    try:
        _, offset, moved = replay.browser.browser._advance_alignment(
            screen, screen, True
        )
        assert offset == 0 and moved is None
    finally:
        replay.phone.close(home=False).require()


@pytest.mark.parametrize(
    "mutation", ["text", "duplicate_old", "duplicate_new", "width", "context"]
)
def test_pending_entry_rejects_changed_ambiguous_or_inconsistent_text(mutation):
    before, after = (read_screen(caption_document(n), SIZE) for n in (243, 244))
    (fragment,) = after.fragments
    if mutation == "text":
        after = replace(after, fragments=(replace(fragment, body="changed"),))
    elif mutation == "duplicate_old":
        before = replace(before, posts=before.posts * 2)
    elif mutation == "duplicate_new":
        after = replace(after, fragments=after.fragments * 2)
    elif mutation == "width":
        before = replace(
            before,
            posts=(
                replace(
                    before.posts[0],
                    body_visibility=replace(
                        before.posts[0].body_visibility, bounds=(177, 399, 1047, 2340)
                    ),
                ),
            ),
        )
    else:
        before = replace(before, collapsed=False)
    with pytest.raises(XError):
        _text_continuation(before, after, entering=True)


@pytest.mark.parametrize("interruption", ["cancel", "deadline", "uncertain"])
def test_pending_phone_interruption_propagates_without_retry(interruption):
    replay = CaptionReplay()
    if interruption == "cancel":
        replay.phone.configure(cancelled=lambda: replay.stage == 4)
        error = InteractionCancelled
    elif interruption == "deadline":
        replay.phone.configure(deadline=100)
        original = replay.sleep

        def expire(seconds):
            original(seconds)
            if replay.stage == 4:
                replay.now = 100

        replay.phone._sleep = expire
        error = SessionExpired
    else:
        replay.injection_error = OSError("injected gesture response lost")
        error = InteractionError
    try:
        with pytest.raises(error) as caught:
            replay.browser.advance()
        if interruption == "uncertain":
            assert caught.value.result.status == Status.UNCERTAIN
        assert len(replay.paths) == (5 if interruption == "uncertain" else 4)
        assert not replay.browser.browsing_valid
        assert replay.browser.browser.verified_account is None
    finally:
        replay.phone.close(home=False).require()
