"""Independent main-post evidence captured with native screen-reader semantics."""

import hashlib
import json

import pytest
from lxml import etree
from unit.paths import CORE

from taktik.core.social_media.x.ui.detail import combine_hierarchies
from taktik.core.social_media.x.ui.screen import read_screen

FIXTURES = CORE / "tests/unit/social_media/x/fixtures/detail"
SIZE = (1080, 2340)


def document(name="image-main"):
    return (FIXTURES / f"{name}.xml").read_text()


def test_main_detail_is_read_independently_with_separate_media_and_timestamp():
    screen = read_screen(document(), SIZE)
    source = read_screen(document("image-source"), SIZE).observable_posts[0]
    assert screen.kind == "detail" and screen.reason is None
    main = screen.detail.main_post
    assert main.author == "@NASA" and main.display_name == "NASA"
    assert main.body == source.body and main.body_complete and main.observable
    assert main.media[0].description == source.media[0].description
    assert main.media[0].visibility.overlaps
    assert main.body_visibility.bounds == (22, 499, 1047, 947)
    assert screen.detail.timestamp.text.startswith("7:14 PM")
    assert main not in screen.posts


def test_main_video_detail_keeps_the_play_glyph_out_of_its_body():
    screen = read_screen(document("video-main"), SIZE)
    source = read_screen(document("video-source"), SIZE).observable_posts[0]
    assert screen.detail.main_post is not None, screen.reason
    main = screen.detail.main_post
    assert main.author == source.author and main.body == source.body
    assert main.observable and main.body_complete
    assert [(m.kind, m.description) for m in main.media] == [("video", "Video")]
    assert main.media[0].visibility.visible_bounds[3] == 2098


def test_ordinary_detail_retains_the_explicit_missing_main_result():
    screen = read_screen(document("image-ordinary"), SIZE)
    assert screen.kind == "detail" and screen.detail.main_post is None
    assert "omits" in screen.detail.main_reason


def test_loaded_replies_do_not_hide_the_independent_main_post():
    screen = read_screen(document("image-loaded"), SIZE)
    assert screen.detail.main_post is not None, screen.reason
    assert screen.detail.main_post.observable
    assert len(screen.detail.main_post.actions) == 5


def test_combined_native_read_preserves_structured_replies_and_main_content():
    for label in ("loaded", "scrolled"):
        ordinary = read_screen(document(f"image-{label}-ordinary"), SIZE)
        native = read_screen(document(f"image-{label}"), SIZE)
        combined = read_screen(
            combine_hierarchies(
                document(f"image-{label}-ordinary"), document(f"image-{label}")
            ),
            SIZE,
        )
        assert combined.posts == ordinary.posts
        assert combined.detail.main_post == native.detail.main_post
    assert len(combined.observable_posts) == 2


@pytest.mark.parametrize("change", ["timestamp", "position", "sort"])
def test_native_and_ordinary_context_drift_cannot_be_joined(change):
    from taktik.core.social_media.x.ui.screen import _Unsupported

    xml = document("image-scrolled")
    if change == "timestamp":
        xml = xml.replace("7:14 PM", "8:14 PM")
    elif change == "position":
        xml = xml.replace("[22,1108][623,1157]", "[22,1109][623,1158]")
    else:
        xml = xml.replace('text="Relevant"', 'text="Most recent"')
    with pytest.raises(_Unsupported, match="changed position"):
        combine_hierarchies(document("image-scrolled-ordinary"), xml)


@pytest.mark.parametrize(
    "mutation",
    [
        "handle",
        "name",
        "avatar",
        "header_order",
        "body_control",
        "extra_body",
        "quote_as_body",
    ],
)
def test_unknown_or_contradictory_main_layout_is_not_an_observation(mutation):
    root = etree.fromstring(document().encode())
    handle = root.xpath('.//*[@text="@NASA"]')[0]
    name = root.xpath('.//*[@text="NASA"]')[0]
    avatar = root.xpath('.//*[@resource-id="timeline_post_avatar"]')[0]
    body = root.xpath('.//*[@text and starts-with(@text,"Join us in getting")]')[0]
    if mutation == "handle":
        handle.set("text", "not a handle")
    elif mutation == "name":
        name.set("text", "Someone else")
    elif mutation == "avatar":
        avatar.set("content-desc", "Someone else")
    elif mutation == "header_order":
        name.getparent().insert(0, handle)
    elif mutation == "body_control":
        body.set("clickable", "true")
    elif mutation == "extra_body":
        body.addnext(etree.fromstring(etree.tostring(body)))
    else:
        body.set("content-desc", "Quote")
    screen = read_screen(etree.tostring(root), SIZE)
    assert screen.detail is None or screen.detail.main_post is None


def test_obscured_main_author_never_becomes_observable():
    root = etree.fromstring(document().encode())
    button = root.xpath('.//*[@content-desc="Post options"]')[0]
    button.set("bounds", "[176,420][302,463]")
    main = read_screen(etree.tostring(root), SIZE).detail.main_post
    assert main is None or not main.observable


def test_main_detail_fixture_provenance():
    manifest = json.loads((FIXTURES / "manifest.json").read_text())
    for item in manifest["fixtures"]:
        assert (
            hashlib.sha256((FIXTURES / item["file"]).read_bytes()).hexdigest()
            == item["sha256"]
        )
