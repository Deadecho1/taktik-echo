"""A composer-covered empty footer slot does not erase retained post content."""

from dataclasses import replace
from pathlib import Path

import pytest
from lxml import etree
from taktik.core.social_media.x.services.browsing.navigation import XError, _alignment
from taktik.core.social_media.x.ui.screen import _fragment, _Unsupported, read_screen


def document(name):
    return (Path(__file__).parent / "fixtures" / f"{name}.xml").read_text()


def test_covered_bookmark_preserves_only_the_five_known_actions():
    before, after = (
        read_screen(document(f"covered-bookmark-{s}"), (1080, 2340))
        for s in ("before", "after")
    )
    assert not after.rejected_posts
    assert _alignment(before, after, scrolling=True) == (1, True)
    p = after.fragments[0]
    assert [a.label for a in p.actions] == [
        "Reply",
        "Repost",
        "Like",
        "Impressions",
        "Share",
    ]
    assert not hasattr(p, "author")
    assert not after.observable_posts


@pytest.mark.parametrize(
    "mutation",
    ["cover", "right_cover", "slot_geometry", "slot_text", "extra_slot", "row", "icon"],
)
def test_missing_bookmark_requires_exact_row_and_complete_icon_coverage(mutation):
    root = etree.fromstring(document("covered-bookmark-after").encode())
    slot = root.xpath('//*[@bounds="[872,2122][959,2240]"]')[0]
    if mutation in {"cover", "right_cover"}:
        cover = (
            (920, 2076, 1036, 2230) if mutation == "cover" else (882, 2076, 940, 2230)
        )
        with pytest.raises(_Unsupported):
            _fragment(
                slot.getparent(),
                (0, 136, 1080, 2230),
                (cover,),
                collapsed=True,
            )
        return
    elif mutation == "slot_geometry":
        slot.set("bounds", "[850,2122][959,2240]")
    elif mutation == "slot_text":
        slot.set("text", "Unknown control")
    elif mutation == "extra_slot":
        slot.getparent().remove(slot)
    elif mutation == "row":
        share = slot.getnext()
        share.set("bounds", "[959,2102][1080,2240]")
    else:
        icon = root.xpath('//*[@content-desc="Reply"]')[0]
        icon.set("bounds", "[176,2146][220,2190]")
    after = read_screen(etree.tostring(root), (1080, 2340))
    assert after.rejected_posts
    assert not after.fragments


def test_covered_footer_does_not_bypass_changed_quoted_text():
    before, after = (
        read_screen(document(f"covered-bookmark-{s}"), (1080, 2340))
        for s in ("before", "after")
    )
    p = after.fragments[0]
    p = replace(p, quoted_post=replace(p.quoted_post, author="@changed"))
    with pytest.raises(XError):
        _alignment(before, replace(after, fragments=(p,)), scrolling=True)
