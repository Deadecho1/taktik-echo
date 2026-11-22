"""An entirely offscreen quote header may retain padding below its text row."""

from copy import deepcopy
from dataclasses import replace

import pytest
from lxml import etree
from unit.x_fixtures import xml_fixture as document

from taktik.core.social_media.x.services.browsing.navigation import (
    XError,
    _alignment,
)
from taktik.core.social_media.x.ui.screen import PostFragment, read_screen


def screen(stage="after"):
    return read_screen(document(f"offscreen-quote-padding-{stage}"), (1080, 2340))


def test_quote_padding_does_not_erase_the_next_post_or_invent_quote_content():
    s = screen()
    assert not s.rejected_posts
    p = s.posts[0]
    q = p.quoted_post
    assert q.body is None and not q.media
    assert q.header_visibility.visible_bounds is None
    assert q.header_visibility.bounds[3] < q.visibility.bounds[3]
    assert not p.observable


@pytest.mark.parametrize(
    "mutation", ["visible_header", "outside_card", "unknown_control"]
)
def test_empty_quote_remains_restricted_to_an_entirely_offscreen_header(mutation):
    root = etree.fromstring(document("offscreen-quote-padding-after").encode())
    card = root.xpath('//*[@content-desc="Quote"]')[0].getparent()
    if mutation == "visible_header":
        card[-1].set("bounds", "[782,2210][851,2259]")
    elif mutation == "outside_card":
        card[-1].set("bounds", "[782,2266][851,2350]")
    else:
        control = deepcopy(card[0])
        control.set("content-desc", "Unknown")
        card.append(control)
    assert read_screen(etree.tostring(root), (1080, 2340)).rejected_posts


def revealed_body():
    before = screen()
    p = before.posts[0]

    def moved(v):
        x1, y1, x2, y2 = v.bounds
        box = (x1, max(0, y1 - 600), x2, max(0, y2 - 600))
        return replace(v, bounds=box, visible_bounds=box, overlaps=(), clipped=False)

    q = p.quoted_post
    q = replace(
        q,
        header_visibility=moved(q.header_visibility),
        visibility=replace(moved(q.visibility), bounds=(176, 1630, 1047, 2300)),
        body="New quoted body",
        body_visibility=replace(
            moved(q.header_visibility), bounds=(209, 1740, 1014, 2220)
        ),
    )
    p = replace(
        p,
        header_visibility=moved(p.header_visibility),
        author_visibility=moved(p.author_visibility),
        body_visibility=moved(p.body_visibility),
        visibility=moved(p.visibility),
        media=tuple(replace(m, visibility=moved(m.visibility)) for m in p.media),
        quoted_post=q,
    )
    fragment = PostFragment(
        p.body, p.media, p.visibility, p.body_visibility, quoted_post=q
    )
    return replace(before, fragments=()), replace(
        before, fragments=(fragment,), posts=()
    )


def test_padded_offscreen_header_can_reveal_body_with_independent_movement():
    assert _alignment(*revealed_body(), scrolling=True) == (1, True)


def test_unclipped_header_cannot_change_height_as_its_body_enters():
    before, after = revealed_body()
    p = after.fragments[0]
    q = p.quoted_post
    q = replace(
        q, header_visibility=replace(q.header_visibility, bounds=(515, 1666, 773, 1740))
    )
    with pytest.raises(XError):
        _alignment(
            before,
            replace(after, fragments=(replace(p, quoted_post=q),)),
            scrolling=True,
        )
