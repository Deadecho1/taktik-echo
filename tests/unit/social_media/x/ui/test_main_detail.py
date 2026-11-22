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


def partial_header(xml, missing="name", *, handle_top=None):
    """Synthetic omissions of text nodes, without changing the detail structure."""
    root = etree.fromstring(xml.encode())
    avatar = root.xpath('.//*[@resource-id="timeline_post_avatar"]')[0]
    column = avatar.getparent()[1]
    for node in list(column):
        is_handle = node.get("text", "").startswith("@")
        if node.get("text") and (
            missing == "both" or (is_handle == (missing == "handle"))
        ):
            column.remove(node)
        elif is_handle and handle_top is not None:
            from taktik.core.shared.ui.geometry import bounds

            left, _, right, bottom = bounds(node)
            node.set("bounds", f"[{left},{handle_top}][{right},{bottom}]")
    return etree.tostring(root, encoding="unicode")


@pytest.mark.parametrize("native", ["native", "native-second"])
def test_full_missing_header_captures_keep_detail_context_without_attribution(native):
    ordinary = document("missing-header-ordinary")
    screen = read_screen(
        combine_hierarchies(ordinary, document(f"missing-header-{native}")),
        (1440, 3216),
    )
    assert read_screen(ordinary, (1440, 3216)).kind == "detail"
    assert screen.kind == "detail", screen.reason
    assert screen.content_viewport == (0, 160, 1440, 2784)
    assert screen.detail.main_post is None and screen.detail.main_reason
    assert screen.detail.main_header_visible is False
    assert screen.detail.timestamp is not None and screen.scroll_areas
    assert not screen.clipboard_bounds
    assert (223, 3040, 1197, 3216) in screen.overlaps


@pytest.mark.parametrize("top", [159, 160, 161, 162, 190])
def test_missing_name_recovery_does_not_depend_on_handle_viewport_position(top):
    xml = partial_header(document("missing-header-native"), handle_top=top)
    screen = read_screen(xml, (1440, 3216))
    assert screen.kind == "detail", screen.reason
    assert screen.detail.main_post is None
    assert screen.detail.main_header_visible is False


@pytest.mark.parametrize("missing", ["name", "handle", "both"])
def test_incomplete_header_is_not_an_author_even_when_its_avatar_is_named(missing):
    screen = read_screen(partial_header(document(), missing), SIZE)
    assert screen.kind == "detail", screen.reason
    assert screen.detail.main_post is None
    assert screen.detail.main_header_visible is False


def test_missing_header_fixture_integrity():
    manifest = json.loads((FIXTURES / "missing-header-manifest.json").read_text())
    assert manifest["size"] == [1440, 3216]
    for item in manifest["fixtures"]:
        assert set(item) == {"file", "sha256"}
        assert (
            hashlib.sha256((FIXTURES / item["file"]).read_bytes()).hexdigest()
            == item["sha256"]
        )


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


def test_secondary_badge_fixture_integrity_and_synthetic_labels():
    manifest = json.loads((FIXTURES / "badge-manifest.json").read_text())
    assert "Synthetic" in manifest["description"]
    for item in manifest["fixtures"]:
        assert set(item) == {"file", "sha256"}
        assert (
            hashlib.sha256((FIXTURES / item["file"]).read_bytes()).hexdigest()
            == item["sha256"]
        )
    main = read_screen(document("badge-native"), SIZE).detail.main_post
    source = read_screen(document("badge-source"), SIZE).observable_posts[0]
    assert main.author == source.author == "@fixture_author"
    assert main.body == source.body and main.labels == (
        "Verified Business",
        "Fixture Museum",
    )


@pytest.mark.parametrize(
    "problem",
    [
        "scope",
        "composer",
        "duplicate_column",
        "column_control",
        "unknown_text",
        "nested_text",
        "outside_column",
        "foreign_package",
        "navigation_geometry",
        "navigation_structure",
    ],
)
def test_incomplete_header_does_not_recover_unknown_or_malformed_structure(problem):
    from copy import deepcopy

    root = etree.fromstring(document("missing-header-native").encode())
    scope = root.xpath('.//*[@resource-id="PostDetail"]')[0]
    avatar = scope.xpath('.//*[@resource-id="timeline_post_avatar"]')[0]
    column = avatar.getparent()[1]
    if problem == "scope":
        scope.set("resource-id", "UnknownScreen")
    elif problem == "composer":
        scope.xpath('.//*[@resource-id="post-detail-reply-text-field"]')[0].set(
            "resource-id", "Unknown"
        )
    elif problem == "duplicate_column":
        avatar.addnext(deepcopy(column))
    elif problem == "column_control":
        column.set("clickable", "true")
    elif problem == "unknown_text":
        column[0].set("text", "Unknown metadata")
    elif problem == "nested_text":
        column[0].append(deepcopy(column[0]))
    elif problem == "outside_column":
        column[0].set("bounds", "[0,162][224,225]")
    elif problem == "foreign_package":
        column[0].set("package", "example.other")
    else:
        bar = root.xpath(
            './node[@resource-id="com.android.systemui:id/navigation_bar_frame"]'
        )[0]
        if problem == "navigation_geometry":
            bar.set("bounds", "[223,500][1197,3216]")
        else:
            bar[0].set("resource-id", "Unknown")
    screen = read_screen(etree.tostring(root), (1440, 3216))
    assert screen.kind == "unsupported" and screen.detail is None


def test_missing_header_without_quote_stays_unattributed():
    root = etree.fromstring(document("missing-header-native").encode())
    listing = root.xpath('.//*[@resource-id="PostDetail"]/node[@scrollable="true"]')[0]
    for child in list(listing):
        if child.xpath('.//*[@content-desc="Quote"]'):
            listing.remove(child)
    screen = read_screen(etree.tostring(root), (1440, 3216))
    assert screen.kind == "detail" and screen.detail.main_post is None
    assert screen.detail.main_header_visible is False


@pytest.mark.parametrize("missing", ["name", "both"])
def test_navigation_with_missing_text_does_not_require_an_avatar_description(missing):
    root = etree.fromstring(
        partial_header(document("missing-header-native"), missing).encode()
    )
    root.xpath('.//*[@resource-id="timeline_post_avatar"]')[0].set("content-desc", "")
    screen = read_screen(etree.tostring(root), (1440, 3216))
    assert screen.kind == "detail" and screen.detail.main_post is None
    assert screen.detail.main_header_visible is False
