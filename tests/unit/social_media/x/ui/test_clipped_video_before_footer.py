"""Retained video and GIF captions can continue below the viewport before its actions enter."""

from copy import deepcopy

import pytest
from lxml import etree
from unit.paths import CORE
from unit.x_fixtures import xml_fixture

from taktik.core.social_media.x.ui.screen import read_screen


def document(name):
    return xml_fixture(CORE / "tests/unit/social_media/x/fixtures" / f"{name}.xml")


def screen(stage="after"):
    return read_screen(document(f"clipped-video-before-footer-{stage}"), (1080, 2340))


@pytest.mark.parametrize("stage", ["after", "expanded"])
def test_clipped_body_and_video_survive_before_the_footer_enters(stage):
    s = screen(stage)
    assert not s.rejected_posts and len(s.fragments) == 1
    p = s.fragments[0]
    assert p.body and p.media[0].kind == "video"
    assert p.quoted_post is None and not p.actions
    assert p.media[0].visibility.bounds[3] >= s.content_viewport[3]
    assert not s.observable_posts


@pytest.mark.parametrize(
    "mutation",
    [
        "visible_empty_card",
        "unknown_control",
        "empty_card_children",
        "video_ends_early",
        "missing_video",
    ],
)
def test_footerless_fragment_requires_continuing_native_media(mutation):
    root = etree.fromstring(document("clipped-video-before-footer-after").encode())
    container = root.xpath(
        '//*[@scrollable="true"]/*[@scrollable="true"]/*[@clickable="true"]'
    )[0]
    card = container[-1]
    if mutation == "visible_empty_card":
        card.set("bounds", "[176,2100][1047,2340]")
    elif mutation == "unknown_control":
        card.set("content-desc", "Unknown control")
    elif mutation == "empty_card_children":
        etree.SubElement(card, "node", attrib=dict(card.attrib))
    elif mutation == "video_ends_early":
        for n in container.iter():
            if n.get("bounds") == "[176,989][1047,2296]":
                n.set("bounds", "[176,989][1047,2100]")
    else:
        container.remove(container[1])
    assert read_screen(etree.tostring(root), (1080, 2340)).rejected_posts


@pytest.mark.parametrize(
    "mutation", ["unknown_prefix", "translation", "translation_overlap"]
)
def test_expanded_toolbar_preserves_existing_prefix_and_translation_validation(
    mutation,
):
    root = etree.fromstring(document("clipped-video-before-footer-expanded").encode())
    container = root.xpath(
        '//*[@scrollable="true"]/*[@scrollable="true"]/*[@clickable="true"]'
    )[0]
    if mutation == "unknown_prefix":
        container[0].set("class", "android.view.View")
    elif mutation == "translation":
        container[1].set("text", "Unknown context")
    else:
        container[2].set("bounds", "[618,58][849,200]")
    assert read_screen(etree.tostring(root), (1080, 2340)).rejected_posts


FIXTURE = CORE / "tests/unit/social_media/x/fixtures/coverage/caption-gif-244.xml"


def test_visible_native_gif_renderer_retains_only_unattributed_content():
    screen = read_screen(
        xml_fixture(FIXTURE.with_name("caption-gif-visible.xml")), (1080, 2340)
    )
    assert not screen.posts and not screen.rejected_posts
    (fragment,) = screen.fragments
    assert fragment.body_visibility.bounds[3] == 1644
    assert fragment.media[0].visibility.visible_bounds == (176, 1666, 1047, 2230)
    assert not fragment.actions


@pytest.mark.parametrize("index", range(6))
@pytest.mark.parametrize(
    "mutation", ["text", "description", "interactive", "bounds", "class", "child"]
)
def test_visible_renderer_rejects_unknown_descendants(index, mutation):
    root = etree.fromstring(
        xml_fixture(FIXTURE.with_name("caption-gif-visible.xml")).encode()
    )
    glyph = root.xpath('//*[@content-desc="GIF"]')[0]
    renderer = glyph.getnext()
    node = list(renderer.iter())[index]
    if mutation == "child":
        node.append(deepcopy(glyph))
    else:
        attr, value = {
            "text": ("text", "Unknown"),
            "description": ("content-desc", "Unknown"),
            "interactive": ("clickable", "true"),
            "bounds": ("bounds", "[176,1667][1047,2340]"),
            "class": ("class", "android.widget.ImageView"),
        }[mutation]
        node.set(attr, value)
    screen = read_screen(etree.tostring(root), (1080, 2340))
    assert not screen.posts and not screen.fragments
    assert screen.rejected_posts


@pytest.mark.parametrize(
    "mutation",
    [
        "unknown_child",
        "empty_child",
        "nested_child",
        "second_gif",
        "image",
        "video",
        "description",
        "wrapper_text",
        "interactive_glyph",
        "interactive_picture",
        "interactive_body",
        "inaccessible_body",
        "body_annotation",
        "reordered",
        "width",
        "overlap",
        "unclipped_footer",
        "glyph_geometry",
        "picture_geometry",
        "wrapper_geometry",
        "container_description",
        "container_text",
        "container_class",
        "container_scrollable",
        "container_long_clickable",
    ],
)
def test_incomplete_gif_footer_requires_exact_structure_and_geometry(mutation):
    root = etree.fromstring(xml_fixture(FIXTURE).encode())
    glyph = root.xpath('//*[@content-desc="GIF"]')[0]
    wrapper = glyph.getparent()
    container = wrapper.getparent()
    body, picture = container[0], wrapper[1]
    if mutation.startswith("container_"):
        attr, value = {
            "container_description": ("content-desc", "Unknown action"),
            "container_text": ("text", "Unknown"),
            "container_class": ("class", "android.widget.Button"),
            "container_scrollable": ("scrollable", "true"),
            "container_long_clickable": ("long-clickable", "true"),
        }[mutation]
        container.set(attr, value)
    elif mutation in {"unknown_child", "empty_child", "nested_child", "second_gif"}:
        extra = deepcopy(picture)
        extra.set(
            "content-desc",
            {"unknown_child": "Unknown", "second_gif": "GIF"}.get(mutation, ""),
        )
        (picture if mutation == "nested_child" else container).append(extra)
    elif mutation in {"image", "video", "description"}:
        glyph.set(
            "content-desc",
            {"image": "Image", "video": "Video", "description": "GIF: changed"}[
                mutation
            ],
        )
    elif mutation == "wrapper_text":
        wrapper.set("text", "Unknown")
    elif mutation.startswith("interactive_"):
        {"glyph": glyph, "picture": picture, "body": body}[
            mutation.removeprefix("interactive_")
        ].set("clickable", "true")
    elif mutation == "inaccessible_body":
        body.set("visible-to-user", "false")
    elif mutation == "body_annotation":
        body.append(deepcopy(picture))
    elif mutation == "reordered":
        container.insert(0, wrapper)
    elif mutation == "width":
        body.set("bounds", "[177,0][1047,2246]")
    elif mutation == "overlap":
        body.set("bounds", "[176,0][1047,2300]")
    elif mutation == "unclipped_footer":
        for node in wrapper.iter():
            node.set("bounds", "[176,2268][1047,2339]")
    else:
        {
            "glyph_geometry": glyph,
            "picture_geometry": picture,
            "wrapper_geometry": wrapper,
        }[mutation].set("bounds", "[177,2268][1047,2340]")
    screen = read_screen(etree.tostring(root), (1080, 2340))
    assert not screen.posts and not screen.fragments
    assert screen.rejected_posts
