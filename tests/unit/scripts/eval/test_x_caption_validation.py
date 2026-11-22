"""The soak caption workflow replays real Phone operations without a device."""

import pytest
from unit.social_media.x.services.expansion_replay import LIMIT_TAP as TAP
from unit.social_media.x.services.expansion_replay import limit_selected as selected
from unit.social_media.x.services.expansion_replay import started as short_expansion
from unit.social_media.x.services.long_detail_replay import started as long_detail

from scripts.eval.x_caption_validation import check_caption
from taktik.core.shared.phone_interaction import (
    InteractionCancelled,
    InteractionError,
    Status,
)
from taktik.core.social_media.x.services.browsing.browser import XBrowser
from taktik.core.social_media.x.services.browsing.navigation import XError


def record(events):
    return lambda name, details: events.append((name, details))


def test_clipped_expansion_continues_at_verified_new_occurrence_without_read_credit(
    monkeypatch,
):
    replay, browser = selected(monkeypatch)
    source = browser.observe()
    events = []
    result = check_caption(browser, source, features={}, covered=record(events))
    after = browser.observe()
    assert (
        browser.browsing_valid and browser.browser.verified_account == "@fixture_owner"
    )
    assert after.identity != source.identity and after.source_key != source.source_key
    assert result["source_identity"] == source.identity
    assert result["continuation_identity"] == after.identity
    assert result["original_text_complete"] is False
    assert [name for name, _ in events] == [
        "inline_caption_attempt",
        "inline_limit",
        "recovery",
    ]
    assert replay.events.count(("expand", TAP)) == 1
    assert ("tap", "Show navigation drawer") in replay.events
    assert ("tap", "Close navigation menu") in replay.events
    with pytest.raises(XError, match="stale|changed|current"):
        browser.read_more(source)
    replay.phone.close().require()
    assert replay.closed


def test_supported_inline_expansion_keeps_occurrence_and_earns_only_inline_credit(
    monkeypatch,
):
    _, browser = short_expansion(monkeypatch, wrapper=True)
    source = browser.observe()
    events = []
    result = check_caption(browser, source, features={}, covered=record(events))
    assert result.identity == source.identity and result.source_key != source.source_key
    assert result.caption_expanded and result.caption_type == "full"
    assert [name for name, _ in events] == ["inline_caption_attempt", "read_more"]


@pytest.mark.parametrize(
    "max_scrolls,complete,length", [(0, False, 727), (8, True, 1857)]
)
def test_native_detail_completeness_comes_from_character_coverage(
    max_scrolls, complete, length
):
    replay, app = long_detail()
    browser = XBrowser(replay.phone, {"search"})
    browser.browser = app
    browser.workflow, browser.target, browser._username, browser._valid = (
        "search",
        app.query,
        "fixture_owner",
        True,
    )
    source = browser.observe()
    events = []
    result = check_caption(
        browser,
        source,
        features={"inline_caption_attempt": 1},
        covered=record(events),
        max_scrolls=max_scrolls,
    )
    assert result.source_key == source.source_key
    assert result.main_text_complete is complete and len(result.main_text) == length
    assert result.scrolls == max_scrolls
    assert not result.main_verified and not result.detail.main_post.body_complete
    assert result.detail.main_post.author.removeprefix("@") == source.username
    assert browser.observe().identity == source.identity
    assert [name for name, _ in events] == (
        ["native_caption_attempt", "native_main_text", "native_long_caption"]
        if complete
        else ["native_caption_attempt"]
    )


@pytest.mark.parametrize(
    "stage",
    [
        "expand",
        "recover",
        "cancel",
        "deadline",
        "wrong_account",
        "recover_cancel",
        "recover_deadline",
    ],
)
def test_uncertain_or_interrupted_operations_do_not_become_successful_recovery(
    monkeypatch, stage
):
    replay, browser = selected(monkeypatch)
    source = browser.observe()
    events = []
    tap = replay.tap
    command = replay.command

    def fail_tap(target, exclude, kind):
        tap(target, exclude, kind)
        if target == TAP:
            if stage == "expand":
                raise OSError("tap response lost")
            if stage == "cancel":
                raise InteractionCancelled("cancelled")
            if stage == "deadline":
                replay.phone.configure(deadline=replay.now)

    def fail_recovery(name, value):
        command(name, value)
        if name == "launch" and stage == "recover":
            raise OSError("launch response lost")
        if name == "launch" and stage == "recover_cancel":
            raise InteractionCancelled("cancelled during recovery")
        if name == "launch" and stage == "recover_deadline":
            replay.phone.configure(deadline=replay.now)

    replay.tap, replay.command = fail_tap, fail_recovery
    if stage == "wrong_account":
        browser.browser._expected = "@another_owner"
    expected = (
        InteractionCancelled
        if stage in {"cancel", "deadline", "recover_cancel", "recover_deadline"}
        else InteractionError
    )
    with pytest.raises(expected) as raised:
        check_caption(browser, source, features={}, covered=record(events))
    if stage in {"expand", "recover"}:
        assert raised.value.result.status == Status.UNCERTAIN
    assert not browser.browsing_valid
    assert not any(
        name in {"recovery", "read_more", "native_main_text"} for name, _ in events
    )
    assert replay.events.count(("expand", TAP)) == 1
    replay.phone.close().require()
    assert replay.closed


def test_cleanup_uncertainty_remains_uncertain_after_handled_limit(monkeypatch):
    replay, browser = selected(monkeypatch)
    check_caption(browser, browser.observe(), features={}, covered=lambda *_: None)

    def fail_close():
        raise OSError("keyboard restoration response lost")

    replay.close = fail_close
    result = replay.phone.close()
    assert result.status == Status.UNCERTAIN


def test_recovery_preserves_latest_query_and_invalidates_cached_observations(
    monkeypatch,
):
    _replay, browser = short_expansion(monkeypatch, wrapper=True)
    source = browser.observe()
    browser.browser.result_tab = "latest"
    browser._expanded_source_key = "old expansion"
    browser._post_link = browser._media_inspection = object()
    browser.recover()
    assert browser.browser.query == browser.target
    assert browser.browser.result_tab == "latest"
    assert browser.observe().identity != source.identity
    assert (
        browser._media_inspection
        is browser._post_link
        is browser._expanded_source_key
        is None
    )


def test_handled_limit_schedules_native_read_then_still_requires_inline_success(
    monkeypatch,
):
    features, events = {}, []

    def covered(name, details):
        features[name] = features.get(name, 0) + 1
        events.append((name, details))

    with monkeypatch.context() as limit_patch:
        _, browser = selected(limit_patch)
        check_caption(browser, browser.observe(), features=features, covered=covered)
    assert "read_more" not in features and "native_long_caption" not in features
    replay, app = long_detail()
    native_browser = XBrowser(replay.phone, {"search"})
    native_browser.browser = app
    native_browser.workflow, native_browser._valid = "search", True
    check_caption(
        native_browser, native_browser.observe(), features=features, covered=covered
    )
    assert "native_long_caption" in features and "read_more" not in features
    _, inline_browser = short_expansion(monkeypatch, wrapper=True)
    check_caption(
        inline_browser, inline_browser.observe(), features=features, covered=covered
    )
    assert features["read_more"] == features["native_long_caption"] == 1
    limit = next(details for name, details in events if name == "inline_limit")
    assert limit["original_text_complete"] is False


@pytest.mark.parametrize("failure", ["author", "uncertain"])
def test_native_failure_does_not_earn_coverage_or_trigger_recovery(failure):
    replay, app = long_detail()
    browser = XBrowser(replay.phone, {"search"})
    browser.browser = app
    browser.workflow, browser._valid = "search", True
    source = browser.observe()
    if failure == "author":
        replay.native = replay.native.replace("@" + source.username, "@someone_else")
    else:
        replay.native_error = OSError("native read response lost")
    events = []
    with pytest.raises(InteractionError) as raised:
        check_caption(
            browser,
            source,
            features={"inline_caption_attempt": 1},
            covered=record(events),
        )
    if failure == "uncertain":
        assert raised.value.result.status == Status.UNCERTAIN
    assert not events and not browser.browsing_valid
