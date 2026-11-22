"""Replay the complete long-caption visit with native character geometry."""

import pytest
from lxml import etree
from unit.social_media.x.services.long_detail_replay import started

from taktik.core.social_media.x.services.browsing.navigation import XError


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
