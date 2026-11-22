"""A retained market strip can precede a newly revealed native quote."""

from dataclasses import replace

import pytest
from lxml import etree
from unit.paths import CORE
from unit.x_fixtures import xml_fixture

from taktik.core.social_media.x.services.browsing.navigation import XError, _alignment
from taktik.core.social_media.x.ui.screen import read_screen


def document(name):
    return xml_fixture(CORE / "tests/unit/social_media/x/fixtures" / f"{name}.xml")


def screen(stage):
    return read_screen(document(f"market-quote-entry-{stage}"), (1080, 2340))


def test_market_strip_and_quote_keep_separate_context():
    p = screen("after").fragments[0]
    assert p.market_card.symbol == "BTC"
    assert p.market_card.adjacent_assets[0].text
    assert p.quoted_post.author == screen("before").posts[0].author
    assert p.market_card.visibility.bounds[3] < p.quoted_post.visibility.bounds[1]
    assert not hasattr(p, "author")


@pytest.mark.parametrize(
    "mutation",
    [
        "none",
        "video_bottom",
        "video_top",
        "body",
        "strip_motion",
        "asset",
        "early_quote",
        "missing_strip",
        "ambiguous",
        "uncommanded",
    ],
)
def test_market_quote_entry_requires_retained_content_and_independent_motion(mutation):
    before, after = screen("before"), screen("after")
    p = after.fragments[0]
    if mutation.startswith("video_"):
        m = p.media[0]
        bounds = list(m.visibility.bounds)
        bounds[3 if mutation == "video_bottom" else 1] += 20
        p = replace(
            p,
            media=(replace(m, visibility=replace(m.visibility, bounds=tuple(bounds))),),
        )
    elif mutation == "body":
        p = replace(p, body="Different body")
    elif mutation == "strip_motion":
        c = p.market_card
        bounds = tuple(
            v + (20 if i % 2 else 0) for i, v in enumerate(c.visibility.bounds)
        )
        p = replace(
            p, market_card=replace(c, visibility=replace(c.visibility, bounds=bounds))
        )
    elif mutation == "asset":
        c = p.market_card
        p = replace(
            p,
            market_card=replace(
                c,
                adjacent_assets=(replace(c.adjacent_assets[0], text="Changed asset"),),
            ),
        )
    elif mutation == "early_quote":
        q = p.quoted_post
        p = replace(
            p,
            quoted_post=replace(
                q, visibility=replace(q.visibility, bounds=(176, 1800, 1047, 2165))
            ),
        )
    elif mutation == "missing_strip":
        before = replace(before, posts=(replace(before.posts[0], market_card=None),))
    elif mutation == "ambiguous":
        before = replace(before, posts=before.posts * 2)
    after = replace(after, fragments=(p,))
    if mutation == "none":
        assert _alignment(before, after, scrolling=True) == (1, True)
    else:
        with pytest.raises(XError):
            _alignment(before, after, scrolling=mutation != "uncommanded")


@pytest.mark.parametrize(
    "mutation",
    [
        "quote_overlap",
        "footer_gap",
        "unknown_content",
        "wrapper_control",
        "wrapper_bounds",
    ],
)
def test_strip_quote_geometry_cannot_hide_unrecognized_content(mutation):
    root = etree.fromstring(document("market-quote-entry-after").encode())
    quote = root.xpath('//*[@content-desc="Quote"]')[0].getparent()
    if mutation == "quote_overlap":
        quote.set("bounds", "[176,1800][1047,2165]")
    elif mutation == "footer_gap":
        quote.set("bounds", "[176,1868][1047,2155]")
    elif mutation == "wrapper_control":
        quote.getparent().set("clickable", "true")
    elif mutation == "wrapper_bounds":
        quote.getparent().set("bounds", "[176,1858][1047,2165]")
    else:
        extra = etree.fromstring(etree.tostring(quote[0]))
        extra.set("content-desc", "Unknown control")
        quote.addprevious(extra)
    s = read_screen(etree.tostring(root), (1080, 2340))
    assert not s.fragments
