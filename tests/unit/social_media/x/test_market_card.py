"""Native market cards remain displayed context, separate from authored content."""

from dataclasses import replace

import pytest
from lxml import etree
from unit.x_fixtures import xml_fixture as document

from taktik.core.social_media.x.services.browsing.browser import post_context
from taktik.core.social_media.x.services.browsing.navigation import XError, _alignment
from taktik.core.social_media.x.ui.screen import read_screen


def screens():
    return tuple(
        read_screen(document(f"market-card-{s}"), (1080, 2340))
        for s in ("before", "after")
    )


def test_market_card_is_separate_displayed_context_and_keeps_outer_identity():
    before, after = screens()
    assert not before.rejected_posts and not after.rejected_posts
    p = before.posts[0]
    card = p.market_card
    assert (card.name, card.symbol, card.price, card.change) == (
        "Fixture text 4",
        "CSI",
        "$0.0000367",
        "+169.15%",
    )
    assert card.name not in p.body
    assert p.advertising == "unknown"
    assert post_context(p)["market_card"]["price"] == card.price
    assert not hasattr(after.fragments[0], "author")
    assert after.fragments[0].market_card.name == card.name
    assert _alignment(before, after, scrolling=True) == (1, True)


@pytest.mark.parametrize(
    "mutation",
    [
        "symbol",
        "price",
        "change",
        "icon",
        "interactive",
        "nested",
        "outside",
        "order",
        "wrapper",
        "before_video",
    ],
)
def test_market_card_requires_native_structure_and_label_geometry(mutation):
    root = etree.fromstring(document("market-card-before").encode())
    symbol = root.xpath('//*[@text="CSI"]')[0]
    card = symbol.getparent()
    wrapper = card.getparent()
    if mutation == "symbol":
        symbol.set("text", "Invalid symbol!")
    elif mutation == "price":
        symbol.getnext().set("text", "Not a price")
    elif mutation == "change":
        card[-1].set("text", "Not a percentage")
    elif mutation == "icon":
        card[0][0].set("content-desc", "Different asset")
    elif mutation == "interactive":
        symbol.set("clickable", "true")
    elif mutation == "nested":
        symbol.append(etree.fromstring(etree.tostring(symbol)))
    elif mutation == "outside":
        symbol.set("bounds", "[0,1521][100,1564]")
    elif mutation == "order":
        card.insert(2, card[-1])
    elif mutation == "wrapper":
        wrapper.set("clickable", "true")
    else:
        wrapper.getparent().insert(0, wrapper)
    assert read_screen(etree.tostring(root), (1080, 2340)).rejected_posts


@pytest.mark.parametrize("mutation", ["identity", "motion", "missing", "uncommanded"])
def test_market_card_continuity_rejects_changed_assets_or_unexplained_loss(mutation):
    before, after = screens()
    p = after.fragments[0]
    c = p.market_card
    if mutation == "identity":
        c = replace(c, symbol="OTHER")
    elif mutation == "motion":
        c = replace(c, visibility=replace(c.visibility, bounds=(176, 850, 1047, 1024)))
    elif mutation == "missing":
        c = None
    after = replace(after, fragments=(replace(p, market_card=c),))
    with pytest.raises(XError):
        _alignment(before, after, scrolling=mutation != "uncommanded")


def test_displayed_prices_can_refresh_without_rewriting_the_authored_post():
    before, _ = screens()
    root = etree.fromstring(document("market-card-before").encode())
    root.xpath('//*[@text="$0.0000367"]')[0].set("text", "$0.0000368")
    root.xpath('//*[@text="+169.15%"]')[0].set("text", "+169.16%")
    after = read_screen(etree.tostring(root), (1080, 2340))
    assert after.posts[0].content_key == before.posts[0].content_key
    assert after.posts[0].market_card.price == "$0.0000368"
    assert _alignment(before, after) == (0, False)
