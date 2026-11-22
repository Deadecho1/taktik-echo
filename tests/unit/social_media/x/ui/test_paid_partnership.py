"""Synthetic text on captured geometry; no phone, model, or operator data."""

from copy import deepcopy

import pytest
from lxml import etree
from unit.paths import CORE
from unit.x_fixtures import xml_fixture

from taktik.core.shared.ui.geometry import bounds
from taktik.core.social_media.x.services.browsing.navigation import XError, _alignment
from taktik.core.social_media.x.ui.screen import read_screen

FIXTURES = CORE / "tests/unit/social_media/x/fixtures"
SIZE = (1080, 2340)


def tree(name="partnership-probe-after"):
    return etree.ElementTree(
        etree.fromstring(xml_fixture(FIXTURES / f"{name}.xml").encode())
    )


@pytest.mark.parametrize("name", ["partnership-probe-after", "partnership-fragment"])
def test_native_disclosure_is_separate_from_body_and_authorship(name):
    screen = read_screen(etree.tostring(tree(name)), SIZE)

    assert not screen.rejected_posts
    (post,) = (*screen.posts, *screen.fragments)
    assert post.body == "Fixture commentary\u00a0Show more"
    assert post.advertising == "paid_partnership"
    assert post.advertising_visibility.unobscured
    assert post.body_annotations == ()
    if screen.fragments:
        assert not hasattr(post, "author")
    else:
        assert post.author == "@fixture_owner"
        assert post.labels == ("Verified",)
        assert not post.body_complete


@pytest.mark.parametrize("name", ["partnership-probe-after", "partnership-fragment"])
@pytest.mark.parametrize(
    "mutation",
    [
        "missing_icon",
        "missing_label",
        "duplicate_icon",
        "duplicate_label",
        "nested_label",
        "label_text",
        "icon_description",
        "icon_text",
        "label_description",
        "icon_class",
        "label_class",
        "clickable",
        "long-clickable",
        "focusable",
        "scrollable",
        "disabled",
        "hidden",
        "reversed",
        "overlap",
        "disjoint",
        "media_overlap",
        "footer_gap",
        "outside_container",
        "unrecognized_media",
        "missing_footer",
        "extra_body",
    ],
)
def test_malformed_disclosure_does_not_get_ignored_as_decoration(name, mutation):
    root = tree(name)
    icon = root.xpath('//*[@content-desc="Paid partnership"]')[0]
    label = icon.getnext()
    parent = icon.getparent()
    if mutation.startswith("missing_") and mutation != "missing_footer":
        parent.remove(icon if mutation == "missing_icon" else label)
    elif mutation.startswith("duplicate_"):
        parent.insert(
            parent.index(icon),
            deepcopy(icon if mutation == "duplicate_icon" else label),
        )
    elif mutation == "nested_label":
        label.append(deepcopy(label))
    elif mutation == "label_text":
        label.set("text", "Sponsored")
    elif mutation == "icon_description":
        icon.set("content-desc", "Sponsored")
    elif mutation == "icon_text":
        icon.set("text", "Another message")
    elif mutation == "label_description":
        label.set("content-desc", "Another message")
    elif mutation.endswith("_class"):
        (icon if mutation == "icon_class" else label).set(
            "class", "android.widget.Button"
        )
    elif mutation in {"clickable", "long-clickable", "focusable", "scrollable"}:
        icon.set(mutation, "true")
    elif mutation in {"disabled", "hidden"}:
        icon.set("enabled" if mutation == "disabled" else "visible-to-user", "false")
    elif mutation == "reversed":
        parent.insert(parent.index(icon), label)
    elif mutation in {
        "overlap",
        "disjoint",
        "media_overlap",
        "footer_gap",
        "outside_container",
    }:
        x1, y1, x2, y2 = bounds(label)
        values = {
            "overlap": (200, y1, x2, y2),
            "disjoint": (x1, y1 - 35, x2, y2 - 35),
            "media_overlap": (x1, y1 - 30, x2, y2),
            "footer_gap": (x1, y1, x2, y2 - 1),
            "outside_container": (x1, y1, 1100, y2),
        }[mutation]
        label.set("bounds", f"[{values[0]},{values[1]}][{values[2]},{values[3]}]")
    elif mutation == "unrecognized_media":
        parent.xpath('.//*[@content-desc="Video"]')[0].set("content-desc", "Image")
    elif mutation == "missing_footer":
        parent.remove(label.getnext())
    elif mutation == "extra_body":
        body = parent.xpath('./node[starts-with(@text,"Fixture commentary")]')[0]
        parent.insert(parent.index(body), deepcopy(body))

    screen = read_screen(etree.tostring(root), SIZE)

    assert screen.rejected_posts
    assert not screen.posts and not screen.fragments


def test_header_loss_tolerance_does_not_accept_a_body_far_below_the_viewport():
    root = tree("partnership-fragment")
    body = root.xpath('//*[starts-with(@text,"Fixture commentary")]')[0]
    body.set("bounds", "[176,139][1047,578]")

    screen = read_screen(etree.tostring(root), SIZE)

    assert not screen.fragments
    assert "clipped post body" in screen.rejected_posts[0].reason


@pytest.mark.parametrize(
    "name,offset", [("partnership-probe-after", 0), ("partnership-fragment", 1)]
)
def test_disclosure_revelation_uses_existing_body_and_video_movement(name, offset):
    before = read_screen(etree.tostring(tree("partnership-before")), SIZE)
    after = read_screen(etree.tostring(tree(name)), SIZE)

    assert _alignment(before, after, scrolling=True) == (offset, True)
    with pytest.raises(XError, match="outside adapter scrolling"):
        _alignment(before, after)
