"""Native inspection evidence never borrows missing main-post text from replies."""

import hashlib
import json

import pytest
from lxml import etree
from unit.paths import CORE

from taktik.core.social_media.x.services.browsing.navigation import (
    _free_regions,
    _scroll_motion,
)
from taktik.core.social_media.x.ui.screen import read_screen

FIXTURES = CORE / "tests/unit/social_media/x/fixtures/inspection"
SIZE = (1080, 2340)


def document(name):
    return (FIXTURES / f"{name}.xml").read_text()


def changed(name, xpath, attribute, value):
    root = etree.fromstring(document(name).encode())
    for node in root.xpath(xpath):
        node.set(attribute, value)
    return etree.tostring(root)


def test_captured_inspection_fixture_hashes():
    manifest = json.loads((FIXTURES / "manifest.json").read_text())
    assert manifest["size"] == list(SIZE)
    for item in manifest["fixtures"]:
        assert (
            hashlib.sha256((FIXTURES / item["file"]).read_bytes()).hexdigest()
            == item["sha256"]
        )


def test_profile_identity_is_separate_from_authors_of_its_reposts():
    screen = read_screen(document("legacy-profile"), SIZE)
    assert screen.kind == "profile"
    assert screen.profile.handle == "@NASA"
    assert screen.profile.display_name.strip() == "NASA"
    assert screen.posts[0].author == "@NASA_Events"
    assert screen.tab == "Reposts"
    assert any(t.label == "Back" for t in screen.controls)


def test_standalone_profile_has_direct_identity_and_header_text():
    screen = read_screen(document("profile"), SIZE)
    assert screen.profile.handle == "@NASA"
    assert any(
        s.text == "Making the seemingly impossible, possible. ✨"
        for s in screen.profile.text
    )
    assert screen.active_account is None
    assert screen.content_viewport == (0, 1389, 1080, 2230)


@pytest.mark.parametrize(
    "name", ["legacy-detail", "text-detail", "image-detail", "image-detail-scrolled"]
)
def test_details_keep_main_content_unavailable_and_parse_other_posts_separately(name):
    screen = read_screen(document(name), SIZE)
    assert screen.kind == "detail"
    assert screen.detail.main_post is None
    assert "omits its author and body" in screen.detail.main_reason
    assert screen.reason == screen.detail.main_reason
    assert screen.content_viewport[3] in {1943, 2098}
    if name == "text-detail":
        assert [p.author for p in screen.observable_posts] == ["@InkSpireMusic"]
        assert screen.detail.timestamp.text.startswith("11:49 PM")
    if name == "image-detail-scrolled":
        assert screen.collapsed
        assert screen.content_viewport[1] == 136
        assert screen.observable_posts[0].author == "@kinda_busy"


def test_native_detail_movement_survives_header_collapse():
    before = read_screen(document("image-detail"), SIZE)
    after = read_screen(document("image-detail-scrolled"), SIZE)
    assert _scroll_motion(before, after) == -312


def test_open_post_target_excludes_text_links_and_nested_controls():
    screen = read_screen(document("text-source"), SIZE)
    post = screen.posts[0]
    target = next(t.visibility for t in post.targets if t.label == "Open post")
    assert post.body_visibility.bounds in target.overlaps
    for action in post.actions:
        assert action.visibility.bounds in target.overlaps
    assert list(_free_regions(target.visible_bounds, target.overlaps, 8))
    author = next(t.visibility for t in post.targets if t.label == "Visit author")
    assert author.unobscured


def test_gallery_uses_ancestor_clipping_to_crop_image_without_controls():
    screen = read_screen(document("image-gallery"), SIZE)
    assert screen.kind == "media"
    assert screen.gallery.author == "@NASA"
    assert screen.gallery.crop == (0, 724, 1080, 1617)
    assert screen.gallery.description.startswith("An artist's concept")
    assert screen.posts == ()
    assert screen.controls[0].label == "Back"


@pytest.mark.parametrize(
    "mutation",
    [
        "handle",
        "covered_handle",
        "back",
        "image_control",
        "foreign_package",
        "keyboard",
        "conflicting_screen",
    ],
)
def test_malformed_or_obscured_gallery_is_unsupported(mutation):
    root = etree.fromstring(document("image-gallery").encode())
    scope = root.xpath('.//*[@resource-id="MediaGallery"]')[0]
    if mutation == "handle":
        root.xpath('.//*[@text="@NASA"]')[0].set("text", "unknown")
    elif mutation == "covered_handle":
        root.xpath('.//*[@text="@NASA"]')[0].getparent().set(
            "bounds", "[193,1677][795,1750]"
        )
    elif mutation == "back":
        root.xpath('.//*[@content-desc="Back"]')[0].set("enabled", "false")
    elif mutation == "image_control":
        root.xpath('.//*[@content-desc="More options"]')[0].set(
            "bounds", "[904,800][1036,932]"
        )
    elif mutation == "foreign_package":
        root.xpath('.//*[@text="@NASA"]')[0].set("package", "other.app")
    elif mutation == "keyboard":
        etree.SubElement(
            root,
            "node",
            package="com.google.android.inputmethod.latin",
            bounds="[0,1400][1080,2340]",
        )
    else:
        etree.SubElement(
            scope,
            "node",
            {
                "resource-id": "PostDetail",
                "package": "com.twitter.android",
                "bounds": "[0,0][1080,2340]",
            },
        )
    assert read_screen(etree.tostring(root), SIZE).kind == "unsupported"


@pytest.mark.parametrize("part", ["author", "caption", "back"])
def test_native_gallery_controls_cannot_cover_identity_or_return_control(part):
    area = {
        "author": "[193,1697][357,1789]",
        "caption": "[44,1827][1036,1925]",
        "back": "[44,158][176,290]",
    }[part]
    xml = changed("image-gallery", './/*[@content-desc="More options"]', "bounds", area)
    assert read_screen(xml, SIZE).kind == "unsupported"


def test_wrapping_unreadable_detail_content_cannot_create_scroll_geometry():
    from taktik.core.social_media.x.services.browsing.navigation import (
        XError,
        scroll_region,
    )

    root = etree.fromstring(document("image-detail").encode())
    body = root.xpath(
        './/*[@resource-id="PostDetail"]/node/node[@bounds="[22,499][1047,1782]"]'
    )[0]
    etree.SubElement(
        body,
        "node",
        {
            "class": "android.view.View",
            "package": "com.twitter.android",
            "bounds": body.get("bounds"),
            "enabled": "true",
        },
    )
    screen = read_screen(etree.tostring(root), SIZE)
    assert screen.kind == "detail"
    with pytest.raises(XError):
        scroll_region(screen)
