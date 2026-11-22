"""Stationary clipboard dismissal through the public browser and raw transport."""

from copy import deepcopy
from pathlib import Path

import pytest
from lxml import etree
from unit.x_fixtures import SIZE, fixture_manifest, xml_fixture

from taktik.core.shared.phone_interaction import (
    InteractionCancelled,
    InteractionError,
    Phone,
    SessionExpired,
)
from taktik.core.shared.phone_interaction._device import TaktikDevice
from taktik.core.shared.ui.geometry import bounds
from taktik.core.social_media.x.services.browsing.browser import XBrowser
from taktik.core.social_media.x.services.browsing.navigation import XError
from taktik.core.social_media.x.ui.screen import PACKAGE, read_screen

FIXTURES = Path(__file__).parent / "fixtures/links"


def document(number):
    return xml_fixture(FIXTURES / f"fullscreen-dismissal-{number}.xml")


class RawReplay:
    def __init__(self):
        self.documents = [document(i) for i in range(12)]
        self.stage = 0
        self.now = 0
        self.actions = []
        self.reads = []

    def app_current(self):
        return {"package": PACKAGE}

    def window_size(self):
        return SIZE

    def dump_hierarchy(self):
        self.reads.append(self.stage)
        xml = self.documents[self.stage]
        self.stage = min(self.stage + 1, len(self.documents) - 1)
        return xml

    def sleep(self, seconds):
        self.now += seconds

    def long_click(self, x, y, duration):
        self.actions.append((self.stage, x, y))
        region = {3: (1003, 1827, 1047, 1871), 5: (220, 1996, 418, 2230)}[self.stage]
        assert region[0] <= x < region[2] and region[1] <= y < region[3]

    def swipe_points(self, path, duration):
        self.actions.append(("scroll", path, duration))


@pytest.fixture
def replay():
    raw = RawReplay()
    phone = Phone(
        TaktikDevice(raw, "fixture"), seed=0, clock=lambda: raw.now, sleep=raw.sleep
    )
    browser = XBrowser(phone, {"for_you"})
    app = browser.browser
    app.timeline = "for_you"
    app.verified_account = app._expected = "@fixture_owner"
    screen = read_screen(raw.documents[0], SIZE)
    app._select(
        screen,
        next(
            i for i, post in enumerate(screen.posts) if post.author == "@fixture_author"
        ),
    )
    browser.workflow, browser._username, browser._valid = (
        "for_you",
        "fixture_owner",
        True,
    )
    yield raw, browser
    phone.close(home=False).require()


def copied(replay):
    raw, browser = replay
    source = browser.observe()
    link = browser.copy_link(source)
    assert browser.observe(previous=source).post_url == link.url
    current = browser.observe(previous=source)
    assert not browser.act("skip", current).advanced
    assert raw.reads == list(range(10))
    assert len(raw.actions) == 2
    return source, link


def test_fullscreen_dismissal_retains_verified_source_and_link(replay):
    raw, browser = replay
    source, link = copied(replay)
    after = browser.observe(previous=source)
    assert after.identity == source.identity
    assert after.source_key == link.source_key
    assert after.post_url == link.url
    assert raw.reads == list(range(12))
    assert len(raw.actions) == 2
    assert browser.browsing_valid
    assert browser.browser._screen.clipboard_bounds is None
    assert raw.now == pytest.approx(0.3)


def test_empty_fullscreen_window_has_no_actionable_or_observable_evidence():
    screen = read_screen(document(10), SIZE)
    assert screen.kind == "unsupported"
    assert screen.reason == "Unidentified empty Android System UI window."
    assert screen.clipboard_text is None
    assert not screen.controls and not screen.posts and not screen.scroll_areas
    hidden = screen.obscured_screen
    assert hidden.kind == "home" and hidden.collapsed
    assert hidden.clipboard_bounds == (0, 0, *SIZE)
    assert hidden.clipboard_text is None
    assert not hidden.observable_posts
    assert all((0, 0, *SIZE) in post.visibility.overlaps for post in hidden.posts)


@pytest.mark.parametrize("action", ["observe", "advance", "like", "copy_link"])
def test_persistent_fullscreen_window_exhausts_read_bound_before_any_action(
    replay, action
):
    raw, browser = replay
    source, _ = copied(replay)
    raw.documents = raw.documents[:11]
    with pytest.raises(XError, match="clipboard dismissal within the read limit"):
        if action == "like":
            browser.act(action, source)
        elif action == "copy_link":
            browser.copy_link(source)
        else:
            getattr(browser, action)()
    assert raw.reads == list(range(10)) + [10] * 8
    assert raw.now == pytest.approx(2.1)
    assert len(raw.actions) == 2
    assert not browser.browsing_valid
    assert browser.browser.verified_account is None


def change_document(xml, problem):
    root = etree.fromstring(xml.encode())
    window = root[-1]
    if problem == "foreign_window":
        window.set("package", "example.other")
    elif problem == "foreign_app_node":
        root[0][0].set("package", "example.other")
    elif problem == "duplicate_status":
        root.insert(1, deepcopy(root[1]))
    elif problem == "duplicate_app":
        root.insert(0, deepcopy(root[0]))
    elif problem == "duplicate_empty":
        root.append(deepcopy(window))
    elif problem == "receipt_and_empty":
        root.append(etree.fromstring(document(9).encode())[-1])
    elif problem == "window_child":
        window.append(etree.Element("node", package=PACKAGE))
    elif problem == "status_geometry":
        root[1].set("bounds", "[0,0][1080,135]")
    elif problem in {"window_top", "window_left", "window_right", "window_bottom"}:
        window.set(
            "bounds",
            {
                "window_top": "[0,1][1080,2340]",
                "window_left": "[1,0][1080,2340]",
                "window_right": "[0,0][1079,2340]",
                "window_bottom": "[0,0][1080,2339]",
            }[problem],
        )
    elif problem in {
        "author",
        "body",
        "source_geometry",
        "duplicate_source",
        "missing_source",
    }:
        author = root.xpath('.//*[@text="@fixture_author"]')[0]
        source = author.getparent().getparent()
        if problem == "author":
            author.set("text", "@another_writer")
        elif problem == "body":
            body = next(n for n in source if n.get("text", "").startswith("Synthetic"))
            body.set("text", "A different fictional account of the exhibit.")
        elif problem == "source_geometry":
            x1, y1, x2, y2 = bounds(source)
            source.set("bounds", f"[{x1 + 1},{y1}][{x2},{y2}]")
        elif problem == "duplicate_source":
            source.addnext(deepcopy(source))
        else:
            source.getparent().remove(source)
    elif problem == "context":
        scope = root.xpath('.//*[@resource-id="scaffold_home_tabbed"]')[0]
        scope.set("resource-id", "Search")
    else:
        attribute, value = problem
        window.set(attribute, value)
    return etree.tostring(root, encoding="unicode")


@pytest.mark.parametrize(
    "problem",
    [
        "foreign_window",
        "foreign_app_node",
        "duplicate_status",
        "duplicate_app",
        "duplicate_empty",
        "receipt_and_empty",
        "window_child",
        "status_geometry",
        "window_top",
        "window_left",
        "window_right",
        "window_bottom",
        "author",
        "body",
        "source_geometry",
        "duplicate_source",
        "missing_source",
        "context",
        *(
            (flag, "true")
            for flag in (
                "checkable",
                "checked",
                "clickable",
                "focusable",
                "focused",
                "scrollable",
                "long-clickable",
                "password",
                "selected",
            )
        ),
        ("enabled", "false"),
        ("visible-to-user", "false"),
        ("text", "Unexpected"),
        ("content-desc", "Unexpected"),
        ("resource-id", "unexpected"),
        ("hint", "Unexpected"),
        ("class", "android.widget.LinearLayout"),
    ],
)
def test_ambiguous_changed_or_unsupported_context_is_rejected_before_wait(
    replay, problem
):
    raw, browser = replay
    source, _ = copied(replay)
    raw.documents[10] = change_document(raw.documents[10], problem)
    with pytest.raises(XError):
        browser.observe(previous=source)
    assert len(raw.reads) == 11
    assert raw.now == 0
    assert len(raw.actions) == 2
    assert not browser.browsing_valid


@pytest.mark.parametrize("receipt", [False, True])
def test_unknown_account_or_missing_prior_receipt_cannot_wait(replay, receipt):
    raw, browser = replay
    source, _ = copied(replay)
    if receipt:
        browser.browser.verified_account = None
    else:
        browser.browser._screen = read_screen(document(11), SIZE)
    with pytest.raises(XError):
        browser.observe(previous=source)
    assert raw.now == 0
    assert len(raw.actions) == 2
    assert not browser.browsing_valid


@pytest.mark.parametrize(
    "interruption", ["cancel", "deadline", "read_error", "foreground"]
)
def test_fullscreen_wait_preserves_phone_interruption_and_foreground_checks(
    replay, interruption
):
    raw, browser = replay
    source, _ = copied(replay)
    phone = browser.browser.phone
    if interruption == "cancel":
        phone.configure(cancelled=lambda: raw.now > 0)
        error = InteractionCancelled
    elif interruption == "deadline":
        phone.configure(deadline=0.1)
        error = SessionExpired
    elif interruption == "read_error":
        original = raw.dump_hierarchy

        def fail_read():
            if raw.stage == 11:
                raise OSError("Synthetic transport unavailable.")
            return original()

        raw.dump_hierarchy = fail_read
        error = InteractionError
    else:
        raw.app_current = lambda: {"package": "example.other" if raw.now else PACKAGE}
        error = XError
    with pytest.raises(error):
        browser.observe(previous=source)
    assert len(raw.actions) == 2
    assert not browser.browsing_valid


@pytest.mark.parametrize(
    "problem",
    [
        "author",
        "body",
        "source_geometry",
        "duplicate_source",
        "missing_source",
        "context",
        "status_geometry",
    ],
)
def test_final_unobscured_return_still_verifies_source_and_context(replay, problem):
    raw, browser = replay
    source, _ = copied(replay)
    raw.documents[11] = change_document(raw.documents[11], problem)
    with pytest.raises(XError):
        browser.observe(previous=source)
    assert raw.reads == list(range(12))
    assert len(raw.actions) == 2
    assert not browser.browsing_valid


def test_synthetic_fixture_integrity():
    manifest = fixture_manifest(FIXTURES / "fullscreen-dismissal-manifest.json")
    assert manifest["kind"] == "synthetic_native_layout"


def test_captured_sequence_reaches_advance_without_inventing_a_successor(replay):
    raw, browser = replay
    copied(replay)
    # No post-gesture capture exists here; subsequent reads repeat the clear frame.
    with pytest.raises(XError, match="next X post within the scrolling limit"):
        browser.advance()
    assert raw.reads[:12] == list(range(12))
    assert all(stage == 11 for stage in raw.reads[12:])
    assert len([action for action in raw.actions if action[0] == "scroll"]) == 8
    assert not browser.browsing_valid


def test_changed_receipt_cannot_replace_the_original_during_fullscreen_wait(replay):
    raw, browser = replay
    source, _ = copied(replay)
    raw.documents[11] = document(9).replace(
        "1000000000000000001", "1000000000000000002"
    )
    with pytest.raises(XError, match="receipt changed"):
        browser.observe(previous=source)
    assert raw.reads == list(range(12))
    assert len(raw.actions) == 2
    assert not browser.browsing_valid


@pytest.mark.parametrize("transients", [1, 7])
def test_fullscreen_wait_requires_clear_return_before_last_read(replay, transients):
    raw, browser = replay
    source, _ = copied(replay)
    raw.documents[10:] = [document(10)] * transients + [document(11)]
    assert browser.observe(previous=source).identity == source.identity
    assert len(raw.reads) == 11 + transients
    assert raw.now == pytest.approx(transients * 0.3)
    assert len(raw.actions) == 2
