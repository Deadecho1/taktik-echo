"""Single-attempt native Copy link flows through the real Phone boundary."""

from copy import deepcopy
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


SOAK_URL = "https://x.com/BlaireWhite/status/2123555038706663930"


class CoveredLinkReplay(LinkReplay):
    def __init__(self):
        super().__init__()
        self.xml = self.results = document("soak-source")
        self.sheet = document("soak-share")
        self.copied = document("soak-receipt")
        self.returns = [
            self.copied,
            *[document("soak-covered")] * 5,
            document("soak-return"),
        ]
        self.read_phases = []
        self.read_error = self.cleanup_error = self.cleanup_xml = None
        self.covered_until = None

    def read(self, what):
        if what == "hierarchy" and self.copy_pending:
            cleaning = bool(self.phone._cleaning)
            self.read_phases.append(cleaning)
            if cleaning and self.cleanup_error:
                raise self.cleanup_error
            if not cleaning and self.receipt_reads == 1 and self.read_error:
                raise self.read_error
            if cleaning and self.cleanup_xml:
                self.xml = self.cleanup_xml
            elif self.covered_until is not None:
                self.xml = (
                    self.copied
                    if self.now < self.covered_until
                    else document("soak-return")
                )
            elif self.returns:
                self.xml = self.returns.pop(0)
        return super().read(what)


def covered_started():
    replay = CoveredLinkReplay()
    browser = XBrowser(replay.phone, {"for_you"})
    app = browser.browser
    app.timeline = "for_you"
    app.verified_account = app._expected = "@fixture_owner"
    before = read_screen(replay.xml, SIZE)
    assert len(before.observable_posts) == 1
    app._select(before, before.posts.index(before.observable_posts[0]))
    browser.workflow = "for_you"
    browser._username, browser._valid = "fixture_owner", True
    return replay, browser


def test_captured_preview_clears_before_link_return_and_preserves_occurrence():
    replay, browser = covered_started()
    source = browser.browser.observe()
    before = browser.observe()
    covered = read_screen(replay.copied, SIZE)
    post = next(p for p in covered.posts if p.content_key == source.content_key)
    assert not post.observable
    assert post.body_visibility.overlaps == ((22, 1993, 608, 2257),)
    link = browser.copy_link(before)
    after = browser.observe(previous=before)
    assert link.url == after.post_url == SOAK_URL
    assert link.post_id == after.native_post_id == "2123555038706663930"
    assert link.source_key == after.source_key == before.source_key
    assert after.identity == before.identity
    assert browser.browser.observe() == source
    assert browser.browser._screen.clipboard_text is None
    assert replay.now >= 1.2
    assert replay.events.count(("link", "share")) == 1
    assert replay.events.count(("link", "copy")) == 1
    assert browser.browsing_valid


@pytest.mark.parametrize("receipt_gone", [False, True])
def test_covered_source_times_out_without_returning_or_repeating_copy(receipt_gone):
    replay, browser = covered_started()
    replay.returns = [replay.copied]
    if receipt_gone:
        replay.returns.append(changed_return(document("soak-return"), "unobservable"))
    with pytest.raises(InteractionError, match="Cannot verify.*selected X occurrence"):
        browser.copy_link(browser.observe())
    assert replay.read_phases.count(False) == 9
    assert replay.read_phases.count(True) == 9
    assert replay.now == pytest.approx(9.1)
    assert replay.events.count(("link", "copy")) == 1
    assert browser._post_link is None
    assert not browser.browsing_valid


def test_source_can_return_on_last_read_within_the_bound():
    replay, browser = covered_started()
    replay.returns = [replay.copied] * 8 + [document("soak-return")]
    assert browser.copy_link(browser.observe()).url == SOAK_URL
    assert replay.now == pytest.approx(7.0)
    assert not any(replay.read_phases)
    assert replay.events.count(("link", "copy")) == 1


def test_fast_device_reads_allow_several_seconds_for_preview_expiry():
    replay, browser = covered_started()
    replay.covered_until = 6.0
    before = browser.observe()
    assert browser.copy_link(before).url == SOAK_URL
    assert browser.observe(previous=before).identity == before.identity
    assert 6.0 <= replay.now <= 7.1
    assert not any(replay.read_phases)
    assert replay.events.count(("link", "copy")) == 1


def test_repeated_copy_after_preview_expiry_preserves_the_original_occurrence():
    replay, browser = covered_started()
    before = browser.observe()
    first = browser.copy_link(before)
    replay.copy_pending = False
    replay.receipt_reads = 0
    replay.returns = [replay.copied, document("soak-return")]
    second = browser.copy_link(before)
    assert first == second
    assert browser.observe(previous=before).identity == before.identity
    assert replay.events.count(("link", "copy")) == 2
    assert browser.browsing_valid


def changed_return(xml, problem):
    root = etree.fromstring(xml.encode())
    post = root.xpath('.//node[@bounds="[0,1825][1080,2177]"]')[0]
    if problem == "receipt":
        return xml.replace("2123555038706663930", "2123555038706663931")
    if problem == "author":
        post.xpath('.//node[@text="@BlaireWhite"]')[0].set("text", "@Other")
    elif problem == "body":
        body = post.xpath('.//node[@bounds="[176,1914][1047,2059]"]')[0]
        body.set("text", "A different post body.")
    elif problem == "bounds":
        post.set("bounds", "[0,1824][1080,2177]")
    elif problem == "body_bounds":
        body = post.xpath('.//node[@bounds="[176,1914][1047,2059]"]')[0]
        body.set("bounds", "[176,1915][1047,2059]")
    elif problem == "header_bounds":
        header = post.xpath('.//node[@resource-id="timeline_post"]')[0]
        header.set("bounds", "[176,1859][876,1907]")
    elif problem == "duplicate":
        post.addnext(deepcopy(post))
    elif problem == "context":
        return document("top-receipt")
    elif problem == "unobservable":
        body = post.xpath('.//node[@bounds="[176,1914][1047,2059]"]')[0]
        body.set("visible-to-user", "false")
    else:
        assert problem == "missing"
        post.getparent().remove(post)
    return etree.tostring(root, encoding="unicode")


@pytest.mark.parametrize("stage", ["covered", "return", "final"])
@pytest.mark.parametrize(
    "problem",
    [
        "receipt",
        "author",
        "body",
        "bounds",
        "body_bounds",
        "header_bounds",
        "duplicate",
        "context",
        "missing",
    ],
)
def test_changed_evidence_rejects_link_even_if_original_source_returns(stage, problem):
    replay, browser = covered_started()
    covered = document("soak-covered")
    returned = document("soak-return")
    # Keep the receipt visible for URL mutation after the source becomes observable.
    if stage != "covered" and problem == "receipt":
        root = etree.fromstring(covered.encode())
        overlay = root[-1]
        overlay.set("bounds", "[22,136][608,400]")
        for node in overlay.iterdescendants():
            node.set("bounds", "[22,136][608,400]")
        returned = etree.tostring(root, encoding="unicode")
        assert read_screen(returned, SIZE).observable_posts
    mutated = changed_return(covered if stage == "covered" else returned, problem)
    replay.returns = {
        "covered": [replay.copied, mutated, returned],
        "return": [replay.copied, covered, mutated, returned],
        "final": [replay.copied, returned, mutated, returned],
    }[stage]
    with pytest.raises(InteractionError):
        browser.copy_link(browser.observe())
    assert browser._post_link is None
    assert not browser.browsing_valid
    assert replay.events.count(("link", "copy")) == 1


def test_receipt_disappearing_before_source_is_observable_retains_captured_link():
    replay, browser = covered_started()
    returned = document("soak-return")
    hidden = changed_return(returned, "unobservable")
    screen = read_screen(hidden, SIZE)
    assert screen.clipboard_text is None and not screen.observable_posts
    replay.returns = [replay.copied, hidden, hidden, returned]
    before = browser.observe()
    assert browser.copy_link(before).url == SOAK_URL
    assert browser.observe(previous=before).identity == before.identity
    assert replay.events.count(("link", "copy")) == 1


@pytest.mark.parametrize("expired", [False, True])
@pytest.mark.parametrize("cleanup_fails", [False, True])
def test_interruption_during_wait_escapes_promptly_and_allows_cleanup(
    expired, cleanup_fails
):
    replay, browser = covered_started()
    replay.cleanup_xml = document("soak-return")
    if cleanup_fails:
        replay.cleanup_error = OSError("restoration read lost")
    if expired:
        replay.phone.configure(deadline=0.1)
    else:
        replay.phone.configure(cancelled=lambda: replay.now >= 0.1)
    with pytest.raises(SessionExpired if expired else InteractionCancelled) as caught:
        browser.copy_link(browser.observe())
    assert replay.now == pytest.approx(0.1)
    assert replay.read_phases.count(False) == 2
    assert any(replay.read_phases)
    if cleanup_fails:
        assert isinstance(caught.value.__cause__, InteractionError)
        assert caught.value.__cause__.result.status == Status.UNCERTAIN
    else:
        assert replay.xml == replay.cleanup_xml
    assert replay.events.count(("link", "copy")) == 1
    assert not browser.browsing_valid


@pytest.mark.parametrize(
    "error",
    [
        OSError("verification response lost"),
        InteractionCancelled("stop"),
        SessionExpired("expired"),
    ],
)
def test_wait_failure_preserves_primary_error_when_restoration_fails(error):
    replay, browser = covered_started()
    replay.read_error = error
    replay.cleanup_error = OSError("restoration response lost")
    expected = InteractionError if isinstance(error, OSError) else type(error)
    with pytest.raises(expected) as caught:
        browser.copy_link(browser.observe())
    if isinstance(error, OSError):
        assert caught.value.result.status == Status.UNCERTAIN
        assert "verification response lost" in str(caught.value)
    else:
        assert caught.value is error
    assert isinstance(caught.value.__cause__, InteractionError)
    assert "restoration response lost" in str(caught.value.__cause__)
    assert replay.events.count(("link", "copy")) == 1
    assert not browser.browsing_valid


def test_changed_receipt_error_is_preserved_when_restoration_fails():
    replay, browser = covered_started()
    replay.returns = [
        replay.copied,
        changed_return(document("soak-covered"), "receipt"),
    ]
    replay.cleanup_error = OSError("restoration response lost")
    with pytest.raises(InteractionError, match="copied link changed") as caught:
        browser.copy_link(browser.observe())
    assert isinstance(caught.value.__cause__, InteractionError)
    assert "restoration response lost" in str(caught.value.__cause__)
    assert replay.events.count(("link", "copy")) == 1
    assert not browser.browsing_valid
