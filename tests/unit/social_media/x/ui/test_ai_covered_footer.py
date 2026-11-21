"""AI labels use the same covered-bookmark proof as the native action row."""

import pytest
from lxml import etree
from unit.paths import CORE

from taktik.core.social_media.x.services.browsing.navigation import _alignment
from taktik.core.social_media.x.ui.screen import _post, _Unsupported, read_screen


def document(name):
    return (CORE / "tests/unit/social_media/x/fixtures" / f"{name}.xml").read_text()


def screen(stage):
    return read_screen(document(f"ai-covered-footer-{stage}"), (1080, 2340))


def test_ai_label_retains_only_known_actions_when_bookmark_is_covered():
    p = screen("after").posts[0]
    assert p.media_labels == ("Made with AI",)
    assert p.body == screen("before").posts[0].body
    assert [t.label for t in p.actions] == [
        "Reply",
        "Repost",
        "Like",
        "Impressions",
        "Share",
    ]


def test_captured_label_entry_retains_alignment():
    assert _alignment(screen("before"), screen("after"), scrolling=True) == (0, True)


@pytest.mark.parametrize(
    "mutation", ["no_cover", "partial_cover", "label", "slot_text", "row"]
)
def test_ai_footer_still_requires_exact_label_and_complete_glyph_coverage(mutation):
    root = etree.fromstring(document("ai-covered-footer-after").encode())
    icon = root.xpath('//*[@content-desc="Made with AI"]')[0]
    container = icon.getparent()
    header = container[1]
    covers = ((882, 2076, 1036, 2230),)
    if mutation == "no_cover":
        covers = ()
    elif mutation == "partial_cover":
        covers = ((930, 2076, 1036, 2230),)
    elif mutation == "label":
        icon.getnext().set("text", "Changed")
    elif mutation == "slot_text":
        container[-2].set("text", "Unknown control")
    else:
        container[-2].set("bounds", "[872,2030][959,2150]")
    with pytest.raises(_Unsupported):
        _post(header, (0, 136, 1080, 2230), covers)
