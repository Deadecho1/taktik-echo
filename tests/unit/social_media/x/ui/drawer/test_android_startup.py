"""Full-width account verification and native dismissal through the raw device seam."""

import re
from pathlib import Path

import pytest
from taktik.core.shared.phone_interaction import InteractionError, Phone, Status
from taktik.core.shared.phone_interaction._device import TaktikDevice
from taktik.core.social_media.x.services.browsing.browser import XBrowser
from taktik.core.social_media.x.services.browsing.navigation import XError
from taktik.core.social_media.x.ui.screen import PACKAGE, read_screen

FIXTURES = Path(__file__).parents[2] / "fixtures/startup"
SIZE = (1440, 3216)


class RawStartup:
    def __init__(self):
        self.drawer = (FIXTURES / "android-buttons-drawer.xml").read_text()
        self.home = re.sub(
            r"\[(\d+),(\d+)\]",
            lambda match: (
                f"[{round(int(match[1]) * 1440 / 1080)},"
                f"{round(int(match[2]) * 3216 / 2340)}]"
            ),
            (FIXTURES / "drawer-tip-home.xml").read_text(),
        )
        self.stage = "home"
        self.actions = []
        self.now = 0
        self.stuck = False
        self.error = None
        self.drawer_reads = 0
        self.change_account = False

    def app_current(self):
        return {"package": PACKAGE}

    def window_size(self):
        return SIZE

    def app_start(self, package):
        assert package == PACKAGE
        self.actions.append("launch")

    def dump_hierarchy(self):
        if self.stage == "drawer":
            self.drawer_reads += 1
            if self.change_account and self.drawer_reads > 1:
                return self.drawer.replace("@fixture_user", "@different_user")
            return self.drawer
        return self.home

    def sleep(self, seconds):
        self.now += seconds

    def long_click(self, x, y, duration):
        assert self.stage == "home"
        target = next(
            control
            for control in read_screen(self.home, SIZE).controls
            if control.label == "Show navigation drawer"
        ).visibility.visible_bounds
        left, top, right, bottom = target
        assert left <= x < right and top <= y < bottom
        self.actions.append("open_drawer")
        self.stage = "drawer"

    def click(self, x, y):
        assert self.stage == "drawer"
        left, top, right, bottom = read_screen(self.drawer, SIZE).android_back
        assert left <= x < right and top <= y < bottom
        self.actions.append("native_back")
        if not self.stuck:
            self.stage = "home"
        if self.error:
            raise self.error

    def press(self, key):
        raise AssertionError(f"Must use the verified visible Back button: {key}")


@pytest.fixture
def replay():
    raw = RawStartup()
    phone = Phone(
        TaktikDevice(raw, "fixture"), seed=0, clock=lambda: raw.now, sleep=raw.sleep
    )
    browser = XBrowser(phone, {"for_you"})
    yield raw, browser
    phone.close(home=False).require()


def test_verified_full_width_drawer_reaches_feed_through_native_back(replay):
    raw, browser = replay
    browser.start("fixture_user", "for_you")
    assert browser.browser.verified_account == "@fixture_user"
    assert browser.observe().username == "fixture_author"
    assert raw.actions == ["launch", "open_drawer", "native_back"]


@pytest.mark.parametrize("changed_after_read", [False, True])
def test_wrong_or_changed_account_never_dismisses_drawer(replay, changed_after_read):
    raw, browser = replay
    raw.change_account = changed_after_read
    if not changed_after_read:
        raw.drawer = raw.drawer.replace("@fixture_user", "@different_user")
    with pytest.raises(XError, match="active X handle"):
        browser.start("fixture_user", "for_you")
    assert raw.actions == ["launch", "open_drawer"]
    assert not browser.browsing_valid


def test_uncertain_native_back_is_not_repeated_even_if_it_navigated(replay):
    raw, browser = replay
    raw.error = RuntimeError("lost reply after touch")
    with pytest.raises(InteractionError) as error:
        browser.start("fixture_user", "for_you")
    assert error.value.result.status == Status.UNCERTAIN
    assert raw.stage == "home"
    assert raw.actions == ["launch", "open_drawer", "native_back"]
    assert not browser.browsing_valid


def test_native_back_must_reach_verified_home(replay):
    raw, browser = replay
    raw.stuck = True
    with pytest.raises(XError, match="return to X Home"):
        browser.start("fixture_user", "for_you")
    assert raw.actions == ["launch", "open_drawer", "native_back"]
    assert not browser.browsing_valid
