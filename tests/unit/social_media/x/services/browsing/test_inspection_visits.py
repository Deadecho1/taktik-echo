"""Phone replays cover successful round trips, stale sources and uncertainty."""

import io
from dataclasses import replace

import pytest
from lxml import etree
from PIL import Image
from taktik.core.shared.behavior.tap import free_tap_zone
from taktik.core.shared.phone_interaction import (
    InteractionCancelled,
    InteractionError,
    Status,
)
from taktik.core.shared.ui.geometry import bounds
from taktik.core.social_media.x.services.browsing.browser import XBrowser
from taktik.core.social_media.x.services.browsing.navigation import X, XError
from taktik.core.social_media.x.ui.screen import PACKAGE, read_screen
from unit.social_media.x.services.browsing.test_search import SearchReplay
from unit.social_media.x.ui.test_inspection_screen import SIZE, document


class InspectionReplay(SearchReplay):
    def __init__(self, image=False):
        super().__init__()
        self.results = document("image-source" if image else "text-source")
        self.latest = self.results
        self.restored = document("image-return" if image else "text-return")
        self.profile = document("profile")
        self.detail = document("image-detail" if image else "text-detail")
        self.gallery = document("image-gallery")
        self.package = PACKAGE
        self.after_capture = None
        self.capture_error = None
        self.visit_error = None
        self.back_error = None
        self.capture_count = 0

    def read(self, what):
        if what == "screen_reader_hierarchy":
            return self.xml
        if what == "app":
            return {"package": self.package}
        if what == "screenshot":
            self.capture_count += 1
            if self.capture_error:
                raise self.capture_error
            if self.after_capture:
                self.after_capture()
            return Image.new("RGB", SIZE, "navy")
        return super().read(what)

    def tap(self, target, exclude, kind):
        assert free_tap_zone(target, exclude) is not None
        screen = read_screen(self.xml, SIZE)
        if screen.kind in {"profile", "detail", "media"}:
            assert target == next(
                t.visibility.visible_bounds
                for t in screen.controls
                if t.label == "Back"
            )
            self.events.append(("tap", "inspection Back"))
            self.xml = self.restored
            if self.back_error:
                raise self.back_error
            return
        matches = [
            t
            for p in screen.posts
            for t in p.targets
            if t.visibility.visible_bounds is not None
            and t.visibility.overlaps == tuple(exclude)
            and t.visibility.visible_bounds[0]
            <= target[0]
            < target[2]
            <= t.visibility.visible_bounds[2]
            and t.visibility.visible_bounds[1]
            <= target[1]
            < target[3]
            <= t.visibility.visible_bounds[3]
        ]
        if matches:
            assert len(matches) == 1
            selected = matches[0]
            assert tuple(exclude) == selected.visibility.overlaps
            self.events.append(("visit", selected.label))
            self.xml = {
                "Visit author": self.profile,
                "Open post": self.detail,
                "Open media 0": self.gallery,
            }[selected.label]
            if self.visit_error:
                raise self.visit_error
            return
        super().tap(target, exclude, kind)

    def command(self, name, value):
        if name == "back" and read_screen(self.xml, SIZE).kind == "detail":
            self.events.append(("back", None))
            self.xml = self.restored
            if self.back_error:
                raise self.back_error
            return
        super().command(name, value)


def started(image=False, wrapper=False):
    replay = InspectionReplay(image)
    app = XBrowser(replay.phone, {"search"}) if wrapper else X(replay.phone)
    query = "from:NASA filter:images -filter:replies" if image else "from:NASA"
    if wrapper:
        app.browser.result_tab = "latest"
        # XBrowser opens Top; the captured tab is changed without altering content.
        root = etree.fromstring(replay.results.encode())
        for label in ("Top", "Latest"):
            node = root.xpath(".//*[@content-desc=$label]", label=label)[0].getparent()
            node.set("selected", "true" if label == "Top" else "false")
        replay.results = etree.tostring(root, encoding="unicode")
        replay.restored = replay.results
        app.start("fixture_owner", "search", query)
    else:
        app.start("fixture_owner", "search", query=query, result_tab="latest")
    return replay, app


def shift_detail(distance):
    root = etree.fromstring(document("text-detail").encode())
    listing = root.xpath('.//*[@resource-id="PostDetail"]/node[@scrollable="true"]')[0]
    for child in listing:
        for n in child.iter():
            left, top, right, bottom = bounds(n)
            n.set("bounds", f"[{left},{top + distance}][{right},{bottom + distance}]")
    return etree.tostring(root, encoding="unicode")


def test_profile_visit_reverifies_author_and_original_selected_occurrence():
    replay, app = started()
    source = app.observe()
    report = app.visit_profile()
    assert report.profile.handle == source.author == "@NASA"
    assert report.source_key == source.content_key
    assert app.observe().content_key == source.content_key
    assert app.query == "from:NASA" and app.result_tab == "latest"
    assert app.verified_account == "@fixture_owner"
    assert replay.events[-2:] == [("visit", "Visit author"), ("tap", "inspection Back")]


def test_detail_inspection_returns_separate_related_post_without_inventing_main_content():
    replay, app = started()
    source = app.observe()
    report = app.inspect_thread(max_scrolls=0)
    assert report.source_key == source.content_key
    assert report.detail.main_post is None and not report.main_verified
    assert report.posts[0].author == "@InkSpireMusic"
    assert report.posts[0].body != source.body
    assert report.stop_reason == "scroll_limit" and not report.complete
    assert app.observe().content_key == source.content_key
    assert not any(e[0] == "gesture" for e in replay.events)


def test_thread_scrolling_is_bounded_measured_and_deduplicated():
    replay, app = started()
    replay.scrolls = [shift_detail(-180)]
    report = app.inspect_thread(max_scrolls=1)
    assert report.scrolls == 1 and report.stop_reason == "scroll_limit"
    assert len(report.posts) == 1
    assert app.observe().author == "@NASA"
    assert len([e for e in replay.events if e[0] == "gesture"]) == 1


def test_stationary_thread_stops_without_claiming_completion():
    _replay, app = started()
    report = app.inspect_thread(max_scrolls=8)
    assert report.scrolls == 1 and report.stop_reason == "no_progress"
    assert not report.complete
    assert app.observe().author == "@NASA"


@pytest.mark.parametrize("change", ["query", "author", "position"])
def test_return_requires_prior_query_and_post_continuity(change):
    replay, app = started()
    if change == "query":
        replay.restored = replay.restored.replace("from:NASA", "other")
    elif change == "author":
        replay.restored = replay.restored.replace("@NASA", "@Else")
    else:
        root = etree.fromstring(replay.restored.encode())
        root.xpath('.//*[@resource-id="timeline_post"]')[0].set(
            "bounds", "[176,478][876,527]"
        )
        replay.restored = etree.tostring(root, encoding="unicode")
    with pytest.raises(XError):
        app.visit_profile()
    assert app.verified_account is None
    assert len([e for e in replay.events if e == ("tap", "inspection Back")]) == 1


def test_wrong_profile_handle_stops_without_following_or_claiming_return():
    replay, app = started()
    replay.profile = replay.profile.replace("@NASA", "@Else")
    with pytest.raises(XError, match="profile"):
        app.visit_profile()
    assert app.verified_account is None
    assert replay.events[-1] == ("visit", "Visit author")


@pytest.mark.parametrize("stage", ["open", "return", "capture", "cancel"])
def test_uncertainty_and_cancellation_never_retry_mutations_and_allow_cleanup(stage):
    replay, app = started(image=True)
    if stage == "open":
        replay.visit_error = OSError("tap response lost")
    elif stage == "return":
        replay.back_error = OSError("back response lost")
    elif stage == "capture":
        replay.capture_error = OSError("capture failed")
    else:
        replay.capture_error = InteractionCancelled("cancelled")
    with pytest.raises(
        InteractionCancelled if stage == "cancel" else InteractionError
    ) as error:
        app.inspect_media()
    if stage != "cancel":
        assert error.value.result.status == Status.UNCERTAIN
    assert app.verified_account is None
    assert len([e for e in replay.events if e[0] == "visit"]) == 1
    assert len([e for e in replay.events if e == ("tap", "inspection Back")]) <= 1
    replay.phone.close().require()
    assert replay.closed


def test_image_capture_verifies_gallery_and_returns_to_the_source():
    replay, app = started(image=True)
    source = app.observe()
    report = app.inspect_media(frame_count=2, interval=0.2)
    assert report.source_key == source.content_key
    assert report.view == "gallery" and not report.partial
    assert report.crop == (0, 724, 1080, 1617)
    assert len(report.frames) == replay.capture_count == 2
    assert all(frame.startswith(b"\xff\xd8") for frame in report.frames)
    assert app.observe().content_key == source.content_key


@pytest.mark.parametrize("change", ["author", "caption", "description", "app"])
def test_gallery_mismatch_during_capture_invalidates_without_returning_frames(change):
    replay, app = started(image=True)

    def changed():
        if change == "app":
            replay.package = "another.app"
        elif change == "author":
            replay.xml = replay.xml.replace("@NASA", "@Else")
        elif change == "caption":
            replay.xml = replay.xml.replace(
                "Let's talk about Voyager", "A different post about Voyager"
            )
        else:
            replay.xml = replay.xml.replace("An artist's concept", "A different image")

    replay.after_capture = changed
    with pytest.raises(XError):
        app.inspect_media()
    assert replay.capture_count == 1
    assert app.verified_account is None
    assert ("tap", "inspection Back") not in replay.events


def test_video_inspection_crops_visible_region_without_opening_or_advancing():
    replay, app = started()
    app.advance()
    source = app.observe()
    report = app.inspect_media(frame_count=2, interval=0.2)
    assert report.view == "inline" and report.partial
    assert len(report.frames) == 2
    assert report.crop[3] <= app._screen.content_viewport[3]
    assert not any(e[0] == "visit" for e in replay.events)
    assert app.observe().content_key == source.content_key


@pytest.mark.parametrize("overlaid", [False, True])
def test_browser_inspection_preserves_identity_and_supplies_explicit_frames(overlaid):
    replay, browser = started(image=True, wrapper=True)
    if overlaid:
        replay.gallery = full_screen_gallery()
    before = browser.observe()
    assert not before.frames
    browser.act("inspect", before)
    after = browser.observe(previous=before)
    assert after.identity == before.identity
    assert after.frames and after.post_context["visual_content_available"]
    assert after.post_context["media_inspection"]["view"] == "gallery"
    assert after.post_context["media_inspection"]["partial"] is overlaid
    assert after.caption == before.caption and not after.caption_expanded
    with pytest.raises(XError):
        browser.visit_profile(replace(after, identity="stale"))
    assert not browser.browsing_valid


def test_browser_retains_attributed_inspection_context_until_recovery():
    _replay, browser = started(wrapper=True)
    source = browser.observe()
    browser.visit_profile(source)
    browser.inspect_thread(source, max_scrolls=0)
    observed = browser.observe(previous=source)
    assert observed.identity == source.identity
    assert observed.caption == source.caption
    profile = observed.post_context["profile_inspection"]
    assert profile["username"] == "NASA"
    assert profile["text"] and not profile["complete"]
    thread = observed.post_context["thread_inspection"]
    assert thread["posts"][0]["username"] == "InkSpireMusic"
    assert thread["posts"][0]["body"] != source.caption
    assert thread["main_text"] is None
    assert not thread["complete"] and not thread["main_verified"]
    assert thread["scrolls"] == 0
    assert observed.post_url is None and observed.native_post_id is None
    browser.recover()
    recovered = browser.observe()
    assert recovered.identity != source.identity
    assert "profile_inspection" not in recovered.post_context
    assert "thread_inspection" not in recovered.post_context


@pytest.mark.parametrize(
    "options",
    [{"max_posts": 0}, {"max_posts": 51}, {"max_scrolls": 9}, {"max_scrolls": True}],
)
def test_thread_limits_reject_invalid_values_before_navigation(options):
    replay, app = started()
    events = list(replay.events)
    with pytest.raises(ValueError):
        app.inspect_thread(**options)
    assert replay.events == events


@pytest.mark.parametrize(
    "options",
    [
        {"index": -1},
        {"index": True},
        {"frame_count": 0},
        {"frame_count": 7},
        {"interval": float("nan")},
        {"interval": 6},
    ],
)
def test_media_limits_reject_invalid_values_before_navigation(options):
    replay, app = started(image=True)
    events = list(replay.events)
    with pytest.raises(ValueError):
        app.inspect_media(**options)
    assert replay.events == events


def test_conflicting_own_profile_evidence_invalidates_the_verified_account():
    replay, app = started()
    replay.profile = replay.profile.replace('text="Follow"', 'text="Edit profile"')
    assert read_screen(replay.profile, SIZE).active_account == "@NASA"
    with pytest.raises(XError, match="account"):
        app.visit_profile()
    assert app.verified_account is None
    assert ("tap", "inspection Back") not in replay.events


def test_collapsed_detail_return_restores_back_with_one_bounded_scroll():
    replay, app = started(image=True)
    replay.detail = document("image-detail-scrolled")
    replay.scrolls = [document("image-detail")]
    source = app.observe()
    report = app.inspect_thread(max_scrolls=0)
    assert report.source_key == source.content_key
    assert app.observe().content_key == source.content_key
    gestures = [e for e in replay.events if e[0] == "gesture"]
    assert len(gestures) == 1 and gestures[0][2] == "down"
    assert ("back", None) not in replay.events


def test_collapsed_detail_back_restoration_exhausts_its_bound_without_blind_back():
    replay, app = started(image=True)
    replay.detail = document("image-detail-scrolled")
    with pytest.raises(XError, match="Back control within the limit"):
        app.inspect_thread(max_scrolls=0)
    assert len([e for e in replay.events if e[0] == "gesture"]) == 8
    assert ("back", None) not in replay.events
    assert ("tap", "inspection Back") not in replay.events
    assert app.verified_account is None


@pytest.mark.parametrize("surface", ["profile", "detail", "gallery"])
def test_explicit_recovery_from_inspection_reverifies_the_drawer_account(surface):
    replay, app = started(image=True)
    replay.xml = getattr(replay, surface)
    source = app.recover()
    assert source.author == "@NASA" and app.verified_account == "@fixture_owner"
    assert replay.events.count(("tap", "Show navigation drawer")) == 2


def test_expired_media_capture_does_not_return_frames_and_cleanup_still_succeeds():
    from taktik.core.shared.phone_interaction import SessionExpired

    replay, app = started(image=True)
    replay.phone.configure(deadline=replay.now + 1)
    replay.after_capture = lambda: setattr(replay, "now", replay.now + 2)
    with pytest.raises(SessionExpired):
        app.inspect_media()
    assert app.verified_account is None
    assert ("tap", "inspection Back") not in replay.events
    replay.phone.close().require()
    assert replay.closed


def test_profile_visit_restores_the_home_timeline_occurrence():
    replay = InspectionReplay()
    app = X(replay.phone)
    source = app.start("fixture_owner", "for_you")
    replay.restored = replay.xml
    replay.profile = replay.profile.replace("@NASA", source.author)
    report = app.visit_profile()
    assert report.profile.handle == source.author
    assert app.observe().content_key == source.content_key
    assert app.timeline == "for_you"


def test_physical_thread_sequence_has_two_verified_scrolls_then_header_restoration():
    replay, app = started()
    replay.detail = document("thread-ready")
    replay.scrolls = [
        document("thread-first-scroll"),
        document("thread-second-scroll"),
        document("thread-header-restored"),
    ]
    source = app.observe()
    report = app.inspect_thread(max_scrolls=2)
    assert report.scrolls == 2 and report.stop_reason == "scroll_limit"
    assert len(report.posts) == 1 and report.posts[0].author == "@InkSpireMusic"
    assert [e[2] for e in replay.events if e[0] == "gesture"] == ["up", "up", "down"]
    assert app.observe().content_key == source.content_key


def full_screen_gallery():
    # X on Android 16 advertises its image as the full-screen media host, even
    # when the Back/options, author, caption and actions overlay that image.
    root = etree.fromstring(document("image-gallery").encode())
    scope = root.xpath('.//*[@resource-id="MediaGallery"]')[0]
    image = scope.xpath('.//*[@content-desc!=""]')[0]
    assert image.get("content-desc").startswith("An artist's concept")
    node = image
    while node is not scope:
        node.set("bounds", "[0,136][1080,2230]")
        node = node.getparent()
    return etree.tostring(root, encoding="unicode")


def test_full_screen_gallery_retains_safe_crop_and_back():
    screen = read_screen(full_screen_gallery(), SIZE)
    assert screen.kind == "media", screen.reason
    assert screen.gallery.crop == (0, 290, 1080, 1677)
    assert screen.gallery.partial
    assert screen.controls[0].label == "Back"
    assert screen.controls[0].visibility.unobscured


def test_captured_android_gallery_retains_safe_image_and_back():
    screen = read_screen(document("overlay-gallery"), (1440, 3216))
    assert screen.kind == "media", screen.reason
    assert screen.gallery.author == "@fixture_author"
    assert screen.gallery.crop == (0, 904, 1440, 2174)
    assert screen.gallery.partial
    assert screen.controls[0].visibility.unobscured


def test_search_inspection_captures_partial_image_and_returns_same_post():
    replay, app = started(image=True)
    replay.gallery = full_screen_gallery()
    source = app.observe()
    report = app.inspect_media(frame_count=2, interval=0.2)
    assert report.partial and report.crop == (0, 290, 1080, 1677)
    assert report.source_key == source.content_key
    assert len(report.frames) == replay.capture_count == 2
    assert Image.open(io.BytesIO(report.frames[0])).size == (797, 1024)
    assert app.observe().content_key == source.content_key
    assert replay.events[-1] == ("tap", "inspection Back")


def test_search_restarts_from_gallery_and_reverifies_account():
    replay, app = started(image=True)
    replay.xml = full_screen_gallery()
    post = app.recover()
    assert post.observable and app.verified_account == "@fixture_owner"
    assert replay.events.count(("tap", "Show navigation drawer")) == 2
    assert replay.events.count(("tap", "inspection Back")) == 1


def covered_image():
    root = etree.fromstring(document("image-gallery").encode())
    root.xpath('.//*[@content-desc="More options"]')[0].set(
        "bounds", "[0,724][1080,1617]"
    )
    return etree.tostring(root, encoding="unicode")


def test_fully_covered_image_stays_navigable_but_cannot_supply_frames():
    replay, app = started(image=True)
    replay.gallery = covered_image()
    screen = read_screen(replay.gallery, SIZE)
    assert screen.kind == "media", screen.reason
    assert screen.gallery.crop is None
    with pytest.raises(XError, match="covered"):
        app.inspect_media()
    assert replay.capture_count == 0
    assert app.verified_account is None
    assert app.recover().observable


def test_uncertain_back_from_overlaid_gallery_is_not_retried():
    replay, app = started(image=True)
    replay.xml = full_screen_gallery()
    replay.back_error = OSError("back response lost")
    with pytest.raises(InteractionError):
        app.recover()
    assert app.verified_account is None
    assert replay.events.count(("tap", "inspection Back")) == 1


def test_gallery_crop_change_during_capture_discards_frames():
    replay, app = started(image=True)
    replay.gallery = full_screen_gallery()

    def changed():
        root = etree.fromstring(replay.xml.encode())
        root.xpath('.//*[@content-desc="More options"]')[0].set(
            "bounds", "[904,800][1036,932]"
        )
        replay.xml = etree.tostring(root, encoding="unicode")

    replay.after_capture = changed
    with pytest.raises(XError, match="changed"):
        app.inspect_media()
    assert app.verified_account is None
    assert replay.capture_count == 1
    assert ("tap", "inspection Back") not in replay.events
