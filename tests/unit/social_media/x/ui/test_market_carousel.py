"""A native market carousel retains full first-card data and clipped asset labels."""

from dataclasses import replace

import pytest
from lxml import etree
from unit.x_fixtures import xml_fixture as document

from taktik.core.social_media.x.services.browsing.browser import post_context
from taktik.core.social_media.x.services.browsing.navigation import XError, _alignment
from taktik.core.social_media.x.ui.screen import read_screen


def screen(stage="after"):
    return read_screen(document(f"market-carousel-{stage}"), (1080, 2340))


def test_market_carousel_preserves_visible_asset_values_and_partial_neighbor():
    s = screen()
    assert not s.rejected_posts
    p = s.posts[0]
    card = p.market_card
    assert (card.name, card.symbol, card.price, card.change) == (
        "Bitcoin",
        "BTC",
        "$65,011.00",
        "+0.18%",
    )
    assert [v.text for v in card.adjacent_assets] == ["Fixture text 5"]
    assert card.adjacent_assets[0].visibility.clipped
    assert (
        post_context(p)["market_card"]["adjacent_assets"][0]["label"]
        == "Fixture text 5"
    )
    assert p.advertising == "unknown"


def test_original_entry_gestures_remain_verified():
    assert _alignment(screen("before"), screen("first"), scrolling=True)[1]
    assert _alignment(screen("first"), screen(), scrolling=True)[1]


@pytest.mark.parametrize(
    "mutation",
    [
        "not_scrollable",
        "container_control",
        "neighbor_control",
        "neighbor_label",
        "neighbor_text",
        "neighbor_extra",
        "unclipped_neighbor",
        "neighbor_overlap",
        "neighbor_vertical",
        "icon_vertical",
    ],
)
def test_market_carousel_requires_native_full_card_and_clipped_neighbor(mutation):
    root = etree.fromstring(document("market-carousel-after").encode())
    icon = root.xpath('//*[@content-desc="Fixture text 5"]')[0]
    picture = icon.getparent()
    neighbor = picture.getparent()
    wrapper = neighbor.getparent()
    if mutation == "not_scrollable":
        wrapper.set("scrollable", "false")
    elif mutation == "container_control":
        wrapper.set("clickable", "true")
    elif mutation == "neighbor_control":
        neighbor.set("clickable", "false")
    elif mutation == "neighbor_label":
        icon.set("content-desc", "")
    elif mutation == "neighbor_text":
        icon.set("text", "Unexpected")
    elif mutation == "neighbor_extra":
        neighbor.append(etree.fromstring(etree.tostring(picture)))
    elif mutation == "unclipped_neighbor":
        neighbor.set("bounds", "[982,2139][1070,2304]")
    elif mutation == "neighbor_overlap":
        neighbor.set("bounds", "[950,2139][1080,2304]")
    elif mutation == "neighbor_vertical":
        neighbor.set("bounds", "[982,2149][1080,2304]")
    else:
        icon.set("bounds", "[1015,2182][1080,2281]")
    assert read_screen(etree.tostring(root), (1080, 2340)).rejected_posts


@pytest.mark.parametrize("mutation", ["label", "motion", "missing"])
def test_adjacent_asset_identity_and_geometry_cannot_change_without_movement(mutation):
    before = screen()
    p = before.posts[0]
    card = p.market_card
    asset = card.adjacent_assets[0]
    if mutation == "label":
        asset = replace(asset, text="Different asset")
    elif mutation == "motion":
        asset = replace(
            asset, visibility=replace(asset.visibility, bounds=(1015, 2182, 1080, 2281))
        )
    card = replace(card, adjacent_assets=() if mutation == "missing" else (asset,))
    after = replace(before, posts=(replace(p, market_card=card),))
    with pytest.raises(XError):
        _alignment(before, after)
