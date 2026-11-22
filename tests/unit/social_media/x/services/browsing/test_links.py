"""Single-attempt native Copy link flows through the real Phone boundary."""

from copy import deepcopy
from dataclasses import replace

import pytest
from lxml import etree
from unit.social_media.x.services.inspection_inputs import LINK_FIXTURES
from unit.social_media.x.services.inspection_inputs import LINK_QUERY as QUERY
from unit.social_media.x.services.inspection_inputs import LINK_URL as URL
from unit.social_media.x.services.inspection_inputs import link_document as document
from unit.social_media.x.services.link_transport import GlyphLinkReplay, glyph_browser
from unit.social_media.x.services.search_replay import SearchReplay
from unit.x_fixtures import SIZE, fixture_manifest

from taktik.core.shared.phone_interaction import (
    InteractionCancelled,
    InteractionError,
    SessionExpired,
    Status,
)
from taktik.core.social_media.x.services.browsing.browser import XBrowser
from taktik.core.social_media.x.services.browsing.navigation import X, XError
from taktik.core.social_media.x.services.browsing.selection import _control
from taktik.core.social_media.x.ui.screen import read_screen


@pytest.mark.parametrize("point", [(540, 525), (100, 100), (500, 2150)])
def test_sheet_replay_rejects_covered_or_unrelated_taps(point):
    raw = GlyphLinkReplay()
    raw.state = "share"
    with pytest.raises(AssertionError, match="missed the verified sheet controls"):
        raw.long_click(*point, 0.1)
    assert raw.state == "share" and not raw.controls


def test_share_glyph_tap_opens_sheet_and_copies_without_wrapper_padding():
    raw, browser = glyph_browser()
    source = browser.observe()
    link = browser.copy_link(source)
    returned = browser.observe(previous=source)
    assert returned.identity == source.identity
    assert returned.source_key == source.source_key == link.source_key
    assert (
        returned.post_url
        == link.url
        == "https://x.com/fixture_author/status/1000000000000000001"
    )
    assert returned.native_post_id == link.post_id
    assert [action[0] for action in raw.actions] == ["source", "share"]
    assert 1003 <= raw.actions[0][1] < 1047 and 1928 <= raw.actions[0][2] < 1972


def test_share_target_excludes_the_padding_point_that_did_not_open_a_sheet():
    screen = read_screen(document("share-glyph-source"), SIZE)
    source = next(post for post in screen.posts if post.author == "@fixture_author")
    target, region = _control(source.actions, "Share")
    assert target.visibility.bounds == (959, 1784, 1080, 1902)
    assert region == (1003, 1828, 1047, 1872)
    assert not (region[0] <= 977 < region[2] and region[1] <= 1832 < region[3])


def test_share_glyph_fixture_integrity():
    manifest = fixture_manifest(LINK_FIXTURES / "share-glyph-manifest.json")
    assert manifest["kind"] == "synthetic_native_layout"
    for item in manifest["fixtures"]:
        assert item["kind"] == "synthetic_native_layout"


def test_edge_clipped_share_uses_the_proven_strip_within_the_glyph_height():
    source = read_screen(document("soak-source"), SIZE).observable_posts[0]
    target, region = _control(source.actions, "Share")
    assert target.visibility.bounds == (959, 2059, 1080, 2177)
    assert target.glyph_visibility.bounds == (1036, 2103, 1047, 2147)
    assert region == (1036, 2103, 1080, 2147)
    assert region[0] <= 1055 < region[2] and region[1] <= 2120 < region[3]
    assert all(
        region[2] <= c[0] or region[0] >= c[2] or region[3] <= c[1] or region[1] >= c[3]
        for c in target.visibility.overlaps
    )


@pytest.mark.parametrize("scale", [1, 2, 3])
def test_share_glyph_geometry_scales_with_native_coordinates(scale):
    for name in ("share-glyph-source", "soak-source"):
        screen = read_screen(document(name), SIZE)
        source = (
            next(p for p in screen.observable_posts if p.author == "@fixture_author")
            if name == "share-glyph-source"
            else screen.observable_posts[0]
        )
        target = next(t for t in source.actions if t.label == "Share")
        _, original = _control((target,), "Share")

        def scaled(visibility):
            return replace(
                visibility,
                bounds=tuple(v * scale for v in visibility.bounds),
                visible_bounds=tuple(v * scale for v in visibility.visible_bounds),
                overlaps=tuple(
                    tuple(v * scale for v in r) for r in visibility.overlaps
                ),
            )

        target = replace(
            target,
            visibility=scaled(target.visibility),
            glyph_visibility=scaled(target.glyph_visibility),
        )
        expected = tuple(v * scale for v in original)
        if name == "soak-source" and scale > 1:
            expected = target.glyph_visibility.bounds
        assert _control((target,), "Share")[1] == expected


@pytest.mark.parametrize(
    "problem",
    [
        "ambiguous",
        "edge",
        "neighbor",
        "height",
        "missing_cover",
        "parent_clip",
        "detached",
        "unowned",
        "inaccessible",
        "invisible",
    ],
)
def test_unknown_share_clipping_cannot_use_wrapper_padding(problem):
    source = read_screen(document("soak-source"), SIZE).observable_posts[0]
    target = next(t for t in source.actions if t.label == "Share")
    control, glyph = target.visibility, target.glyph_visibility
    cover = control.overlaps[0]
    if problem == "ambiguous":
        control = replace(control, overlaps=(cover, (1050, 2059, 1080, 2070)))
    elif problem == "edge":
        control = replace(
            control, overlaps=((cover[0], cover[1], cover[2] - 1, cover[3]),)
        )
    elif problem == "neighbor":
        control = replace(control, overlaps=((1000, cover[1], cover[2], cover[3]),))
    elif problem == "height":
        control = replace(control, overlaps=((cover[0], 2120, cover[2], cover[3]),))
    elif problem == "missing_cover":
        control = replace(control, overlaps=())
    elif problem == "parent_clip":
        control = replace(control, visible_bounds=(959, 2059, 1079, 2177))
    elif problem == "detached":
        control = replace(
            control,
            bounds=(959, 2059, 1120, 2177),
            visible_bounds=(959, 2059, 1120, 2177),
        )
    elif problem == "unowned":
        glyph = replace(glyph, bounds=(950, 2103, 1047, 2147))
    elif problem == "inaccessible":
        glyph = replace(glyph, accessible=False)
    else:
        glyph = replace(glyph, visible_bounds=None)
    with pytest.raises(InteractionError, match="(?:glyph|target)"):
        _control(
            (replace(target, visibility=control, glyph_visibility=glyph),), "Share"
        )


@pytest.mark.parametrize(
    "problem", ["hidden", "disabled", "missing", "duplicate", "unowned", "tiny"]
)
def test_invalid_native_share_glyph_rejects_before_injection(problem):
    raw, browser = glyph_browser()
    source = browser.observe()
    root = etree.fromstring(raw.frames["source"].encode())
    icon = root.xpath('.//node[@content-desc="Share"]')[-1]
    if problem == "hidden":
        icon.set("visible-to-user", "false")
    elif problem == "disabled":
        icon.set("enabled", "false")
    elif problem == "missing":
        icon.set("content-desc", "")
    elif problem == "duplicate":
        icon.getparent().append(deepcopy(icon))
    elif problem == "unowned":
        icon.set("bounds", "[950,1928][980,1972]")
    else:
        icon.set("bounds", "[1003,1928][1014,1939]")
    raw.frames["source"] = etree.tostring(root, encoding="unicode")
    with pytest.raises(InteractionError):
        browser.copy_link(source)
    assert raw.actions == []
    assert not browser.browsing_valid


def test_share_glyph_geometry_is_part_of_source_return_verification():
    raw, browser = glyph_browser()
    root = etree.fromstring(raw.frames["receipt"].encode())
    root.xpath('.//node[@content-desc="Share"]')[-1].set(
        "bounds", "[1004,1928][1048,1972]"
    )
    raw.frames["receipt"] = etree.tostring(root, encoding="unicode")
    with pytest.raises(InteractionError, match="source changed"):
        browser.copy_link(browser.observe())
    assert raw.controls == ["Share", "Copy link"]
    assert not browser.browsing_valid


@pytest.mark.parametrize("stage", ["share", "copy"])
@pytest.mark.parametrize("problem", ["transport", "cancel", "deadline"])
def test_glyph_tap_failure_is_never_repeated(stage, problem):
    raw, browser = glyph_browser()
    error = {
        "transport": OSError("response lost"),
        "cancel": InteractionCancelled("stop"),
        "deadline": SessionExpired("expired"),
    }[problem]
    setattr(raw, stage + "_error", error)
    with pytest.raises(
        type(error) if problem != "transport" else InteractionError
    ) as caught:
        browser.copy_link(browser.observe())
    if problem == "transport":
        assert caught.value.result.status == Status.UNCERTAIN
    else:
        assert caught.value is error
    assert raw.controls.count("Share") == 1
    assert raw.controls.count("Copy link") == (stage == "copy")
    assert not browser.browsing_valid


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


def dismissal_document(name):
    return document("dismissal-" + name)


def dismissal_started():
    replay = CoveredLinkReplay()
    replay.xml = replay.results = dismissal_document("source")
    replay.sheet = dismissal_document("share")
    replay.copied = dismissal_document("receipt")
    replay.returns = [replay.copied] * 5 + [
        dismissal_document("empty"),
        dismissal_document("return"),
    ]
    browser = XBrowser(replay.phone, {"for_you"})
    app = browser.browser
    app.timeline = "for_you"
    app.verified_account = app._expected = "@fixture_owner"
    screen = read_screen(replay.xml, SIZE)
    app._select(screen, next(i for i, p in enumerate(screen.posts) if p.observable))
    browser.workflow = "for_you"
    browser._username, browser._valid = "fixture_owner", True
    return replay, browser


def dismissal_copied():
    replay, browser = dismissal_started()
    source = browser.observe()
    link = browser.copy_link(source)
    assert browser.observe(previous=source).post_url == link.url
    current = browser.observe(previous=source)
    assert not browser.act("skip", current).advanced
    assert replay.receipt_reads == 5
    return replay, browser, source, link


@pytest.mark.parametrize("transients", [1, 7])
def test_captured_dismissal_preserves_occurrence_and_link(transients):
    replay, browser, source, link = dismissal_copied()
    replay.returns = [dismissal_document("empty")] * transients + [
        dismissal_document("return")
    ]
    events = list(replay.events)
    after = browser.observe(previous=source)
    assert after.identity == source.identity
    assert after.source_key == source.source_key == link.source_key
    assert after.post_url == link.url
    assert browser.browser._screen.clipboard_text is None
    assert replay.receipt_reads == 5 + transients + 1
    assert replay.now == pytest.approx(transients * 0.3)
    assert replay.events == events
    assert replay.events.count(("link", "copy")) == 1
    assert browser.browsing_valid


@pytest.mark.parametrize("action", ["observe", "advance", "like", "copy_link"])
def test_persistent_dismissal_stops_before_any_action(action):
    replay, browser, source, _ = dismissal_copied()
    replay.returns = [dismissal_document("empty")]
    events = list(replay.events)
    with pytest.raises(XError, match="clipboard dismissal within the read limit"):
        if action == "like":
            browser.act(action, source)
        elif action == "copy_link":
            browser.copy_link(source)
        else:
            getattr(browser, action)()
    assert replay.receipt_reads == 13
    assert replay.now == pytest.approx(2.1)
    assert replay.events == events
    assert not browser.browsing_valid


def changed(xml, problem):
    root = etree.fromstring(xml.encode())
    author = root.xpath('.//*[@text="@BlaireWhite"]')[0]
    header = author.getparent()
    post = header.getparent()
    if problem == "author":
        author.set("text", "@Other")
    elif problem == "body":
        post.xpath('.//*[@bounds="[176,1499][1047,1644]"]')[0].set("text", "Changed.")
    elif problem == "body_bounds":
        post.xpath('.//*[@bounds="[176,1499][1047,1644]"]')[0].set(
            "bounds", "[176,1500][1047,1644]"
        )
    elif problem in {"body_left", "body_bottom"}:
        post.xpath('.//*[@bounds="[176,1499][1047,1644]"]')[0].set(
            "bounds",
            "[177,1499][1047,1644]"
            if problem == "body_left"
            else "[176,1499][1047,1645]",
        )
    elif problem == "header_bounds":
        header.set("bounds", "[176,1444][876,1492]")
    elif problem == "header_right":
        header.set("bounds", "[176,1443][877,1492]")
    elif problem == "post_bounds":
        post.set("bounds", "[0,1411][1080,1762]")
    elif problem == "duplicate":
        post.addnext(deepcopy(post))
    elif problem == "missing":
        post.getparent().remove(post)
    elif problem == "context":
        return document("top-source")
    elif problem == "account":
        from unit.social_media.x.services.search_replay import document as search

        return search("account-drawer").replace("@fixture_owner", "@Other")
    else:
        raise AssertionError(problem)
    return etree.tostring(root, encoding="unicode")


@pytest.mark.parametrize("stage", ["empty", "return"])
@pytest.mark.parametrize(
    "problem",
    [
        "author",
        "body",
        "body_bounds",
        "body_left",
        "body_bottom",
        "header_bounds",
        "header_right",
        "post_bounds",
        "duplicate",
        "missing",
        "context",
        "account",
    ],
)
def test_changed_source_or_context_is_not_waited_through(stage, problem):
    replay, browser, source, _ = dismissal_copied()
    replay.returns = [
        dismissal_document("empty"),
        changed(dismissal_document(stage), problem),
        dismissal_document("return"),
    ]
    events = list(replay.events)
    with pytest.raises(InteractionError):
        browser.observe(previous=source)
    assert replay.receipt_reads == 7
    assert replay.events == events
    assert not browser.browsing_valid


@pytest.mark.parametrize(
    "problem", ["no_prior_receipt", "bounds", "interactive", "package", "multiple"]
)
def test_unknown_window_is_not_treated_as_dismissal(problem):
    replay, browser, source, _ = dismissal_copied()
    root = etree.fromstring(dismissal_document("empty").encode())
    window = root[0]
    if problem == "no_prior_receipt":
        browser.browser._screen = read_screen(dismissal_document("source"), SIZE)
    elif problem == "bounds":
        window.set("bounds", "[27,1937][608,2257]")
    elif problem == "interactive":
        window.set("clickable", "true")
    elif problem == "package":
        window.set("package", "other.app")
    else:
        root.insert(0, deepcopy(window))
    replay.returns = [
        etree.tostring(root, encoding="unicode"),
        dismissal_document("return"),
    ]
    events = list(replay.events)
    with pytest.raises(InteractionError) as caught:
        browser.observe(previous=source)
    assert "Home controls changed" not in str(caught.value)
    assert replay.receipt_reads == 6
    assert replay.now == 0
    assert replay.events == events


def test_empty_window_cannot_provide_a_fresh_link():
    replay, browser = dismissal_started()
    replay.returns = [dismissal_document("empty"), dismissal_document("return")]
    with pytest.raises(InteractionError, match="fresh native Copy link receipt"):
        browser.copy_link(browser.observe())
    assert browser._post_link is None
    assert replay.events.count(("link", "copy")) == 1
    assert not browser.browsing_valid


@pytest.mark.parametrize("change", ["receipt", "foreground"])
def test_changed_receipt_or_foreground_during_reread_invalidates_browsing(change):
    replay, browser, source, _ = dismissal_copied()
    replay.returns = [
        dismissal_document("empty"),
        dismissal_document("receipt").replace(
            "2123555038706663930", "2123555038706663931"
        ),
        dismissal_document("return"),
    ]
    if change == "foreground":
        original_read = replay.read

        def read(what):
            if replay.now and what == "app":
                return {"package": "other.app"}
            return original_read(what)

        replay.read = read
    events = list(replay.events)
    with pytest.raises(InteractionError, match="receipt changed|foreground"):
        browser.observe(previous=source)
    assert replay.events == events
    assert not browser.browsing_valid


@pytest.mark.parametrize("expired", [False, True])
def test_cancellation_or_deadline_interrupts_dismissal_wait(expired):
    replay, browser, source, _ = dismissal_copied()
    if expired:
        replay.phone.configure(deadline=0.1)
    else:
        replay.phone.configure(cancelled=lambda: replay.now >= 0.1)
    events = list(replay.events)
    with pytest.raises(SessionExpired if expired else InteractionCancelled):
        browser.observe(previous=source)
    assert replay.now == pytest.approx(0.1)
    assert replay.receipt_reads == 6
    assert replay.events == events
    assert not browser.browsing_valid


@pytest.mark.parametrize(
    "error",
    [OSError("read lost"), InteractionCancelled("stop"), SessionExpired("expired")],
)
def test_dismissal_reread_error_survives_failed_copy_cleanup(error):
    replay, browser = dismissal_started()
    replay.returns = [
        replay.copied,
        dismissal_document("empty"),
        dismissal_document("return"),
    ]
    replay.cleanup_error = OSError("cleanup read lost")
    original_read = replay.read

    def read(what):
        if (
            what == "hierarchy"
            and replay.receipt_reads == 2
            and not replay.phone._cleaning
        ):
            raise error
        return original_read(what)

    replay.read = read
    expected = InteractionError if isinstance(error, OSError) else type(error)
    with pytest.raises(expected) as caught:
        browser.copy_link(browser.observe())
    if isinstance(error, OSError):
        assert caught.value.result.status == Status.UNCERTAIN
        assert "read lost" in str(caught.value)
    else:
        assert caught.value is error
    assert isinstance(caught.value.__cause__, InteractionError)
    assert "cleanup read lost" in str(caught.value.__cause__)
    assert replay.events.count(("link", "copy")) == 1
    assert not browser.browsing_valid


@pytest.mark.parametrize("problem", [None, "query", "tab"])
def test_search_dismissal_still_requires_query_and_tab(problem):
    replay, browser = started(browser=True)
    source = browser.observe()
    link = browser.copy_link(source)
    root = etree.fromstring(replay.copied.encode())
    window = next(
        w
        for w in root
        if w.get("package") == "com.android.systemui"
        and w.get("bounds") != "[0,0][1080,136]"
    )
    for child in list(window):
        window.remove(child)
    if problem == "query":
        xml = etree.tostring(root, encoding="unicode").replace(
            "from:NASA", "from:Other"
        )
    elif problem == "tab":
        for node in root.xpath('.//*[@content-desc="Top" or @content-desc="Latest"]'):
            node.getparent().set(
                "selected", "true" if node.get("content-desc") == "Latest" else "false"
            )
        xml = etree.tostring(root, encoding="unicode")
    else:
        xml = etree.tostring(root, encoding="unicode")
    replay.after = xml
    original_sleep = replay.sleep

    def sleep(seconds):
        original_sleep(seconds)
        replay.after = document("top-source")

    replay.phone._sleep = sleep
    if problem:
        with pytest.raises(InteractionError):
            browser.observe(previous=source)
        assert replay.now == 0
    else:
        after = browser.observe(previous=source)
        assert after.post_url == link.url
        assert after.identity == source.identity
        assert browser.browser._screen.clipboard_bounds is None
        assert replay.now == pytest.approx(0.3)


@pytest.mark.parametrize("timeline", ["for_you", "search"])
def test_unsupported_reason_precedes_header_transition_diagnostics(timeline):
    _, browser, _, _ = dismissal_copied()
    app = browser.browser
    app.timeline = timeline
    before = replace(
        app._screen,
        kind="search_results" if timeline == "search" else "home",
        collapsed=True,
    )
    invalid = read_screen("<invalid/>", SIZE)
    with pytest.raises(XError, match="Expected a hierarchy"):
        app._check_timeline(invalid, before)
    with pytest.raises(XError, match="controls changed outside adapter scrolling"):
        app._check_timeline(replace(before, collapsed=False), before)


def test_advancement_resumes_after_dismissal_using_existing_search_scroll_evidence():
    from unit.social_media.x.services.search_replay import SearchReplay, shifted_results
    from unit.social_media.x.services.search_replay import document as search

    replay = SearchReplay()
    replay.latest = shifted_results(350)
    replay.scrolls = [search("search-latest")]
    app = XBrowser(replay.phone, {"search"}).browser
    app.start("fixture_owner", "search", query="astronomy", result_tab="latest")
    assert app.advance().author == "@SzandraDMLLP"
    source = app.observe()
    root = etree.fromstring(replay.xml.encode())
    receipt = etree.fromstring(dismissal_document("receipt").encode())[0]
    root.insert(0, receipt)
    replay.xml = etree.tostring(root, encoding="unicode")
    assert app.observe().content_key == source.content_key
    root.replace(receipt, etree.fromstring(dismissal_document("empty").encode())[0])
    replay.xml = etree.tostring(root, encoding="unicode")
    original_sleep = replay.phone._sleep

    def sleep(seconds):
        original_sleep(seconds)
        replay.xml = replay.latest
        replay.phone._sleep = original_sleep

    replay.phone._sleep = sleep
    assert app.advance().author == "@Astronomy1world"
    assert app.observe().author == "@Astronomy1world"
    gestures = [e for e in replay.events if e[0] == "gesture"]
    assert len(gestures) == 1
    assert gestures[0][1:3] == ("scroll", "up")
