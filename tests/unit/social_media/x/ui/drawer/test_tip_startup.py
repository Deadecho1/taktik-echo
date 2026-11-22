"""Drawer-tip recognition verified through the public startup and raw device seam."""

import hashlib
import json
from copy import deepcopy

import pytest
from lxml import etree
from unit.paths import CORE
from unit.x_fixtures import xml_fixture

from taktik.core.shared.phone_interaction import (
    InteractionCancelled,
    InteractionError,
    Phone,
    SessionExpired,
    Status,
)
from taktik.core.shared.phone_interaction._device import TaktikDevice
from taktik.core.shared.ui.geometry import bounds
from taktik.core.social_media.x.services.browsing.browser import XBrowser
from taktik.core.social_media.x.services.browsing.navigation import XError
from taktik.core.social_media.x.ui.screen import PACKAGE, read_screen

FIXTURES = CORE / "tests/unit/social_media/x/fixtures/startup"
SIZE = (1080, 2340)


def document(name):
    return xml_fixture(FIXTURES / f"drawer-tip{name}.xml")


class RawStartup:
    def __init__(self):
        self.home, self.drawer = document("-home"), document("")
        self.stage = "home"
        self.actions, self.reads = [], []
        self.now = 0
        self.close_error = None
        self.close_stuck = False
        self.foreground = PACKAGE

    def app_current(self):
        return {"package": self.foreground}

    def window_size(self):
        return SIZE

    def app_start(self, package):
        assert package == PACKAGE
        self.actions.append("launch")

    def dump_hierarchy(self):
        self.reads.append(self.stage)
        return self.drawer if self.stage == "drawer" else self.home

    def sleep(self, seconds):
        self.now += seconds

    def long_click(self, x, y, duration):
        if self.stage == "home" and 273 <= x < 558 and 301 <= y < 433:
            root = etree.fromstring(self.home.encode())
            for label, selected in (("For you", "false"), ("Following", "true")):
                node = root.xpath(".//*[@content-desc=$label]", label=label)[0]
                node.getparent().set("selected", selected)
            self.home = etree.tostring(root, encoding="unicode")
            self.actions.append("select_following")
        elif self.stage == "home":
            assert 11 <= x < 165 and 147 <= y < 301
            self.actions.append("open_drawer")
            self.stage = "drawer"
        else:
            assert 990 <= x < 1080 and 136 <= y < 2340
            self.actions.append("close_drawer")
            if self.close_error:
                raise self.close_error
            if not self.close_stuck:
                self.stage = "home"


@pytest.fixture
def replay():
    raw = RawStartup()
    phone = Phone(
        TaktikDevice(raw, "fixture"), seed=0, clock=lambda: raw.now, sleep=raw.sleep
    )
    browser = XBrowser(phone, {"for_you", "following"})
    yield raw, browser
    phone.close(home=False).require()


@pytest.mark.parametrize("workflow", ["for_you", "following"])
def test_tip_startup_verifies_account_and_selects_a_source(replay, workflow):
    raw, browser = replay
    browser.start("fixture_owner", workflow)
    observation = browser.observe()
    assert observation.username == "fixture_author"
    assert browser.browser.verified_account == "@fixture_owner"
    assert browser.browsing_valid
    assert browser.browser._screen.tab == (
        "Following" if workflow == "following" else "For you"
    )
    assert raw.actions == ["launch", "open_drawer", "close_drawer"] + (
        ["select_following"] if workflow == "following" else []
    )
    assert raw.reads[:4] == ["home", "drawer", "home", "home"]


def test_tip_geometry_remains_an_exclusion():
    screen = read_screen(document(""), SIZE)
    assert screen.kind == "drawer"
    assert screen.active_account == "@fixture_owner"
    assert (0, 923, 924, 1143) in screen.overlaps
    (close,) = [t for t in screen.controls if t.label == "Close navigation menu"]
    assert close.visibility.overlaps == ((0, 0, 1080, 136),)
    assert not screen.posts and not screen.scroll_areas


@pytest.mark.parametrize("seed", [0, 3, 7, 41])
def test_partial_close_occlusion_excludes_the_tip_from_physical_taps(seed):
    raw = RawStartup()
    root = etree.fromstring(raw.drawer.encode())
    for node in root[0].iter():
        x1, y1, x2, y2 = bounds(node)
        node.set("bounds", f"[{x1 + 110},{y1}][{x2 + 110},{y2}]")
    raw.drawer = etree.tostring(root, encoding="unicode")
    screen = read_screen(raw.drawer, SIZE)
    target = next(t for t in screen.controls if t.label == "Close navigation menu")
    assert (110, 923, 1034, 1143) in target.visibility.overlaps
    close = raw.long_click

    def check_point(x, y, duration):
        if raw.stage == "drawer":
            assert not (110 <= x < 1034 and 923 <= y < 1143)
        close(x, y, duration)

    raw.long_click = check_point
    phone = Phone(
        TaktikDevice(raw, "fixture"), seed=seed, clock=lambda: raw.now, sleep=raw.sleep
    )
    try:
        browser = XBrowser(phone, {"for_you"})
        browser.start("fixture_owner", "for_you")
        assert browser.observe().username == "fixture_author"
    finally:
        phone.close(home=False).require()


def changed_drawer(problem):
    root = etree.fromstring(document("").encode())
    tip, _, main = root
    if problem == "duplicate_tip":
        root.append(deepcopy(tip))
    elif problem == "duplicate_main":
        root.append(deepcopy(main))
    elif problem == "foreign_overlay":
        root.append(
            etree.Element("node", package="example.other", bounds="[0,0][1080,2340]")
        )
    elif problem == "foreign_tip":
        tip.set("package", "example.other")
    elif problem == "foreign_descendant":
        tip[0].set("package", "example.other")
    elif problem == "extra_tip_child":
        tip.append(deepcopy(tip[0]))
    elif problem == "wrong_tip_text":
        tip.xpath('.//*[@text!=""]')[0].set("text", "An unknown native tip")
    elif problem == "unsupported_drawer":
        main.xpath('.//*[@text="Profile"]')[0].set("text", "Unknown row")
    elif problem == "missing_landing":
        main.xpath('.//*[@resource-id="MainLanding"]')[0].set("resource-id", "Unknown")
    elif problem == "wrong_account":
        main.xpath('.//*[@text="@fixture_owner"]')[0].set("text", "@another_owner")
    elif problem == "covered_account":
        for node in tip.iter():
            x1, y1, x2, y2 = bounds(node)
            node.set("bounds", f"[{x1},{y1 - 550}][{x2},{y2 - 550}]")
    elif problem == "covered_close":
        main.xpath('.//*[@content-desc="Close navigation menu"]')[0].set(
            "bounds", "[900,978][924,1082]"
        )
    elif problem == "tip_over_home":
        home = etree.fromstring(document("-home").encode())
        home.insert(0, tip)
        root = home
    elif problem == "keyboard":
        root.append(
            etree.Element(
                "node",
                package="com.google.android.inputmethod.latin",
                bounds="[0,1200][1080,2340]",
            )
        )
    elif problem == "tip_only":
        root.remove(main)
    else:
        index, attr, value = problem
        list(tip.iter())[index].set(attr, value)
    return etree.tostring(root, encoding="unicode")


@pytest.mark.parametrize(
    "problem",
    [
        "duplicate_tip",
        "duplicate_main",
        "foreign_overlay",
        "foreign_tip",
        "foreign_descendant",
        "extra_tip_child",
        "wrong_tip_text",
        "unsupported_drawer",
        "missing_landing",
        "wrong_account",
        "covered_account",
        "covered_close",
        "tip_over_home",
        "keyboard",
        "tip_only",
        (0, "bounds", "[0,0][1080,2340]"),
        (0, "bounds", "[-1,923][924,1143]"),
        (5, "bounds", "[55,978][1000,1082]"),
        (0, "resource-id", "unknown"),
        (3, "content-desc", "Unknown action"),
        (3, "clickable", "false"),
        (5, "clickable", "true"),
        (2, "enabled", "false"),
        (3, "visible-to-user", "false"),
        (1, "scrollable", "true"),
    ],
)
def test_unsupported_tip_or_drawer_never_closes_or_browses(replay, problem):
    raw, browser = replay
    raw.drawer = changed_drawer(problem)
    with pytest.raises(InteractionError):
        browser.start("fixture_owner", "for_you")
    assert raw.actions == ["launch", "open_drawer"]
    assert browser.browser.verified_account is None
    assert not browser.browsing_valid


@pytest.mark.parametrize("stage", ["drawer", "home"])
def test_uncertain_close_is_not_repeated_even_if_home_appears(replay, stage):
    raw, browser = replay
    close = raw.long_click

    def uncertain_close(*args):
        was_drawer = raw.stage == "drawer"
        close(*args)
        if was_drawer:
            raw.stage = stage
            raise OSError("Synthetic lost acknowledgement")

    raw.long_click = uncertain_close
    with pytest.raises(InteractionError) as failure:
        browser.start("fixture_owner", "for_you")
    assert failure.value.result.status == Status.UNCERTAIN
    assert raw.actions == ["launch", "open_drawer", "close_drawer"]
    assert not browser.browsing_valid
    assert browser.browser.verified_account is None


def test_persistent_tip_after_close_exhausts_reads_without_another_tap(replay):
    raw, browser = replay
    raw.close_stuck = True
    with pytest.raises(XError, match="return to X Home"):
        browser.start("fixture_owner", "for_you")
    assert raw.actions == ["launch", "open_drawer", "close_drawer"]
    assert raw.reads == ["home"] + ["drawer"] * 9
    assert not browser.browsing_valid


@pytest.mark.parametrize("interruption", ["cancel", "deadline", "foreground"])
def test_interruption_during_tip_wait_invalidates_startup(replay, interruption):
    raw, browser = replay
    phone = browser.browser.phone
    raw.close_stuck = True
    if interruption == "cancel":
        phone.configure(cancelled=lambda: raw.now > 0)
        expected = InteractionCancelled
    elif interruption == "deadline":
        phone.configure(deadline=0.1)
        expected = SessionExpired
    else:
        raw.app_current = lambda: {"package": "example.other" if raw.now else PACKAGE}
        expected = XError
    with pytest.raises(expected):
        browser.start("fixture_owner", "for_you")
    assert raw.actions == ["launch", "open_drawer", "close_drawer"]
    assert not browser.browsing_valid
    assert browser.browser.verified_account is None


def test_window_order_does_not_choose_the_primary_window(replay):
    raw, browser = replay
    root = etree.fromstring(raw.drawer.encode())
    root[:] = list(reversed(root))
    raw.drawer = etree.tostring(root, encoding="unicode")
    browser.start("fixture_owner", "for_you")
    assert browser.observe().username == "fixture_author"


def test_already_open_tip_drawer_is_verified_before_reopening(replay):
    raw, browser = replay
    raw.stage = "drawer"
    browser.start("fixture_owner", "for_you")
    assert raw.actions == ["launch", "close_drawer", "open_drawer", "close_drawer"]
    assert browser.observe().username == "fixture_author"


def test_tip_free_drawer_keeps_existing_startup(replay):
    raw, browser = replay
    root = etree.fromstring(raw.drawer.encode())
    root.remove(root[0])
    raw.drawer = etree.tostring(root, encoding="unicode")
    browser.start("fixture_owner", "for_you")
    assert browser.observe().username == "fixture_author"


def test_synthetic_fixture_integrity():
    manifest = json.loads((FIXTURES / "drawer-tip-manifest.json").read_text())
    assert manifest["kind"] == "synthetic_native_layout"
    for item in manifest["fixtures"]:
        assert (
            hashlib.sha256((FIXTURES / item["file"]).read_bytes()).hexdigest()
            == item["sha256"]
        )
