"""A retained video can continue below the viewport before its actions enter."""

from pathlib import Path

import pytest
from lxml import etree
from taktik.core.social_media.x.ui.screen import read_screen


def document(name):
    return (Path(__file__).parent / "fixtures" / f"{name}.xml").read_text()


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
