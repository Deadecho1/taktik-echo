"""Native media footer labels remain separate from body and author attribution."""

from copy import deepcopy

import pytest
from lxml import etree
from unit.paths import CORE
from unit.x_fixtures import SIZE, xml_fixture
from unit.x_fixtures import xml_fixture as document

from taktik.core.shared.ui.geometry import bounds
from taktik.core.social_media.x.services.browsing.browser import post_context
from taktik.core.social_media.x.services.browsing.navigation import _alignment
from taktik.core.social_media.x.ui.screen import read_screen


def screen(stage):
    return read_screen(document(f"ai-label-footer-{stage}"), (1080, 2340))


def test_ai_label_without_creation_button_remains_separate_context():
    post = screen("after").posts[0]
    assert post.media_labels == ("Made with AI",)
    assert "Made with AI" not in post.body
    assert post.advertising == "unknown"


def test_captured_ai_label_entry_keeps_continuity():
    assert _alignment(screen("before"), screen("after"), scrolling=True) == (0, True)


@pytest.mark.parametrize(
    "mutation",
    [
        "text",
        "icon",
        "overlap_video",
        "footer_gap",
        "label_control",
        "icon_control",
        "extra_control",
        "label_children",
    ],
)
def test_ai_annotation_without_button_requires_exact_native_pair_and_footer(mutation):
    root = etree.fromstring(document("ai-label-footer-after").encode())
    icon = root.xpath('//*[@content-desc="Made with AI"]')[0]
    label = icon.getnext()
    if mutation == "text":
        label.set("text", "Unknown label")
    elif mutation == "icon":
        icon.set("content-desc", "Unknown icon")
    elif mutation == "overlap_video":
        icon.set("bounds", "[176,2098][215,2148]")
    elif mutation == "footer_gap":
        icon.set("bounds", "[176,2121][215,2140]")
        label.set("bounds", "[226,2119][436,2140]")
    elif mutation in {"label_control", "icon_control"}:
        (label if mutation == "label_control" else icon).set("clickable", "true")
    elif mutation == "extra_control":
        extra = etree.fromstring(etree.tostring(icon))
        extra.set("content-desc", "Unknown action")
        label.addnext(extra)
    else:
        label.append(etree.fromstring(etree.tostring(icon)))
    assert not read_screen(etree.tostring(root), (1080, 2340)).posts


FIXTURES = CORE / "tests/unit/social_media/x/fixtures/coverage"


def tree(name="single"):
    return etree.ElementTree(
        etree.fromstring(xml_fixture(FIXTURES / f"media-tag-{name}.xml").encode())
    )


@pytest.mark.parametrize(
    "name,author,label",
    [
        ("single", "@NASASolarSystem", "NASA JPL"),
        ("current", "@NASASolarSystem", "NASA JPL"),
        ("plural", "@NASA_Events", "Air Dot Show Tour and 3 others"),
    ],
)
def test_captured_tags_do_not_supply_authorship_or_caption(name, author, label):
    screen = read_screen(etree.tostring(tree(name)), SIZE)
    post = next(p for p in screen.observable_posts if p.author == author)
    assert post.media_tags == (label,)
    assert label not in post.body
    assert post.reposted_by == (None if name == "current" else "NASA reposted")
    assert post.advertising == "unknown"


@pytest.mark.parametrize(
    "mutation",
    [
        "before_media",
        "duplicate",
        "nested",
        "description",
        "disabled",
        "hidden",
        "long_clickable",
        "scrollable",
        "not_focusable",
        "outside_container",
        "above_media",
        "below_footer",
        "footer_gap",
        "missing_media",
        "missing_footer",
    ],
)
def test_unverified_tag_structure_cannot_supply_a_post(mutation):
    root = tree()
    tag = root.xpath('//*[@text="NASA JPL"]')[0]
    parent = tag.getparent()
    media = tag.getprevious()
    if mutation == "before_media":
        parent.insert(parent.index(media), tag)
    elif mutation == "duplicate":
        parent.insert(parent.index(tag), deepcopy(tag))
    elif mutation == "nested":
        tag.append(deepcopy(tag))
    elif mutation == "description":
        tag.set("content-desc", "Unrecognized annotation")
    elif mutation in {"disabled", "hidden", "not_focusable"}:
        tag.set(
            {
                "disabled": "enabled",
                "hidden": "visible-to-user",
                "not_focusable": "focusable",
            }[mutation],
            "false",
        )
    elif mutation in {"long_clickable", "scrollable"}:
        tag.set(mutation.replace("_", "-"), "true")
    elif mutation in {"outside_container", "above_media", "below_footer", "footer_gap"}:
        tag.set(
            "bounds",
            {
                "outside_container": "[176,1358][1100,1431]",
                "above_media": "[176,800][335,1431]",
                "below_footer": "[176,1431][335,1504]",
                "footer_gap": "[176,1358][335,1430]",
            }[mutation],
        )
    elif mutation == "missing_media":
        parent.remove(media)
    elif mutation == "missing_footer":
        parent.remove(tag.getnext())

    screen = read_screen(etree.tostring(root), SIZE)
    assert not any(p.author == "@NASASolarSystem" for p in screen.posts)
    assert any(r.bounds == (0, 444, 1080, 1549) for r in screen.rejected_posts)


def test_captured_tagged_post_scroll_preserves_native_order():
    before, after = [
        read_screen(etree.tostring(tree(name)), SIZE)
        for name in ("before-scroll", "after-scroll")
    ]
    assert before.posts[0].media_tags == ("NASA JPL",)
    assert _alignment(before, after, scrolling=True) == (1, True)


def test_clipped_tag_is_not_exposed_as_observed_context():
    root = tree("current")
    tag = root.xpath('//*[@text="NASA JPL"]')[0]
    container = tag.getparent()
    for sibling in list(container.getparent()):
        if sibling is not container:
            container.getparent().remove(sibling)
    for node in container.iter():
        left, top, right, bottom = bounds(node)
        node.set(
            "bounds",
            f"[{left},{min(top + 900, 2340)}][{right},{min(bottom + 900, 2340)}]",
        )

    screen = read_screen(etree.tostring(root), SIZE)
    (post,) = screen.observable_posts

    assert post.author == "@NASASolarSystem"
    assert post.media_tags == ()
    assert post_context(post)["media_tags"] == []
