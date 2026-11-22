"""Known badges do not supply a missing author or hide usable content anchors."""

import pytest
from lxml import etree
from unit.paths import CORE
from unit.x_fixtures import xml_fixture

from taktik.core.social_media.x.services.browsing.navigation import _alignment
from taktik.core.social_media.x.ui.screen import read_screen


def document(name):
    return xml_fixture(CORE / "tests/unit/social_media/x/fixtures" / f"{name}.xml")


def screen(stage="after"):
    return read_screen(document(f"missing-handle-short-age-{stage}"), (1080, 2340))


def test_shorter_age_keeps_body_and_video_unattributed():
    s = screen()
    assert not s.rejected_posts
    assert len(s.fragments) == 2
    fragment = s.fragments[-1]
    assert not hasattr(fragment, "author")
    assert fragment.body and not fragment.media
    quote = fragment.quoted_post
    assert quote.author is None
    assert quote.media[0].kind == "video"
    assert quote.translation == "Translated from Japanese"
    assert not quote.body_complete and not quote.observable
    assert not s.observable_posts


def test_captured_preceding_movements_preserve_continuity():
    assert _alignment(screen("before"), screen("first"), scrolling=True)[1]
    assert _alignment(screen("first"), screen(), scrolling=True)[1]


@pytest.mark.parametrize(
    "badge", ["Verified", "Verified Business", "Verified Governmental Account"]
)
def test_known_badges_share_the_same_missing_handle_rules(badge):
    root = etree.fromstring(document("missing-handle-short-age-after").encode())
    root.xpath('//*[@resource-id="timeline_post"]')[0][1].set("content-desc", badge)
    s = read_screen(etree.tostring(root), (1080, 2340))
    assert not s.rejected_posts and len(s.fragments) == 2
    assert not s.observable_posts


@pytest.mark.parametrize(
    "mutation", ["unknown", "interactive", "disabled", "name", "overlap", "height"]
)
def test_missing_handle_still_requires_plain_native_geometry(mutation):
    root = etree.fromstring(document("missing-handle-short-age-after").encode())
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
        badge.set("bounds", "[720,397][779,418]")
    else:
        age.set("bounds", "[797,370][879,418]")
    s = read_screen(etree.tostring(root), (1080, 2340))
    assert s.rejected_posts and len(s.fragments) == 1


@pytest.mark.parametrize(
    "mutation",
    [
        "translation",
        "translation_control",
        "translation_overlap",
        "date_height",
        "date_edge",
    ],
)
def test_unattributed_quote_retains_translation_and_native_geometry_guards(mutation):
    root = etree.fromstring(document("missing-handle-short-age-after").encode())
    card = root.xpath('//*[@content-desc="Quote"]')[0].getparent()
    age, label = card[3:5]
    if mutation == "translation":
        label.set("text", "Unknown annotation")
    elif mutation == "translation_control":
        label.set("clickable", "true")
    elif mutation == "translation_overlap":
        label.set("bounds", "[261,1049][675,1112]")
    elif mutation == "date_height":
        age.set("bounds", "[810,990][1019,1055]")
    else:
        age.set("bounds", "[810,1006][1030,1055]")
    assert read_screen(etree.tostring(root), (1080, 2340)).rejected_posts
