from dataclasses import replace
from pathlib import Path

import pytest
from lxml import etree
from unit.x_fixtures import xml_fixture

from taktik.core.social_media.x.services.browsing.navigation import XError, _alignment
from taktik.core.social_media.x.ui.screen import read_screen

FIXTURES = Path(__file__).with_name("fixtures")


def screens(prefix):
    return tuple(
        read_screen(xml_fixture(FIXTURES / f"{prefix}-{stage}.xml"), (1080, 2340))
        for stage in ("before", "after")
    )


@pytest.mark.parametrize(
    "prefix,offset", [("covered-badge", 2), ("video-revelation", 1)]
)
def test_neighbor_content_establishes_independent_ordered_movement(prefix, offset):
    before, after = screens(prefix)
    assert _alignment(before, after, scrolling=True) == (offset, True)


def test_action_only_footer_never_establishes_its_own_forward_identity():
    before, after = screens("covered-badge")
    before = replace(before, posts=before.posts[:1])
    after = replace(after, fragments=after.fragments[:1], posts=())
    with pytest.raises(XError):
        _alignment(before, after, scrolling=True)


@pytest.mark.parametrize(
    "mutation", ["badge", "badge_text", "badge_control", "handle", "cover"]
)
def test_covered_badge_does_not_allow_unknown_header_content(mutation):
    root = etree.fromstring(xml_fixture(FIXTURES / "covered-badge-after.xml").encode())
    header = root.xpath('//*[@resource-id="timeline_post"]')[0]
    if mutation == "badge":
        header[1].set("content-desc", "Unknown")
    elif mutation == "badge_text":
        header[1].set("text", "unexpected")
    elif mutation == "badge_control":
        header[1].set("clickable", "true")
    elif mutation == "handle":
        header[0].set("text", "@partial...")
    else:
        cover = root.xpath('//*[@resource-id="ntp"]')[0]
        cover.getparent().remove(cover)
    screen = read_screen(etree.tostring(root), (1080, 2340))
    assert not any(fragment.body for fragment in screen.fragments)
    assert screen.rejected_posts
