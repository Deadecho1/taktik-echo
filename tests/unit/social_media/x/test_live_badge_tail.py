"""A native clipped LIVE badge can outlast the avatar beside retained body text."""

from pathlib import Path

import pytest
from lxml import etree
from unit.x_fixtures import xml_fixture

from taktik.core.social_media.x.services.browsing.navigation import _alignment
from taktik.core.social_media.x.ui.screen import read_screen


def document(name):
    return xml_fixture(Path(__file__).parent / "fixtures" / f"{name}.xml")


def screen(stage):
    return read_screen(document(f"live-badge-tail-{stage}"), (1080, 2340))


def test_live_tail_is_retained_without_inventing_an_author_or_body_label():
    before, after = screen("before"), screen("after")
    p = after.fragments[0]
    assert p.body == before.posts[0].body
    assert not hasattr(p, "author")
    assert _alignment(before, after, scrolling=True) == (1, True)


@pytest.mark.parametrize(
    "mutation",
    [
        "text",
        "control",
        "wrapper_control",
        "nested",
        "outside",
        "unclipped",
        "different_wrappers",
        "overlap_body",
        "no_body",
    ],
)
def test_live_tail_requires_native_wrappers_left_of_a_clipped_body(mutation):
    root = etree.fromstring(document("live-badge-tail-after").encode())
    label = root.xpath('//*[@text="LIVE"]')[0]
    inner, badge = label.getparent(), label.getparent().getparent()
    if mutation == "text":
        label.set("text", "Unknown badge")
    elif mutation == "control":
        label.set("clickable", "true")
    elif mutation == "wrapper_control":
        badge.set("clickable", "true")
    elif mutation == "nested":
        label.append(etree.fromstring(etree.tostring(label)))
    elif mutation == "outside":
        label.set("bounds", "[59,180][117,213]")
    elif mutation in {"unclipped", "overlap_body"}:
        rect = "[22,136][154,268]" if mutation == "unclipped" else "[100,59][232,191]"
        badge.set("bounds", rect)
        inner.set("bounds", rect)
        label.set(
            "bounds",
            "[59,185][117,218]" if mutation == "unclipped" else "[137,108][195,141]",
        )
    elif mutation == "different_wrappers":
        inner.set("bounds", "[22,60][154,192]")
    else:
        badge.getparent().remove(badge.getnext())
    assert read_screen(etree.tostring(root), (1080, 2340)).rejected_posts
