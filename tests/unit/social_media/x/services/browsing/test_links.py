"""Single-attempt native Copy link flows through the real Phone boundary."""

from dataclasses import replace

import pytest
from lxml import etree
from unit.social_media.x.services.browsing.test_search import SearchReplay
from unit.social_media.x.ui.test_inspection_screen import (
    LINK_QUERY as QUERY,
)
from unit.social_media.x.ui.test_inspection_screen import (
    LINK_URL as URL,
)
from unit.social_media.x.ui.test_inspection_screen import (
    SIZE,
)
from unit.social_media.x.ui.test_inspection_screen import (
    link_document as document,
)

from taktik.core.shared.phone_interaction import (
    InteractionCancelled,
    InteractionError,
    SessionExpired,
    Status,
)
from taktik.core.social_media.x.services.browsing.browser import XBrowser
from taktik.core.social_media.x.services.browsing.navigation import X
from taktik.core.social_media.x.ui.screen import read_screen


class LinkReplay(SearchReplay):
    def __init__(self):
        super().__init__()
        self.results = self.latest = document("source")
        self.sheet = document("share")
        self.copied = document("copied")
        self.after = None
        self.share_error = self.copy_error = None
        self.close_error = None
        self.foreground = "com.twitter.android"
        self.copy_pending = False
        self.receipt_reads = 0

    def read(self, what):
        if what == "app":
            return {"package": self.foreground}
        if what == "hierarchy" and self.copy_pending:
            self.receipt_reads += 1
            if self.receipt_reads > 1 and self.after:
                self.xml = self.after
        return super().read(what)

    def tap(self, target, exclude, kind):
        screen = read_screen(self.xml, SIZE)
        targets = (*screen.controls, *(a for p in screen.posts for a in p.actions))
        matches = [
            t.label
            for t in targets
            if t.visibility.visible_bounds
            and t.visibility.visible_bounds[0]
            <= target[0]
            < target[2]
            <= t.visibility.visible_bounds[2]
            and t.visibility.visible_bounds[1]
            <= target[1]
            < target[3]
            <= t.visibility.visible_bounds[3]
        ]
        if matches == ["Share"]:
            self.events.append(("link", "share"))
            self.xml = self.sheet
            if self.share_error:
                raise self.share_error
        elif matches == ["Copy link"]:
            self.events.append(("link", "copy"))
            self.xml = self.copied
            self.copy_pending = True
            if self.copy_error:
                raise self.copy_error
        elif matches == ["Close sheet"]:
            self.events.append(("link", "close"))
            if self.close_error:
                raise self.close_error
            self.xml = self.results
        else:
            super().tap(target, exclude, kind)


def started(browser=False):
    replay = LinkReplay()
    if browser:
        replay.results = document("top-source")
        replay.copied = document("top-receipt")
        replay.sheet = document("top-share")
    app = XBrowser(replay.phone, {"search"}) if browser else X(replay.phone)
    if browser:
        app.start("fixture_owner", "search", target=QUERY)
    else:
        app.start("fixture_owner", "search", query=QUERY, result_tab="latest")
    return replay, app


def test_copy_binds_the_native_url_and_preserves_the_selected_occurrence():
    replay, app = started()
    source = app.observe()
    link = app.copy_link()
    assert link.url == URL and link.post_id == "2123169377855922254"
    assert link.author == source.author == "@NASA"
    assert link.source_key == source.content_key == app.observe().content_key
    assert replay.events.count(("link", "share")) == 1
    assert replay.events.count(("link", "copy")) == 1
    assert app.verified_account == "@fixture_owner"


def test_browser_enriches_observations_without_replacing_local_identity():
    _replay, app = started(browser=True)
    before = app.observe()
    assert before.native_post_id is None and before.post_url is None
    link = app.copy_link(before)
    after = app.observe(previous=before)
    assert after.native_post_id == link.post_id
    assert after.post_url == URL
    assert before.identity == after.identity
    assert before.source_key == after.source_key == link.source_key
    assert before.caption == after.caption
    app.start("fixture_owner", "search", target=QUERY)
    assert app.observe().post_url is None


def test_browser_rejects_stale_decisions_before_opening_share():
    replay, app = started(browser=True)
    with pytest.raises(InteractionError):
        app.copy_link(replace(app.observe(), identity="old"))
    assert not any(e[0] == "link" for e in replay.events)


@pytest.mark.parametrize(
    "problem",
    [
        "no_receipt",
        "wrong_author",
        "malformed",
        "different_post",
        "query",
        "final_url",
        "final_author",
        "final_missing_post",
    ],
)
def test_unverified_links_never_escape_and_copy_is_not_retried(problem):
    replay, app = started()
    if problem == "no_receipt":
        replay.copied = document("source")
    elif problem == "wrong_author":
        replay.copied = replay.copied.replace("x.com/NASA/", "x.com/Other/")
    elif problem == "malformed":
        replay.copied = replay.copied.replace("https://x.com/", "https://evil.test/")
    elif problem == "different_post":
        replay.copied = replay.copied.replace(
            "stellar merger", "different stellar merger"
        )
    elif problem == "query":
        replay.copied = replay.copied.replace("from:NASA", "from:Other")
    elif problem == "final_url":
        replay.after = replay.copied.replace(
            "2123169377855922254", "2123169377855922255"
        )
    elif problem == "final_author":
        replay.after = replay.copied.replace("@NASA", "@Other")
    else:
        replay.after = document("share")
    with pytest.raises(InteractionError):
        app.copy_link()
    assert app.verified_account is None
    assert replay.events.count(("link", "copy")) == 1


@pytest.mark.parametrize("stage", ["share", "copy"])
@pytest.mark.parametrize(
    "error",
    [OSError("response lost"), InteractionCancelled("stop"), SessionExpired("expired")],
)
def test_transport_failure_and_cancellation_preserve_cleanup_without_repeating(
    stage, error
):
    replay, app = started()
    setattr(replay, stage + "_error", error)
    with pytest.raises(
        InteractionCancelled
        if isinstance(error, InteractionCancelled)
        else InteractionError
    ) as caught:
        app.copy_link()
    if isinstance(error, OSError):
        assert caught.value.result.status == Status.UNCERTAIN
    assert app.verified_account is None
    assert replay.events.count(("link", stage)) == 1
    if stage == "share":
        assert ("link", "close") in replay.events
        assert ("link", "copy") not in replay.events


def test_missing_copy_control_closes_the_sheet_without_copying():
    replay, app = started()
    # A recognized sheet disappears before the required pre-copy reread.
    snapshot = app._snapshot
    calls = 0

    def changed():
        nonlocal calls
        result = snapshot()
        if result.kind == "share":
            calls += 1
            if calls == 2:
                return replace(result, controls=result.controls[:1])
        return result

    app._snapshot = changed
    with pytest.raises(InteractionError):
        app.copy_link()
    assert ("link", "close") in replay.events
    assert ("link", "copy") not in replay.events


def test_receipt_disappearance_after_capture_does_not_change_the_link():
    replay, app = started()
    replay.after = document("source")
    assert app.copy_link().url == URL


def test_old_receipt_must_disappear_before_copy_can_be_issued():
    replay, app = started()
    root = etree.fromstring(replay.sheet.encode())
    old = etree.fromstring(document("copied").encode())[0]
    assert old.get("package") == "com.android.systemui"
    root.insert(0, old)
    replay.sheet = etree.tostring(root, encoding="unicode")
    with pytest.raises(InteractionError):
        app.copy_link()
    assert ("link", "copy") not in replay.events


def test_explicit_restart_dismisses_retained_share_and_reverifies_account():
    replay = LinkReplay()
    replay.xml = replay.sheet
    app = X(replay.phone)
    app.start("fixture_owner", "search", query=QUERY, result_tab="latest")
    assert ("link", "close") in replay.events
    assert ("tap", "Show navigation drawer") in replay.events
    assert app.verified_account == "@fixture_owner"
    assert app.observe().author == "@NASA"
    assert ("link", "copy") not in replay.events


def test_cleanup_failure_preserves_the_original_cancellation():
    replay, app = started()
    cancellation = InteractionCancelled("cancelled before copy")
    replay.share_error = cancellation
    replay.close_error = OSError("dismissal response lost")
    with pytest.raises(InteractionCancelled) as caught:
        app.copy_link()
    assert caught.value is cancellation
    assert isinstance(caught.value.__cause__, InteractionError)
    assert replay.events.count(("link", "close")) == 1
    assert ("link", "copy") not in replay.events
    assert app.verified_account is None
