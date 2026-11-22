"""Headerless quoted body/video and a newly entering nested quote."""

from dataclasses import replace

import pytest
from lxml import etree
from unit.x_fixtures import xml_fixture as document

from taktik.core.social_media.x.services.browsing.browser import post_context
from taktik.core.social_media.x.services.browsing.navigation import XError, _alignment
from taktik.core.social_media.x.ui.screen import read_screen


def screens():
    return tuple(
        read_screen(document(f"nested-quote-tail-{s}"), (1080, 2340))
        for s in ("before", "after")
    )


def test_original_final_gesture_retains_both_occurrences_and_nested_attribution():
    before, after = screens()
    assert _alignment(before, after, scrolling=True) == (0, True)
    assert not after.rejected_posts
    tail = after.fragments[0]
    assert tail.body is None and tail.quoted_post is None
    assert tail.quoted_body.text == before.fragments[0].quoted_post.body
    assert not hasattr(tail, "author")
    post = after.posts[0]
    assert post.author == "@fixture_11"
    assert post.quoted_post.author == "@fixture_14"
    assert post.quoted_post.nested_quote.author == "@fixture_17"
    assert post_context(post)["quoted_post"]["quoted_post"]["username"] == "fixture_17"


@pytest.mark.parametrize(
    "mutation",
    [
        "body",
        "video_edge",
        "body_edge",
        "header_visible",
        "outer_visible",
        "nested_entry",
        "nested_body",
        "nested_author",
    ],
)
def test_new_quote_states_require_retained_text_geometry_and_explained_entry(mutation):
    before, after = screens()
    old, new = before.fragments[0], after.fragments[0]
    if mutation == "body":
        new = replace(new, quoted_body=replace(new.quoted_body, text="Changed"))
    elif mutation in {"video_edge", "body_edge"}:
        v = (
            new.media[0].visibility
            if mutation == "video_edge"
            else new.quoted_body.visibility
        )
        x1, y1, x2, y2 = v.bounds
        v = replace(v, bounds=(x1, y1, x2, y2 + 20))
        new = (
            replace(new, media=(replace(new.media[0], visibility=v),))
            if mutation == "video_edge"
            else replace(new, quoted_body=replace(new.quoted_body, visibility=v))
        )
    elif mutation == "header_visible":
        q = old.quoted_post
        old = replace(
            old,
            quoted_post=replace(
                q,
                header_visibility=replace(
                    q.header_visibility, bounds=(578, 800, 884, 849)
                ),
            ),
        )
    elif mutation == "outer_visible":
        old = replace(
            old,
            body_visibility=replace(old.body_visibility, bounds=(176, 94, 1047, 800)),
        )
    else:
        p = after.posts[0]
        q = p.quoted_post
        n = q.nested_quote
        if mutation == "nested_entry":
            n = replace(
                n, visibility=replace(n.visibility, bounds=(209, 1600, 1014, 1809))
            )
        else:
            previous = (
                replace(n, body="Changed")
                if mutation == "nested_body"
                else replace(n, author="@changed")
            )
            bp = before.posts[0]
            before = replace(
                before,
                posts=(
                    replace(
                        bp, quoted_post=replace(bp.quoted_post, nested_quote=previous)
                    ),
                ),
            )
        after = replace(
            after,
            posts=(
                replace(p, quoted_post=replace(q, nested_quote=n)),
                *after.posts[1:],
            ),
        )
    before = replace(before, fragments=(old,))
    after = replace(after, fragments=(new,))
    with pytest.raises(XError):
        _alignment(before, after, scrolling=True)


@pytest.mark.parametrize(
    "mutation",
    [
        "marker",
        "body_marker",
        "interactive_body",
        "unknown_text",
        "overlap",
        "extra_card",
    ],
)
def test_nested_card_requires_native_structure(mutation):
    root = etree.fromstring(document("nested-quote-tail-after").encode())
    node = root.xpath('//*[@resource-id="nested_quote_preview"]')[0]
    body = node[-1]
    if mutation == "marker":
        node.set("resource-id", "unknown")
    elif mutation == "body_marker":
        body.set("resource-id", "unknown")
    elif mutation == "interactive_body":
        body.set("clickable", "true")
    elif mutation == "unknown_text":
        etree.SubElement(node, "node", text="Unknown")
    elif mutation == "overlap":
        node.set("bounds", "[209,1750][1014,2061]")
    else:
        etree.SubElement(node.getparent(), "node")
    screen = read_screen(etree.tostring(root), (1080, 2340))
    assert not any(p.author == "@fixture_11" for p in screen.posts)


def test_quoted_body_reread_retains_text_without_claiming_movement():
    _, screen = screens()
    assert _alignment(screen, screen) == (0, False)


@pytest.mark.parametrize(
    "mutation", ["interactive", "new_text", "new_body", "inset_body", "card_edge"]
)
def test_headless_quote_body_requires_known_contained_layout(mutation):
    root = etree.fromstring(document("nested-quote-tail-after").encode())
    card = root.xpath('//*[@bounds="[176,7][1047,709]" and @clickable="true"]')[0]
    body = card[0]
    if mutation == "interactive":
        body.set("clickable", "true")
    elif mutation == "new_text":
        card.set("text", "Unknown")
    elif mutation == "new_body":
        etree.SubElement(card, "node", text="Unknown")
    elif mutation == "inset_body":
        body.set("bounds", "[209,150][1014,215]")
    else:
        card.set("bounds", "[176,7][1047,690]")
    screen = read_screen(etree.tostring(root), (1080, 2340))
    assert not screen.fragments
