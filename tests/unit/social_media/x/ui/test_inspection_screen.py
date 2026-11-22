"""Native inspection evidence never borrows missing main-post text from replies."""

import copy

import pytest
from lxml import etree
from unit.social_media.x.services.inspection_inputs import (
    ENGAGEMENT_FIXTURES,
    FIXTURES,
    LINK_FIXTURES,
    LINK_URL,
    document,
    engagement_document,
    link_document,
)
from unit.x_fixtures import SIZE, fixture_manifest

from taktik.core.shared.behavior.tap import free_tap_zone
from taktik.core.shared.ui.geometry import bounds
from taktik.core.social_media.x.services.browsing.navigation import (
    _free_regions,
    _scroll_motion,
)
from taktik.core.social_media.x.ui.screen import PACKAGE, read_screen


def changed(name, xpath, attribute, value):
    root = etree.fromstring(document(name).encode())
    for node in root.xpath(xpath):
        node.set(attribute, value)
    return etree.tostring(root)


def test_captured_inspection_fixture_hashes():
    manifest = fixture_manifest(FIXTURES / "manifest.json")
    assert manifest["size"] == list(SIZE)


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


def test_engagement_fixture_provenance():
    manifest = fixture_manifest(ENGAGEMENT_FIXTURES / "manifest.json")
    assert manifest["size"] == list(SIZE)


@pytest.mark.parametrize(
    "name,liked,saved",
    [("source", False, False), ("liked", True, False), ("bookmarked", True, True)],
)
def test_native_state_labels_normalize_without_changing_post_identity(
    name, liked, saved
):
    source = read_screen(engagement_document("source"), SIZE).posts[0]
    post = read_screen(engagement_document(name), SIZE).posts[0]
    assert post.observable and post.content_key == source.content_key
    states = {t.label: t.selected for t in post.actions}
    assert states["Like"] is liked and states["Bookmark"] is saved
    assert any(t.label == "Post options" for t in post.targets)


def test_like_animation_does_not_invent_an_engageable_post():
    screen = read_screen(engagement_document("like-animation"), SIZE)
    assert not screen.observable_posts
    assert screen.rejected_posts


def test_bookmark_toast_keeps_the_covered_search_query_unverified():
    screen = read_screen(engagement_document("bookmark-toast"), SIZE)
    assert screen.kind == "unsupported"


@pytest.mark.parametrize("following", [False, True])
def test_search_menu_exposes_native_author_and_relationship_without_feedback(following):
    xml = engagement_document("search-options")
    if following:
        xml = xml.replace("Follow @NASA", "Unfollow @NASA")
    screen = read_screen(xml, SIZE)
    assert screen.kind == "post_options"
    assert screen.post_options.author == "@NASA"
    assert screen.post_options.following is following
    assert screen.post_options.feedback_label is None


@pytest.mark.parametrize(
    "problem", ["author", "duplicate", "covered", "disabled", "unknown"]
)
def test_untrusted_menu_structure_never_supplies_an_engagement_target(problem):
    root = etree.fromstring(engagement_document("search-options").encode())
    label = root.xpath('.//*[@text="Follow @NASA"]')[0]
    if problem == "author":
        label.set("text", "Follow @other")
    elif problem == "duplicate":
        root.xpath('.//*[@text="Mute @NASA"]')[0].set("text", "Follow @NASA")
    elif problem == "covered":
        label.set("bounds", "[154,0][466,1147]")
    elif problem == "disabled":
        label.getparent().set("enabled", "false")
    else:
        label.set("text", "Subscribe @NASA")
    assert read_screen(etree.tostring(root), SIZE).kind == "unsupported"


def test_duplicate_footer_state_labels_reject_the_post():
    root = etree.fromstring(engagement_document("liked").encode())
    icon = root.xpath('.//*[@content-desc="Undo Like"]')[0]
    extra = etree.SubElement(icon.getparent(), "node", **dict(icon.attrib))
    extra.set("content-desc", "Like")
    assert not read_screen(etree.tostring(root), SIZE).observable_posts


def test_native_full_screen_dismissal_excludes_the_sheet_and_every_action_row():
    from taktik.core.social_media.x.services.browsing.engagement import _control

    screen = read_screen(engagement_document("full-screen-dismissal"), SIZE)
    close, region = _control(screen.controls, "Close sheet")
    assert close.visibility.bounds == (0, 0, 1080, 2340)
    assert region[1] >= 136 and region[3] <= 986
    for row in screen.controls:
        if row.label != "Close sheet":
            assert region[3] <= row.visibility.bounds[1]


@pytest.mark.parametrize("flag", ["clickable", "long-clickable"])
def test_nested_menu_controls_never_receive_an_engagement_tap(flag):
    root = etree.fromstring(engagement_document("search-options").encode())
    row = root.xpath('.//*[@text="Follow @NASA"]')[0].getparent()
    attrs = dict(row.attrib)
    attrs.update({"text": "", "content-desc": "", "clickable": "false", flag: "true"})
    etree.SubElement(row, "node", **attrs)
    assert read_screen(etree.tostring(root), SIZE).kind == "unsupported"


def test_post_options_taps_stay_clear_of_grok_and_post_opening_padding():
    from taktik.core.social_media.x.services.browsing.engagement import _control

    for name in ("source", "home-source"):
        screen = read_screen(engagement_document(name), SIZE)
        post = screen.observable_posts[0]
        target, region = _control(post.targets, "Post options")
        left, _, right, _ = target.visibility.bounds
        assert region[0] >= (left + right) // 2
        assert region[1] >= post.header_visibility.bounds[1]
        assert region[3] <= post.header_visibility.bounds[3]


def test_link_fixture_provenance():
    manifest = fixture_manifest(LINK_FIXTURES / "manifest.json")
    assert manifest["size"] == list(SIZE)


def test_share_exposes_only_copy_and_safe_dismissal_targets():
    screen = read_screen(link_document("share"), SIZE)
    assert screen.kind == "share"
    assert not screen.posts
    assert [c.label for c in screen.controls] == ["Close sheet", "Copy link"]
    close, link = screen.controls
    assert link.visibility.unobscured
    assert link.visibility.bounds == (220, 1996, 418, 2230)
    zone = free_tap_zone(close.visibility.visible_bounds, close.visibility.overlaps)
    assert zone[1] >= 136 and zone[3] <= 507


def test_clipboard_receipt_is_metadata_and_occludes_the_underlying_timeline():
    before = read_screen(link_document("source"), SIZE)
    after = read_screen(link_document("copied"), SIZE)
    assert after.kind == "search_results"
    assert after.clipboard_text.startswith(LINK_URL + "?")
    assert before.clipboard_text is None
    assert (
        before.observable_posts[0].content_key == after.observable_posts[0].content_key
    )
    assert (22, 1938, 608, 2257) in after.overlaps
    assert all(after.clipboard_text != p.body for p in after.posts)


def test_clipboard_covering_authored_text_cannot_leave_the_post_observable():
    root = etree.fromstring(link_document("copied").encode())
    for node in root[0].iter():
        left, top, right, bottom = bounds(node)
        node.set("bounds", f"[{left},{top - 1300}][{right},{bottom - 1300}]")
    screen = read_screen(etree.tostring(root), SIZE)
    assert screen.kind == "search_results"
    assert not screen.observable_posts


@pytest.mark.parametrize(
    "problem",
    ["missing", "duplicate", "disabled", "hidden", "nested", "row", "package"],
)
def test_share_rejects_unverifiable_copy_targets(problem):
    root = etree.fromstring(link_document("share").encode())
    label = root.xpath('.//*[@text="Copy link"]')[0]
    target = label.getparent()
    if problem == "missing":
        target.remove(label)
    elif problem == "duplicate":
        target.append(copy.deepcopy(label))
    elif problem in {"disabled", "hidden"}:
        target.set("enabled" if problem == "disabled" else "visible-to-user", "false")
    elif problem == "nested":
        child = etree.SubElement(target, "node", dict(label.attrib))
        child.set("text", "External app")
        child.set("clickable", "true")
    elif problem == "row":
        target.getparent().getparent().append(target)
    else:
        label.set("package", "other.app")
    assert read_screen(etree.tostring(root), SIZE).kind == "unsupported"


@pytest.mark.parametrize(
    "problem",
    [
        "missing",
        "duplicate",
        "package",
        "hidden",
        "preview_parent",
        "clipped",
        "unknown",
    ],
)
def test_unrecognized_system_overlays_still_block_browsing(problem):
    root = etree.fromstring(link_document("copied").encode())
    receipt = root.xpath('.//*[@resource-id="com.android.systemui:id/clipboard_ui"]')[0]
    preview = receipt.xpath(
        './/*[@resource-id="com.android.systemui:id/text_preview"]'
    )[0]
    if problem == "missing":
        preview.getparent().remove(preview)
    elif problem == "duplicate":
        preview.getparent().append(copy.deepcopy(preview))
    elif problem == "package":
        preview.set("package", PACKAGE)
    elif problem == "hidden":
        preview.set("visible-to-user", "false")
    elif problem == "preview_parent":
        preview.getparent().set("resource-id", "other")
    elif problem == "clipped":
        preview.set("bounds", "[55,2004][800,2224]")
    else:
        receipt.set("resource-id", "com.android.systemui:id/other")
    assert read_screen(etree.tostring(root), SIZE).kind == "unsupported"


def test_empty_system_window_keeps_underlying_occlusion_without_receipt_or_targets():
    root = etree.fromstring(link_document("soak-covered").encode())
    window = next(w for w in root if w.get("bounds") == "[22,1993][608,2257]")
    empty = etree.fromstring(link_document("dismissal-empty").encode())[0]
    root.replace(window, empty)
    screen = read_screen(etree.tostring(root), SIZE)
    assert screen.kind == "unsupported"
    assert screen.clipboard_text is None
    assert not screen.posts and not screen.controls and not screen.scroll_areas
    assert (27, 1938, 608, 2257) in screen.overlaps
    underlying = screen.obscured_screen
    assert underlying.clipboard_text is None
    assert underlying.clipboard_bounds == (27, 1938, 608, 2257)
    source = next(p for p in underlying.posts if p.author == "@BlaireWhite")
    assert not source.observable
    assert source.body_visibility.overlaps == ((27, 1938, 608, 2257),)
    target = next(t.visibility for t in source.targets if t.label == "Open post")
    assert (27, 1938, 608, 2257) in target.overlaps
    from taktik.core.social_media.x.services.browsing.navigation import (
        XError,
        scroll_region,
    )

    with pytest.raises(XError, match="recognized feed viewport"):
        scroll_region(screen)
    _, _, exclusions = scroll_region(underlying)
    assert (27, 1938, 608, 2257) in exclusions


@pytest.mark.parametrize(
    "attribute,value",
    [
        ("text", "Unknown"),
        ("resource-id", "other"),
        ("content-desc", "Unknown"),
        ("class", "android.view.View"),
        ("clickable", "true"),
        ("focusable", "true"),
        ("enabled", "false"),
        ("visible-to-user", "false"),
    ],
)
def test_only_inert_empty_windows_expose_underlying_evidence(attribute, value):
    root = etree.fromstring(link_document("dismissal-empty").encode())
    root[0].set(attribute, value)
    screen = read_screen(etree.tostring(root), SIZE)
    assert screen.kind == "unsupported"
    assert screen.clipboard_text is None
    assert screen.obscured_screen is None


def test_empty_window_alongside_a_receipt_is_ambiguous():
    root = etree.fromstring(link_document("dismissal-receipt").encode())
    root.insert(0, etree.fromstring(link_document("dismissal-empty").encode())[0])
    screen = read_screen(etree.tostring(root), SIZE)
    assert screen.kind == "unsupported"
    assert screen.reason == "Ambiguous clipboard receipts."
    assert screen.obscured_screen is None and screen.clipboard_text is None
