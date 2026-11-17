"""Native main-detail reads retain attribution and the source browsing occurrence."""

import pytest
from lxml import etree
from unit.social_media.x.services.browsing.test_inspection_visits import (
    InspectionReplay,
)
from unit.social_media.x.ui.test_main_detail import document

from taktik.core.shared.phone_interaction import InteractionError, Status
from taktik.core.social_media.x.services.browsing.navigation import (
    X,
    XError,
    scroll_region,
)
from taktik.core.social_media.x.ui.screen import read_screen


class MainReplay(InspectionReplay):
    def __init__(self):
        super().__init__()
        self.results = self.latest = document("image-source")
        self.restored = document("image-return")
        self.detail = document("image-ordinary")
        self.native = document("image-main")
        self.native_error = None
        self.native_reads = 0

    def read(self, what):
        if what == "screen_reader_hierarchy":
            self.native_reads += 1
            if self.native_error:
                raise self.native_error
            return self.native
        return super().read(what)


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
