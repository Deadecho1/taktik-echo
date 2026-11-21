"""Replay the delayed search surfaces seen on the pinned TikTok 47.0.3 build."""

from types import SimpleNamespace
from unittest.mock import Mock

import pytest

from taktik.core.shared.browsing import PlatformError
from taktik.core.shared.phone_interaction import InteractionCancelled, Result, Status
from taktik.core.social_media.tiktok.services.browsing.browser import TikTok

PACKAGE = "com.zhiliaoapp.musically"


def screen(contents=""):
    return (
        f'<hierarchy><android.widget.FrameLayout package="{PACKAGE}" '
        f'bounds="[0,0][1440,3216]" enabled="true">{contents}'
        '</android.widget.FrameLayout></hierarchy>'
    )


TOP = (
    f'<android.widget.TextView package="{PACKAGE}" text="Top" '
    'bounds="[104,368][232,528]" enabled="true" selected="false"/>'
)
TILE = (
    f'<android.widget.Button package="{PACKAGE}" content-desc="Video by Creator" '
    'bounds="[68,792][804,1968]" enabled="true"/>'
)


def delayed_search(*, tab_after=1.5, result_after=8, ambiguous=False):
    state = SimpleNamespace(now=0, selected_at=None, opened=False, taps=[])

    def hierarchy():
        if state.opened:
            return screen()
        if state.now < tab_after:
            return screen()
        body = TOP
        if ambiguous:
            body += TOP.replace("[104,368][232,528]", "[400,368][600,528]")
        if state.selected_at is not None and state.now - state.selected_at >= result_after:
            body += TILE
        return screen(body)

    def wait(seconds, **_):
        state.now += seconds

    def tap(rect):
        state.taps.append(rect)
        if rect[1] == 368:
            state.selected_at = state.now
        else:
            assert rect == (68, 792, 804, 1968)
            state.opened = True
        return Result(Status.SUCCESS)

    phone = SimpleNamespace(
        read=lambda kind: (1440, 3216) if kind == "size" else hierarchy(),
        wait=wait,
        tap=tap,
    )
    browser = TikTok(phone, ["search"])
    browser._search_results = Mock()
    browser._read = Mock()
    return browser, state


def test_search_waits_for_tabs_then_delayed_results_before_tapping():
    browser, state = delayed_search()

    browser.transition("search", "herbal remedy shop")

    assert state.opened
    assert len(state.taps) == 2
    assert state.now >= 9.5
    assert browser.workflow == "search"
    browser._read.assert_called()


def test_slow_results_alone_do_not_trigger_the_old_four_second_failure():
    browser, state = delayed_search(tab_after=0, result_after=6)

    browser.transition("search", "herbal remedy shop")

    assert state.opened
    assert len(state.taps) == 2


def test_an_ambiguous_search_tab_is_never_tapped():
    browser, state = delayed_search(tab_after=0, ambiguous=True)
    with pytest.raises(PlatformError, match="ambiguous"):
        browser.transition("search", "herbal remedy shop")
    assert state.taps == []


def test_results_that_never_load_still_fail_with_a_bound():
    browser, state = delayed_search(tab_after=0, result_after=float("inf"))
    with pytest.raises(PlatformError, match="No TikTok search result"):
        browser.transition("search", "herbal remedy shop")
    assert not state.opened
    assert len(state.taps) == 1
    assert state.now <= 20


def test_missing_tabs_time_out_without_tapping():
    browser, state = delayed_search(tab_after=float("inf"))
    with pytest.raises(PlatformError, match="search control did not become ready"):
        browser.transition("search", "herbal remedy shop")
    assert state.taps == []
    assert state.now <= 10


def test_cancellation_interrupts_search_readiness():
    browser, state = delayed_search()
    browser.phone.wait = Mock(side_effect=InteractionCancelled("Stopped"))
    with pytest.raises(InteractionCancelled):
        browser.transition("search", "herbal remedy shop")
    assert state.taps == []
