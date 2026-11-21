"""A native video footer is separate from author/body and advertising labels."""

from pathlib import Path

import pytest
from lxml import etree

from taktik.core.social_media.x.services.browsing.navigation import _alignment
from taktik.core.social_media.x.ui.screen import read_screen

FIXTURES = Path(__file__).with_name("fixtures")


def document(name):
    return (FIXTURES / f"{name}.xml").read_text()


def test_made_on_x_video_footer_preserves_the_captured_forward_transition():
    before, after = [
        read_screen(document(f"made-on-x-{s}"), (1080, 2340))
        for s in ("before", "after")
    ]
    post = next(p for p in after.posts if p.author == "@fixture_4")
    assert post.media_labels == ("Made on X",)
    assert post.advertising == "unknown"
    assert "Made on X" not in post.body
    assert _alignment(before, after, scrolling=True) == (1, True)


@pytest.mark.parametrize(
    "mutation",
    [
        "label",
        "text",
        "class",
        "not_clickable",
        "nested",
        "above_video",
        "outside",
        "footer_gap",
    ],
)
def test_made_on_x_rejects_unknown_controls_or_unrelated_geometry(mutation):
    root = etree.fromstring(document("made-on-x-after").encode())
    (label,) = root.xpath('//*[@text="Made on X"]')
    if mutation == "label":
        label.set("text", "Made elsewhere")
    elif mutation == "text":
        label.set("content-desc", "Unexpected")
    elif mutation == "class":
        label.set("class", "android.widget.TextView")
    elif mutation == "not_clickable":
        label.set("clickable", "false")
    elif mutation == "nested":
        etree.SubElement(label, "node", text="Unexpected")
    elif mutation == "above_video":
        label.set("bounds", "[176,400][366,473]")
    elif mutation == "outside":
        label.set("bounds", "[0,2078][366,2151]")
    else:
        label.set("bounds", "[176,2078][366,2141]")
    screen = read_screen(etree.tostring(root), (1080, 2340))
    assert not any(p.author == "@fixture_4" for p in screen.posts)
