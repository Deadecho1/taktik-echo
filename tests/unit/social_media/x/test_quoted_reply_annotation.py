"""Quoted reply recipients are contextual metadata, never outer authorship."""

from dataclasses import replace
from pathlib import Path

import pytest
from lxml import etree
from taktik.core.social_media.x.services.browsing.browser import post_context
from taktik.core.social_media.x.services.browsing.navigation import XError, _alignment
from taktik.core.social_media.x.ui.screen import read_screen


def document(name):
    return (Path(__file__).with_name("fixtures") / f"{name}.xml").read_text()


def screen(stage):
    return read_screen(document(f"quoted-reply-annotation-{stage}"), (1080, 2340))


def test_quoted_reply_context_keeps_raw_annotation_and_local_recipients():
    p = screen("after").posts[0]
    q = p.quoted_post
    assert q.reply_to == ("@Hollywoodbets",)
    assert q.reply_annotation == "Replying to \ufeff@Hollywoodbets\ufeff"
    assert q.author != p.author
    assert p.reply_annotation is None and not p.reply_to
    assert q.translation is None
    assert q.body and q.body != q.reply_annotation
    assert not q.body_complete
    context = post_context(p)
    assert context["quoted_post"]["reply_to"] == ["@Hollywoodbets"]
    assert not context["reply_to"]


@pytest.mark.parametrize(
    "mutation",
    [
        "recipient",
        "class",
        "nested",
        "disabled",
        "not_clickable",
        "order",
        "left",
        "top",
    ],
)
def test_quoted_reply_requires_native_structure_and_recipient_syntax(mutation):
    root = etree.fromstring(document("quoted-reply-annotation-after").encode())
    label = root.xpath('//*[starts-with(@text,"Replying to ")]')[0]
    if mutation == "recipient":
        label.set("text", "Replying to someone")
    elif mutation == "class":
        label.set("class", "android.view.View")
    elif mutation == "nested":
        label.append(etree.fromstring('<node text="unknown"/>'))
    elif mutation == "disabled":
        label.set("enabled", "false")
    elif mutation == "not_clickable":
        label.set("clickable", "false")
    elif mutation == "order":
        label.getparent().append(label)
    else:
        label.set(
            "bounds",
            "[100,1763][736,1895]" if mutation == "left" else "[198,1750][736,1895]",
        )
    assert not read_screen(etree.tostring(root), (1080, 2340)).posts


def test_quoted_reply_change_cannot_refresh_a_known_occurrence():
    before = screen("after")
    p = before.posts[0]
    q = replace(
        p.quoted_post,
        reply_to=("@different",),
        reply_annotation="Replying to @different",
    )
    after = replace(before, posts=(replace(p, quoted_post=q),))
    with pytest.raises(XError):
        _alignment(before, after)
