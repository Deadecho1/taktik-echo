"""An offscreen quote header does not yet establish readable quote content."""

from dataclasses import replace
from pathlib import Path

import pytest
from lxml import etree
from unit.x_fixtures import xml_fixture

from taktik.core.social_media.x.services.browsing.navigation import _alignment
from taktik.core.social_media.x.ui.screen import PostFragment, read_screen


def document(name):
    return xml_fixture(Path(__file__).parent / "fixtures" / f"{name}.xml")


def test_native_quote_header_below_viewport_can_enter_without_invented_body():
    before = read_screen(document("quote-header-entry-before"), (1080, 2340))
    after = read_screen(document("quote-header-entry-after"), (1080, 2340))
    offset, moved = _alignment(before, after, scrolling=True)
    assert (offset, moved) == (0, True)
    p = after.posts[0]
    assert p.author.startswith("@fixture_")
    assert p.quoted_post.author.startswith("@fixture_")
    assert p.quoted_post.body is None and not p.quoted_post.media
    assert not p.observable


@pytest.mark.parametrize(
    "mutation", ["visible_header", "unknown_text", "unknown_control"]
)
def test_empty_quote_requires_clipped_offscreen_header_only(mutation):
    root = etree.fromstring(document("quote-header-entry-after").encode())
    q = root.xpath('//*[@content-desc="Quote"]')[0].getparent()
    if mutation == "visible_header":
        q[-1].set("bounds", "[807,2100][947,2149]")
    elif mutation == "unknown_text":
        etree.SubElement(q, "node", text="Unknown")
    else:
        etree.SubElement(q, "node", **{"clickable": "true", "content-desc": "Unknown"})
    s = read_screen(etree.tostring(root), (1080, 2340))
    assert not s.posts


def revealed_body_screens():
    before = read_screen(document("quote-header-entry-after"), (1080, 2340))
    p = before.posts[0]

    def moved(v):
        x1, y1, x2, y2 = v.bounds
        rect = (x1, max(0, y1 - 606), x2, max(0, y2 - 606))
        return replace(v, bounds=rect, visible_bounds=rect, clipped=False, overlaps=())

    q = p.quoted_post
    q = replace(
        q,
        body="Newly revealed quoted body",
        body_complete=True,
        visibility=replace(moved(q.visibility), bounds=(176, 1685, 1047, 2140)),
        header_visibility=replace(
            moved(q.header_visibility), bounds=(478, 1721, 798, 1770)
        ),
        body_visibility=replace(
            moved(q.header_visibility), bounds=(209, 1795, 1014, 2090)
        ),
    )
    fragment = PostFragment(
        p.body,
        tuple(replace(m, visibility=moved(m.visibility)) for m in p.media),
        moved(p.visibility),
        moved(p.body_visibility),
        quoted_post=q,
    )
    return before, replace(before, posts=(), fragments=(fragment,))


def test_header_only_quote_can_reveal_its_body_on_the_next_verified_gesture():
    before, after = revealed_body_screens()
    assert _alignment(before, after, scrolling=True) == (1, True)


@pytest.mark.parametrize(
    "mutation", ["author", "outer_body", "early_body", "header_motion"]
)
def test_quote_body_revelation_requires_prior_header_and_explained_entry(mutation):
    from taktik.core.social_media.x.services.browsing.navigation import XError

    before, after = revealed_body_screens()
    p = after.fragments[0]
    q = p.quoted_post
    if mutation == "author":
        q = replace(q, author="@changed")
    elif mutation == "outer_body":
        p = replace(p, body="Changed")
    elif mutation == "early_body":
        q = replace(
            q,
            body_visibility=replace(q.body_visibility, bounds=(209, 1600, 1014, 2090)),
        )
    else:
        q = replace(
            q,
            header_visibility=replace(
                q.header_visibility, bounds=(478, 1751, 798, 1800)
            ),
        )
    after = replace(after, fragments=(replace(p, quoted_post=q),))
    with pytest.raises(XError):
        _alignment(before, after, scrolling=True)
