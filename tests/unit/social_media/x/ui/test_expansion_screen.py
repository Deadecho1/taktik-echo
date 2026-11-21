"""Expansion evidence separates readable inline text from missing detail content."""

import hashlib
import json

from unit.paths import CORE

from taktik.core.social_media.x.ui.screen import read_screen

FIXTURES = CORE / "tests/unit/social_media/x/fixtures/expansion"
SIZE = (1080, 2340)


def screen(name):
    return read_screen((FIXTURES / f"{name}.xml").read_text(), SIZE)


def test_expansion_fixture_hashes():
    manifest = json.loads((FIXTURES / "manifest.json").read_text())
    assert manifest["size"] == list(SIZE)
    for item in manifest["fixtures"]:
        assert (
            hashlib.sha256((FIXTURES / item["file"]).read_bytes()).hexdigest()
            == item["sha256"]
        )


def test_native_inline_expansion_exposes_independently_attributed_full_text():
    before = screen("source").observable_posts[0]
    after = screen("expanded").observable_posts[0]
    assert before.author == after.author == "@OpenAI"
    assert not before.body_complete and after.body_complete
    assert before.header_visibility == after.header_visibility
    assert after.body.startswith(before.body.removesuffix("\xa0Show more"))
    assert screen("return").observable_posts[0].content_key == after.content_key


def test_long_expanded_accessibility_text_does_not_establish_visible_complete_text():
    before = screen("long-source").observable_posts[0]
    after = screen("long-expanded")
    assert before.author == after.posts[0].author
    assert len(after.posts[0].body) > len(before.body)
    assert not after.posts[0].body_complete
    assert not after.observable_posts


def test_deeper_detail_dump_still_does_not_supply_main_post_content():
    for name in ("detail", "detail-depth-100"):
        result = screen(name)
        assert result.kind == "detail"
        assert result.detail.main_post is None
