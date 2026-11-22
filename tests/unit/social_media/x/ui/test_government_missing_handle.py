"""Known badges do not supply a missing author or hide usable content anchors."""

import pytest
from lxml import etree
from unit.paths import CORE
from unit.x_fixtures import xml_fixture

from taktik.core.social_media.x.services.browsing.navigation import _alignment
from taktik.core.social_media.x.ui.screen import read_screen


def document(name):
    return xml_fixture((CORE / "tests/unit/social_media/x/fixtures") / f"{name}.xml")


def screen(stage="after"):
    return read_screen(document(f"government-missing-handle-{stage}"), (1080, 2340))


def test_government_badge_keeps_body_and_video_unattributed():
    s = screen()
    assert not s.rejected_posts
    assert len(s.fragments) == 2
    fragment = s.fragments[-1]
    assert not hasattr(fragment, "author")
    assert fragment.body and fragment.media[0].kind == "video"
    assert not s.observable_posts


def test_captured_preceding_movements_preserve_continuity():
    assert _alignment(screen("before"), screen("first"), scrolling=True)[1]
    assert _alignment(screen("first"), screen(), scrolling=True)[1]


@pytest.mark.parametrize(
    "badge", ["Verified", "Verified Business", "Verified Governmental Account"]
)
def test_known_badges_share_the_same_missing_handle_rules(badge):
    root = etree.fromstring(document("government-missing-handle-after").encode())
    root.xpath('//*[@resource-id="timeline_post"]')[0][1].set("content-desc", badge)
    s = read_screen(etree.tostring(root), (1080, 2340))
    assert not s.rejected_posts and len(s.fragments) == 2
    assert not s.observable_posts


@pytest.mark.parametrize(
    "mutation", ["unknown", "interactive", "disabled", "name", "overlap", "height"]
)
def test_missing_handle_still_requires_plain_native_geometry(mutation):
    root = etree.fromstring(document("government-missing-handle-after").encode())
    name, badge, age = root.xpath('//*[@resource-id="timeline_post"]')[0]
    if mutation == "unknown":
        badge.set("content-desc", "Unknown")
    elif mutation == "interactive":
        badge.set("clickable", "true")
    elif mutation == "disabled":
        badge.set("enabled", "false")
    elif mutation == "name":
        name.set("text", "@partial...")
    elif mutation == "overlap":
        badge.set("bounds", "[730,451][795,492]")
    else:
        age.set("bounds", "[813,430][879,496]")
    s = read_screen(etree.tostring(root), (1080, 2340))
    assert s.rejected_posts and len(s.fragments) == 1
