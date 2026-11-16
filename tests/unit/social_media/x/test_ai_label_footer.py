"""The native AI label may meet the action row without a Grok creation button."""

from pathlib import Path

import pytest
from lxml import etree
from taktik.core.social_media.x.services.browsing.navigation import _alignment
from taktik.core.social_media.x.ui.screen import read_screen


def document(name):
    return (Path(__file__).parent / "fixtures" / f"{name}.xml").read_text()


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
