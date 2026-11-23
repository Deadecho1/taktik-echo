"""Replay the complete long-caption visit with native character geometry."""

import pytest
from lxml import etree
from unit.social_media.x.services.browsing.test_native_detail_visits import MainReplay
from unit.social_media.x.ui.test_main_detail import SIZE, document

from taktik.core.social_media.x.services.browsing.navigation import X, XError
from taktik.core.social_media.x.ui.screen import read_screen


def started():
    replay = MainReplay()
    replay.results = replay.latest = document("long-run-source")
    replay.restored = document("long-run-return")
    replay.detail = document("long-step-0-ordinary")
    replay.native = document("long-step-0-native")
    gesture = replay.gesture
    replay.stage = 0

    def scroll(intent, direction, region, distance, exclude):
        gesture(intent, direction, region, distance, exclude)
        replay.stage += 1
        replay.xml = document(f"long-step-{replay.stage}-ordinary")
        replay.native = document(f"long-step-{replay.stage}-native")

    replay.gesture = scroll
    app = X(replay.phone)
    app.start(
        "fixture_owner",
        "search",
        query=read_screen(replay.results, SIZE).query,
        result_tab="latest",
    )
    return replay, app


def test_full_native_body_coverage_keeps_the_original_snapshot_clipped():
    replay, app = started()
    source = app.observe()
    result = app.inspect_thread(max_scrolls=8)
    assert result.main_text == result.detail.main_post.body
    assert len(result.main_text) == 1857 and result.main_text_complete
    assert not result.detail.main_post.body_complete
    assert not result.main_verified and not result.complete
    assert result.scrolls == 8 and result.stop_reason == "scroll_limit"
    assert [e[2] for e in replay.events if e[0] == "gesture"] == ["up"] * 8 + ["down"]
    assert app.observe().content_key == source.content_key == result.source_key


def test_zero_scrolls_returns_only_the_initial_observed_prefix():
    replay, app = started()
    result = app.inspect_thread(max_scrolls=0)
    assert len(result.main_text) == 727 and not result.main_text_complete
    assert not any(e[0] == "gesture" for e in replay.events)


def test_changing_unseen_native_text_invalidates_the_read_instead_of_joining_it():
    replay, app = started()
    scroll = replay.gesture

    def changed(*args):
        scroll(*args)
        replay.native = replay.native.replace("Former Google CEO", "Former Search CEO")

    replay.gesture = changed
    with pytest.raises(XError, match="native main text changed"):
        app.inspect_thread(max_scrolls=8)
    assert app.verified_account is None
    assert len([e for e in replay.events if e[0] == "gesture"]) == 1


def test_observed_truncation_control_does_not_mean_the_caption_is_complete():
    replay, app = started()
    read = replay.read

    def truncated(what):
        xml = read(what)
        if what == "screen_reader_hierarchy":
            root = etree.fromstring(xml.encode())
            for node in root.iter():
                text = node.get("text", "")
                if len(text) == 1857:
                    node.set("text", text[:-10] + " Show more")
            return etree.tostring(root, encoding="unicode")
        return xml

    replay.read = truncated
    result = app.inspect_thread(max_scrolls=8)
    assert len(result.main_text) == 1857 and result.main_text.endswith(" Show more")
    assert not result.main_text_complete


@pytest.mark.parametrize("missing", ["name", "handle", "both"])
def test_partial_header_during_long_reading_preserves_coverage_and_forward_direction(
    missing,
):
    from unit.social_media.x.ui.test_main_detail import partial_header

    replay, app = started()
    read = replay.read
    omissions = []

    def without_header(what):
        xml = read(what)
        if (
            what == "screen_reader_hierarchy"
            and replay.stage == 0
            and replay.native_reads > 1
        ):
            omissions.append(missing)
            return partial_header(xml, missing)
        return xml

    replay.read = without_header
    source = app.observe()
    report = app.inspect_thread(max_scrolls=8)
    assert omissions
    expected = read_screen(document("long-step-0-native"), SIZE).detail.main_post.body
    assert report.main_text == expected
    assert report.detail.main_post.body == expected
    assert len(report.main_text) == 1857 and report.main_text_complete
    assert not report.main_verified and not report.detail.main_post.body_complete
    assert report.scrolls == 8
    assert [e[2] for e in replay.events if e[0] == "gesture"] == ["up"] * 8 + ["down"]
    assert app.observe().content_key == source.content_key == report.source_key
