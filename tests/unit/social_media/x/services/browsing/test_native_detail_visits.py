"""Native main-detail reads retain attribution and the source browsing occurrence."""

import base64
from types import SimpleNamespace

import pytest
from lxml import etree
from unit.social_media.x.services.detail_inputs import document
from unit.social_media.x.services.detail_replay import MainReplay
from unit.social_media.x.services.startup_transport import RawStartup

from taktik.core.shared.phone_interaction import InteractionError, Phone, Status
from taktik.core.shared.phone_interaction._device import TaktikDevice
from taktik.core.social_media.x.services.browsing.browser import XBrowser
from taktik.core.social_media.x.services.browsing.navigation import (
    X,
    XError,
    scroll_region,
)
from taktik.core.social_media.x.ui.screen import read_screen


def started():
    replay = MainReplay()
    app = X(replay.phone)
    app.start(
        "fixture_owner",
        "search",
        query="from:NASA -filter:replies",
        result_tab="latest",
    )
    return replay, app


def test_thread_inspection_verifies_main_content_and_returns_to_source_occurrence():
    replay, app = started()
    source = app.observe()
    report = app.inspect_thread(max_scrolls=0)
    assert report.main_verified and report.detail.main_post.body == source.body
    assert report.source_key == source.content_key
    assert app.observe().content_key == source.content_key
    assert report.detail.main_post not in report.posts and not report.complete
    assert replay.native_reads >= 2


@pytest.mark.parametrize("field", ["author", "body", "media", "context"])
def test_native_detail_mismatch_invalidates_without_retrying_the_visit(field):
    replay, app = started()
    root = etree.fromstring(replay.native.encode())
    if field == "author":
        root.xpath('.//*[@text="@NASA"]')[0].set("text", "@another")
    elif field == "body":
        root.xpath('.//*[@text and starts-with(@text,"Join us in getting")]')[0].set(
            "text", "Another post's body."
        )
    elif field == "media":
        root.xpath(
            './/*[@class="android.widget.ImageView" and starts-with(@content-desc,"Image:")]'
        )[0].set("content-desc", "Image: A different photograph.")
    else:
        root.xpath('.//*[@resource-id="PostDetail"]')[0].set(
            "resource-id", "UnknownScreen"
        )
    replay.native = etree.tostring(root, encoding="unicode")
    with pytest.raises(XError):
        app.inspect_thread(max_scrolls=0)
    assert app.verified_account is None
    assert [e for e in replay.events if e[0] == "visit"] == [("visit", "Open post")]
    assert ("tap", "inspection Back") not in replay.events


def test_uncertain_native_read_preserves_uncertainty_and_requires_explicit_recovery():
    replay, app = started()
    replay.native_error = OSError("native read response lost")
    with pytest.raises(InteractionError) as error:
        app.inspect_thread(max_scrolls=0)
    assert error.value.result.status == Status.UNCERTAIN
    assert app.verified_account is None and replay.native_reads == 1


def test_native_expanded_caption_has_an_explicit_source_reference():
    replay = MainReplay()
    root = etree.fromstring(replay.results.encode())
    body = root.xpath('.//*[@text and starts-with(@text,"Join us in getting")]')[0]
    body.set("text", body.get("text")[:72] + "\xa0Show more")
    replay.results = replay.latest = replay.restored = etree.tostring(
        root, encoding="unicode"
    )
    app = X(replay.phone)
    app.start(
        "fixture_owner",
        "search",
        query="from:NASA -filter:replies",
        result_tab="latest",
    )
    source = app.observe()
    report = app.inspect_thread(max_scrolls=0)
    assert report.main_verified and report.detail.main_post.body_complete
    assert report.detail.main_post.body.startswith(
        source.body.removesuffix("\xa0Show more")
    )
    assert report.source_key == source.content_key
    assert app.observe().body == source.body


def test_native_detail_return_uses_enough_travel_to_reveal_the_toolbar():
    replay, app = started()
    gesture = replay.gesture

    def scroll(intent, direction, region, distance, exclude):
        if direction == "down":
            assert distance >= 235
        gesture(intent, direction, region, distance, exclude)
        replay.native = document(
            "image-scrolled" if direction == "up" else "image-main"
        )
        replay.xml = document(
            "image-scrolled-ordinary" if direction == "up" else "image-ordinary"
        )

    replay.gesture = scroll
    source = app.observe()
    report = app.inspect_thread(max_scrolls=1)
    assert report.main_verified and report.scrolls == 1
    assert [e[2] for e in replay.events if e[0] == "gesture"] == ["up", "down"]
    assert app.observe().content_key == source.content_key


def test_captured_toolbar_restoration_has_a_long_control_free_path():
    before = read_screen(document("toolbar-collapsed"), (1080, 2340))
    after = read_screen(document("toolbar-restored"), (1080, 2340))
    region, distance, exclusions = scroll_region(before, restore=True)
    assert before.collapsed and not after.collapsed
    assert (
        after.detail.timestamp.visibility.bounds[1]
        - before.detail.timestamp.visibility.bounds[1]
        == 312
    )
    assert distance >= 235 and distance <= (region[3] - region[1]) * 0.6
    assert all(
        not (
            r[0] < region[2]
            and r[2] > region[0]
            and r[1] < region[3]
            and r[3] > region[1]
        )
        for r in exclusions
    )


@pytest.mark.parametrize("layout", ["video", "expanded", "quote"])
def test_captured_detail_layouts_verify_source_and_preserve_the_occurrence(layout):
    replay = MainReplay()
    replay.results = replay.latest = document(f"{layout}-source")
    replay.restored = document(f"{layout}-return")
    replay.detail = document(f"{layout}-ordinary")
    replay.native = document(f"{layout}-main")
    query = read_screen(replay.results, (1080, 2340)).query
    app = X(replay.phone)
    app.start("fixture_owner", "search", query=query, result_tab="latest")
    source = app.observe()
    report = app.inspect_thread(max_scrolls=0)
    assert report.main_verified and report.detail.main_post.observable
    assert report.source_key == source.content_key == app.observe().content_key
    if layout == "expanded":
        assert len(source.body) == 276 and len(report.detail.main_post.body) == 551
        assert not source.body_complete and report.detail.main_post.body_complete
    elif layout == "quote":
        assert report.detail.main_post.quoted_post.author == "@OpenAI"
        assert report.detail.main_post.media == ()
        assert report.detail.main_post.quoted_post.media[0].kind == "video"


def test_long_body_does_not_claim_visibility_or_invent_its_offscreen_quote():
    from taktik.core.social_media.x.services.browsing.inspection import (
        _verify_main_source,
    )

    source = read_screen(document("long-source"), (1080, 2340)).observable_posts[0]
    main = read_screen(document("long-main"), (1080, 2340)).detail.main_post
    assert len(main.body) == 1857 and not main.body_complete and not main.observable
    assert source.quoted_post is not None and main.quoted_post is None
    assert _verify_main_source(source, main) is False


def test_retained_detail_position_is_restored_before_reading_the_main_post():
    replay, app = started()

    def native_state(name):
        root = etree.fromstring(document(name).encode())
        root.set("taktik-reader", "screen-reader")
        return etree.tostring(root, encoding="unicode")

    replay.detail = document("image-scrolled-ordinary")
    replay.native = native_state("image-scrolled")
    gesture = replay.gesture

    def restore(intent, direction, region, distance, exclude):
        assert direction == "down"
        gesture(intent, direction, region, distance, exclude)
        replay.xml = document("image-ordinary")
        replay.native = native_state("image-main")

    replay.gesture = restore
    report = app.inspect_thread(max_scrolls=0)
    assert report.main_verified
    assert len([e for e in replay.events if e[0] == "gesture"]) == 1


def test_captured_reverse_movement_restores_an_observable_quoted_main_header():
    from taktik.core.social_media.x.services.browsing.navigation import _scroll_motion

    before = read_screen(document("quote-header-scrolled"), (1080, 2340))
    after = read_screen(document("quote-header-restored"), (1080, 2340))
    assert before.detail.main_header_visible is False
    assert after.detail.main_header_visible is True
    assert after.detail.main_post.observable
    assert _scroll_motion(after, before) < -200


class BadgeReplay(RawStartup):
    """Synthetic thread visit through the real native-reader transport protocol."""

    def __init__(self):
        super().__init__()
        self.home = document("badge-source")
        self.detail = document("badge-ordinary")
        self.native = document("badge-native")
        self.returned = self.home
        self.native_reads = 0
        self.after_native = lambda: None
        self.after_scroll = lambda: None
        self.tap_error = self.native_error = None
        self._process = object()
        self.config = {"waitForIdleTimeout": 321, "waitForSelectorTimeout": 123}
        self.jsonrpc = SimpleNamespace(
            getConfigurator=lambda: self.config.copy(),
            setConfigurator=lambda config: config,
        )
        self.adb_device = SimpleNamespace(sync=SimpleNamespace(push=self.push))

    def dump_hierarchy(self):
        if self.stage == "detail":
            return self.detail
        return super().dump_hierarchy()

    def push(self, local, remote, check):
        assert local.endswith("hierarchy-reader.dex") and check is True
        self.remote = remote

    def stop_uiautomator(self, *, wait):
        assert wait is False
        self._process = None

    def start_uiautomator(self):
        self._process = object()

    def shell(self, command, *, timeout):
        if command == ["dumpsys", "accessibility"]:
            return SimpleNamespace(exit_code=0, output="")
        if isinstance(command, str):
            assert command.endswith("app_process / taktik.phone.HierarchyReader")
            self.native_reads += 1
            if self.native_error:
                raise self.native_error
            payload = base64.b64encode(self.native.encode()).decode()
            self.after_native()
            return SimpleNamespace(exit_code=0, output="TAKTIK_HIERARCHY_V1:" + payload)
        assert command == ["rm", "-f", self.remote]
        return SimpleNamespace(exit_code=0, output="")

    def long_click(self, x, y, duration):
        if self.stage == "drawer":
            return super().long_click(x, y, duration)
        xml = self.detail if self.stage == "detail" else self.home
        screen = read_screen(xml, (1080, 2340))
        targets = (
            screen.controls
            if self.stage == "detail"
            else tuple(t for p in screen.posts for t in p.targets)
        )
        label = "Back" if self.stage == "detail" else "Open post"
        matches = [
            t
            for t in targets
            if t.label == label
            and t.visibility.visible_bounds is not None
            and t.visibility.visible_bounds[0] <= x < t.visibility.visible_bounds[2]
            and t.visibility.visible_bounds[1] <= y < t.visibility.visible_bounds[3]
            and not any(
                a <= x < c and b <= y < d for a, b, c, d in t.visibility.overlaps
            )
        ]
        if matches:
            assert len(matches) == 1
            self.actions.append(label)
            if label == "Back":
                self.stage, self.home = "home", self.returned
            else:
                self.stage = "detail"
            if self.tap_error:
                raise self.tap_error
        else:
            super().long_click(x, y, duration)

    def swipe_points(self, points, duration):
        self.actions.append("scroll")
        self.after_scroll()


@pytest.fixture
def badge_visit():
    raw = BadgeReplay()
    phone = Phone(
        TaktikDevice(raw, "fixture"), seed=0, clock=lambda: raw.now, sleep=raw.sleep
    )
    browser = XBrowser(phone, {"for_you"})
    try:
        browser.start("fixture_owner", "for_you")
        raw.actions.clear()
        yield raw, browser
    finally:
        phone.close(home=False).require()


def test_secondary_author_badge_visits_thread_and_returns_without_restoring_header(
    badge_visit,
):
    raw, browser = badge_visit
    source = browser.observe()
    report = browser.inspect_thread(source, max_scrolls=0)
    assert report.main_verified and report.detail.main_post.observable
    assert report.detail.main_post.labels == ("Verified Business", "Fixture Museum")
    assert report.detail.main_post.author == "@fixture_author"
    assert report.detail.main_post.body == source.caption
    assert browser.observe().identity == source.identity
    assert browser.browsing_valid and raw.native_reads >= 2
    assert raw.actions == ["Open post", "Back"]


def changed_badge(change):
    from copy import deepcopy

    root = etree.fromstring(document("badge-native").encode())
    avatar = root.xpath('.//*[@resource-id="timeline_post_avatar"]')[0]
    column = avatar.getparent()[1]
    name, verification, affiliation, handle = column
    if change == "missing_verification":
        column.remove(verification)
    elif change == "missing_name":
        for node in (name, verification, affiliation):
            column.remove(node)
    elif change == "duplicate_affiliation":
        affiliation.addnext(deepcopy(affiliation))
    elif change == "duplicate_avatar":
        avatar.addnext(deepcopy(avatar))
    elif change == "nested":
        affiliation.append(deepcopy(verification))
    elif change == "unrelated_sibling":
        extra = deepcopy(affiliation)
        extra.set("content-desc", "Unknown metadata")
        column.append(extra)
    elif change == "overlap":
        root.xpath('.//*[@content-desc="Post options"]')[0].set(
            "bounds", affiliation.get("bounds")
        )
    elif change == "offscreen":
        from taktik.core.shared.ui.geometry import bounds

        for node in avatar.getparent().iter():
            a, b, c, d = bounds(node)
            node.set("bounds", f"[{a},{b - 312}][{c},{d - 312}]")
    else:
        node, attr, value = change
        {
            "name": name,
            "verification": verification,
            "affiliation": affiliation,
            "handle": handle,
            "avatar": avatar,
            "column": column,
        }[node].set(attr, value)
    return etree.tostring(root, encoding="unicode")


@pytest.mark.parametrize(
    "change",
    [
        "missing_verification",
        "missing_name",
        "duplicate_affiliation",
        "duplicate_avatar",
        "nested",
        "unrelated_sibling",
        ("verification", "content-desc", "Unknown"),
        ("verification", "content-desc", ""),
        ("verification", "clickable", "true"),
        ("affiliation", "content-desc", "Verified"),
        ("affiliation", "content-desc", " "),
        ("affiliation", "text", "Unknown metadata"),
        ("affiliation", "class", "android.widget.TextView"),
        ("affiliation", "resource-id", "unknown"),
        ("affiliation", "clickable", "true"),
        ("affiliation", "long-clickable", "true"),
        ("affiliation", "focusable", "true"),
        ("affiliation", "scrollable", "true"),
        ("affiliation", "enabled", "false"),
        ("affiliation", "visible-to-user", "false"),
        ("affiliation", "package", "another.app"),
        ("affiliation", "bounds", "[590,367][625,402]"),
        ("affiliation", "bounds", "[597,410][632,445]"),
        ("affiliation", "bounds", "[597,367][650,402]"),
        ("affiliation", "bounds", "[597,364][639,406]"),
        ("affiliation", "bounds", "[797,367][832,402]"),
        ("column", "clickable", "true"),
        ("column", "content-desc", "Unknown metadata"),
        ("handle", "text", "not a handle"),
        ("avatar", "content-desc", "Another Author"),
    ],
)
def test_unsupported_identity_fails_without_a_header_restore(badge_visit, change):
    raw, browser = badge_visit
    raw.native = changed_badge(change)
    parsed = read_screen(raw.native, (1080, 2340))
    assert parsed.kind == "unsupported" and parsed.reason
    with pytest.raises(XError, match=parsed.reason.replace(".", r"\.")):
        browser.inspect_thread(browser.observe(), max_scrolls=0)
    assert raw.actions == ["Open post"]
    assert not browser.browsing_valid


@pytest.mark.parametrize("change", ["overlap", "offscreen"])
def test_geometrically_hidden_badge_header_requires_verified_motion(
    badge_visit, change
):
    raw, browser = badge_visit
    raw.native = changed_badge(change)
    screen = read_screen(raw.native, (1080, 2340))
    assert screen.detail.main_header_visible is False
    assert not screen.detail.main_post.observable
    with pytest.raises(XError, match="Cannot verify progress"):
        browser.inspect_thread(browser.observe(), max_scrolls=0)
    assert raw.actions == ["Open post", "scroll"]
    assert not browser.browsing_valid


def test_hidden_badge_header_can_be_restored_before_verified_return(badge_visit):
    raw, browser = badge_visit
    raw.native = changed_badge("offscreen")
    raw.after_scroll = lambda: setattr(raw, "native", document("badge-native"))
    source = browser.observe()
    report = browser.inspect_thread(source, max_scrolls=0)
    assert report.main_verified
    assert raw.actions == ["Open post", "scroll", "Back"]
    assert browser.observe().identity == source.identity


@pytest.mark.parametrize("change", ["author", "name", "body", "context", "return"])
def test_badge_acceptance_keeps_source_context_and_return_checks(badge_visit, change):
    raw, browser = badge_visit
    if change == "author":
        raw.native = raw.native.replace("@fixture_author", "@another_author")
    elif change == "name":
        raw.native = raw.native.replace("Fixture Author", "Another Author")
    elif change == "body":
        raw.native = raw.native.replace("The fictional museum", "A different museum")
    elif change == "context":
        raw.native = raw.native.replace("9:00 AM", "10:00 AM")
    else:
        raw.returned = raw.returned.replace("@fixture_author", "@another_author")
    with pytest.raises(XError):
        browser.inspect_thread(browser.observe(), max_scrolls=0)
    assert raw.actions == ["Open post"] + (["Back"] if change == "return" else [])
    assert not browser.browsing_valid


@pytest.mark.parametrize("operation", ["read", "tap", "scroll"])
def test_badge_visit_does_not_retry_uncertain_operations(badge_visit, operation):
    raw, browser = badge_visit
    error = OSError("Synthetic acknowledgement lost")
    if operation == "read":
        raw.native_error = error
    elif operation == "tap":
        raw.tap_error = error
    else:
        raw.native = changed_badge("offscreen")

        def uncertain():
            raise error

        raw.after_scroll = uncertain
    with pytest.raises(InteractionError) as failure:
        browser.inspect_thread(browser.observe(), max_scrolls=0)
    assert failure.value.result.status == Status.UNCERTAIN
    assert raw.actions == ["Open post"] + (["scroll"] if operation == "scroll" else [])
    assert not browser.browsing_valid


@pytest.mark.parametrize("stop", ["cancel", "deadline"])
def test_badge_visit_preserves_interruption_and_native_cleanup(badge_visit, stop):
    from taktik.core.shared.phone_interaction import InteractionCancelled

    raw, browser = badge_visit

    def interrupt():
        if stop == "cancel":
            raise InteractionCancelled("Synthetic cancellation")
        browser.phone.configure(deadline=raw.now)

    raw.after_native = interrupt
    with pytest.raises(InteractionCancelled):
        browser.inspect_thread(browser.observe(), max_scrolls=0)
    assert raw.actions == ["Open post"] and raw.native_reads == 1
    assert raw._process is not None and not browser.browsing_valid


def test_affiliation_change_between_native_reads_invalidates_visit(badge_visit):
    raw, browser = badge_visit
    raw.after_native = lambda: setattr(
        raw, "native", raw.native.replace("Fixture Museum", "Another Organization")
    )
    with pytest.raises(XError, match="native main post changed"):
        browser.inspect_thread(browser.observe(), max_scrolls=0)
    assert raw.actions == ["Open post"] and not browser.browsing_valid
