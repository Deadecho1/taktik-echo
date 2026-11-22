"""Offscreen native action slots can precede their missing glyphs."""

import pytest
from lxml import etree
from unit.paths import CORE

from taktik.core.social_media.x.ui.screen import read_screen


def document(name):
    return (CORE / "tests/unit/social_media/x/fixtures" / f"{name}.xml").read_text()


def screen(xml=None):
    return read_screen(xml or document("blank-footer-slots-before"), (1080, 2340))


def test_hidden_slots_retain_unattributed_text_and_video_without_actions():
    s = screen()
    assert len(s.fragments) == 1
    assert s.scroll_areas
    p = s.fragments[0]
    assert not hasattr(p, "author")
    assert p.body_visibility.clipped
    assert p.media[0].kind == "video"
    assert p.actions == ()
    assert not s.observable_posts


@pytest.mark.parametrize(
    "mutation",
    ["count", "visible", "gap", "label", "interactive", "nested", "media_padding"],
)
def test_blank_slots_require_exact_offscreen_native_structure(mutation):
    root = etree.fromstring(document("blank-footer-slots-before").encode())
    body = root.xpath(
        '//*[@scrollable="true"]/node[@clickable="true"]/node[@class="android.widget.TextView"]'
    )[0]
    container, wrapper = body.getparent(), body.getnext()
    slot = container[-1]
    if mutation == "count":
        container.remove(slot)
    elif mutation == "visible":
        slot.set("bounds", "[959,2220][1080,2340]")
    elif mutation == "gap":
        slot.set("bounds", "[960,2298][1080,2340]")
    elif mutation == "label":
        slot.set("content-desc", "Unexpected")
    elif mutation == "interactive":
        slot.set("scrollable", "true")
    elif mutation == "nested":
        etree.SubElement(slot, "node", dict(slot.attrib))
    else:
        wrapper.set("bounds", "[176,1005][1047,2297]")
    assert not screen(etree.tostring(root)).scroll_areas
