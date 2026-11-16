"""Quoted inline accessibility annotations retain their own attribution."""

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
        read_screen(document(f"quoted-inline-annotation-{s}"), (1080, 2340))
        for s in ("before", "after")
    )


def test_quote_annotation_restores_the_original_ordered_transition():
    before, after = screens()
    assert not before.rejected_posts
    assert not after.rejected_posts
    assert _alignment(before, after, scrolling=True) == (0, True)
    post = before.posts[0]
    assert post.body_annotations == ()
    assert [v.text for v in post.quoted_post.body_annotations] == ["Iran flag"]
    assert post_context(post)["quoted_post"]["body_annotations"] == ["Iran flag"]


@pytest.mark.parametrize(
    "mutation", ["label", "nested", "interactive", "outside", "class"]
)
def test_quote_annotations_reuse_strict_native_body_recognition(mutation):
    root = etree.fromstring(document("quoted-inline-annotation-before").encode())
    node = root.xpath('//*[@content-desc="Iran flag"]')[0]
    if mutation == "label":
        node.set("content-desc", "Unknown")
    elif mutation == "nested":
        etree.SubElement(
            node,
            "node",
            text="Unknown",
            package="com.twitter.android",
            bounds=node.get("bounds"),
        )
    elif mutation == "interactive":
        node.set("clickable", "true")
    elif mutation == "outside":
        node.set("bounds", "[0,0][42,42]")
    else:
        node.set("class", "android.widget.Button")
    after = read_screen(etree.tostring(root), (1080, 2340))
    assert after.rejected_posts


@pytest.mark.parametrize("mutation", ["missing", "text", "motion", "duplicate"])
@pytest.mark.parametrize("scrolling", [False, True])
def test_visible_annotation_changes_cannot_bypass_continuity(mutation, scrolling):
    before, after = screens()
    if not scrolling:
        after = before
    items = list(after.posts)
    index = next(i for i, p in enumerate(items) if p.quoted_post is not None)
    p = items[index]
    q = p.quoted_post
    item = q.body_annotations[0]
    if mutation == "text":
        item = replace(item, text="Changed")
    elif mutation == "motion":
        r = item.visibility.bounds
        item = replace(
            item,
            visibility=replace(
                item.visibility, bounds=(r[0], r[1] + 20, r[2], r[3] + 20)
            ),
        )
    annotations = (
        ()
        if mutation == "missing"
        else (item, item)
        if mutation == "duplicate"
        else (item,)
    )
    items[index] = replace(p, quoted_post=replace(q, body_annotations=annotations))
    after = replace(after, posts=tuple(items))
    with pytest.raises(XError):
        _alignment(before, after, scrolling=scrolling)


@pytest.mark.parametrize("shift", [550, 600])
def test_annotation_survival_and_loss_follow_quoted_body_clipping(shift):
    before = replace(screens()[1], fragments=(), posts=(screens()[1].posts[0],))
    root = etree.fromstring(document("quoted-inline-annotation-after").encode())
    flag = root.xpath('//*[@content-desc="Iran flag"]')[0]
    body = flag.getparent()
    card = body.getparent()
    wrapper = card.getparent()
    container = wrapper.getparent()
    for sibling in list(container.getparent()):
        if sibling is not container:
            container.getparent().remove(sibling)
    for child in list(container):
        if child is wrapper:
            break
        container.remove(child)
    for child in list(card):
        if child is body:
            break
        card.remove(child)
    if shift == 600:
        body.remove(flag)
    for node in container.iter():
        x1, y1, x2, y2 = bounds(node)
        node.set("bounds", f"[{x1},{max(0, y1 - shift)}][{x2},{max(0, y2 - shift)}]")
    after = read_screen(etree.tostring(root), (1080, 2340))
    assert not after.rejected_posts
    assert after.fragments[0].quoted_body is not None
    assert bool(after.fragments[0].quoted_body_annotations) == (shift == 550)
    assert _alignment(before, after, scrolling=True) == (1, True)
    if shift == 550:
        p = after.fragments[0]
        with pytest.raises(XError):
            _alignment(
                before,
                replace(after, fragments=(replace(p, quoted_body_annotations=()),)),
                scrolling=True,
            )
