"""Native disclosure in a quote wrapper remains separate from the outer post."""

from dataclasses import replace
from pathlib import Path

import pytest
from lxml import etree

from taktik.core.shared.ui.geometry import bounds
from taktik.core.social_media.x.services.browsing.browser import post_context
from taktik.core.social_media.x.services.browsing.navigation import XError, _alignment
from taktik.core.social_media.x.ui.screen import read_screen


def document(name):
    return (Path(__file__).parent / "fixtures" / f"{name}.xml").read_text()


def screens():
    return tuple(
        read_screen(document(f"quoted-paid-disclosure-{s}"), (1080, 2340))
        for s in ("before", "after")
    )


def test_native_pair_is_quote_footer_context_and_not_outer_advertising():
    before, after = screens()
    assert not after.rejected_posts
    assert _alignment(before, after, scrolling=True) == (1, True)
    p = after.fragments[0]
    assert p.advertising == "unknown"
    assert [v.text for v in p.quoted_post.footer_annotations] == ["Paid partnership"]
    context = post_context(replace(before.posts[0], quoted_post=p.quoted_post))
    assert context["advertising"] == "unknown"
    assert context["quoted_post"]["footer_annotations"] == ["Paid partnership"]


@pytest.mark.parametrize(
    "mutation", ["label", "interactive", "position", "wrapper", "missing_icon"]
)
def test_quote_disclosure_requires_native_pair_and_exact_wrapper_geometry(mutation):
    root = etree.fromstring(document("quoted-paid-disclosure-after").encode())
    icon = root.xpath('//*[@content-desc="Paid partnership"]')[0]
    label = icon.getnext()
    if mutation == "label":
        label.set("text", "Unknown sponsorship")
    elif mutation == "interactive":
        icon.set("clickable", "true")
    elif mutation == "position":
        label.set("bounds", "[237,1958][504,1998]")
    elif mutation == "wrapper":
        icon.getparent().set("bounds", "[176,793][1047,2150]")
    else:
        icon.getparent().remove(icon)
    after = read_screen(etree.tostring(root), (1080, 2340))
    assert not after.fragments


@pytest.mark.parametrize("mutation", ["early_entry", "label", "uncommanded"])
def test_disclosure_never_supplies_movement_or_bypasses_native_entry_checks(mutation):
    before, after = screens()
    p = after.fragments[0]
    q = p.quoted_post
    item = q.footer_annotations[0]
    if mutation == "early_entry":
        item = replace(
            item, visibility=replace(item.visibility, bounds=(187, 1658, 504, 1698))
        )
    elif mutation == "label":
        item = replace(item, text="Unknown")
    p = replace(p, quoted_post=replace(q, footer_annotations=(item,)))
    with pytest.raises(XError):
        _alignment(
            before, replace(after, fragments=(p,)), scrolling=mutation != "uncommanded"
        )


def test_disclosure_remains_in_the_quoted_body_tail_after_its_header_leaves():
    before = replace(screens()[1], posts=())
    root = etree.fromstring(document("quoted-paid-disclosure-after").encode())
    marker = root.xpath('//*[@content-desc="Quote"]')[0]
    card = marker.getparent()
    wrapper = card.getparent()
    container = wrapper.getparent()
    for sibling in list(container.getparent()):
        if sibling is not container:
            container.getparent().remove(sibling)
    for child in list(container):
        if child is wrapper:
            break
        container.remove(child)
    for child in list(card)[:-2]:
        card.remove(child)
    for node in container.iter():
        x1, y1, x2, y2 = bounds(node)
        node.set("bounds", f"[{x1},{max(0, y1 - 900)}][{x2},{max(0, y2 - 900)}]")
    after = read_screen(etree.tostring(root), (1080, 2340))
    assert not after.rejected_posts
    assert _alignment(before, after, scrolling=True) == (0, True)
    assert after.fragments[0].quoted_footer_annotations == tuple(
        replace(
            v,
            visibility=replace(
                v.visibility,
                bounds=(187, 1158, 504, 1198),
                visible_bounds=(187, 1158, 504, 1198),
                overlaps=(),
            ),
        )
        for v in before.fragments[0].quoted_post.footer_annotations
    )


@pytest.mark.parametrize("mutation", ["missing", "text", "motion"])
def test_visible_quote_disclosure_cannot_change_during_a_reread(mutation):
    before = screens()[1]
    p = before.fragments[0]
    q = p.quoted_post
    item = q.footer_annotations[0]
    if mutation == "text":
        item = replace(item, text="Changed")
    elif mutation == "motion":
        item = replace(
            item, visibility=replace(item.visibility, bounds=(187, 2050, 504, 2090))
        )
    q = replace(q, footer_annotations=() if mutation == "missing" else (item,))
    with pytest.raises(XError):
        _alignment(before, replace(before, fragments=(replace(p, quoted_post=q),)))
