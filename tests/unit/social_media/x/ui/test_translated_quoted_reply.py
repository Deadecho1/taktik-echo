"""A native quoted reply may place translation between its recipient and body."""

from dataclasses import replace

import pytest
from lxml import etree
from unit.x_fixtures import xml_fixture as document

from taktik.core.social_media.x.services.browsing.navigation import XError, _alignment
from taktik.core.social_media.x.ui.screen import read_screen


def screen(stage):
    return read_screen(document(f"translated-quoted-reply-{stage}"), (1080, 2340))


def test_reply_and_translation_remain_separate_from_quoted_body():
    s = screen("after")
    assert not s.rejected_posts
    q = s.fragments[0].quoted_post
    assert len(q.reply_to) == 1 and q.reply_to[0].startswith("@")
    assert q.translation == "Translated from Spanish"
    assert not q.body_complete
    assert "Replying to" not in q.body
    assert "Translated from" not in q.body


def test_captured_fragment_quote_entry_retains_alignment():
    assert _alignment(screen("first"), screen("second"), scrolling=True)[1]
    assert _alignment(screen("before"), screen("after"), scrolling=True)[1]


@pytest.mark.parametrize(
    "mutation",
    ["body", "translation", "obscured", "width", "early_quote", "video", "uncommanded"],
)
def test_fragment_quote_entry_requires_independent_retained_body_and_media(mutation):
    before, after = screen("first"), screen("second")
    p = after.fragments[1]
    if mutation == "body":
        p = replace(p, body="Changed")
    elif mutation == "translation":
        p = replace(p, translation="Translated from French")
    elif mutation == "obscured":
        p = replace(
            p,
            body_visibility=replace(
                p.body_visibility, overlaps=((176, 857, 1047, 961),)
            ),
        )
    elif mutation == "width":
        p = replace(
            p, body_visibility=replace(p.body_visibility, bounds=(186, 857, 1047, 961))
        )
    elif mutation == "early_quote":
        q = p.quoted_post
        p = replace(
            p,
            quoted_post=replace(
                q, visibility=replace(q.visibility, bounds=(176, 1580, 1047, 2257))
            ),
        )
    elif mutation == "video":
        m = p.media[0]
        p = replace(
            p,
            media=(
                replace(
                    m, visibility=replace(m.visibility, bounds=(176, 1003, 1047, 1854))
                ),
            ),
        )
    after = replace(after, fragments=(after.fragments[0], p))
    with pytest.raises(XError):
        _alignment(before, after, scrolling=mutation != "uncommanded")


@pytest.mark.parametrize(
    "mutation",
    [
        "recipient",
        "translation",
        "order",
        "reply_control",
        "translation_control",
        "geometry",
    ],
)
def test_translated_reply_preserves_native_annotation_validation(mutation):
    root = etree.fromstring(document("translated-quoted-reply-after").encode())
    reply = root.xpath('//*[starts-with(@text,"Replying to ")]')[0]
    label = reply.getnext()
    if mutation == "recipient":
        reply.set("text", "Replying to unknown")
    elif mutation == "translation":
        label.set("text", "Translated from ???")
    elif mutation == "order":
        reply.getparent().append(label)
    elif mutation == "reply_control":
        reply.set("clickable", "false")
    elif mutation == "translation_control":
        label.set("clickable", "true")
    else:
        reply.set("bounds", "[100,1127][803,1259]")
    assert read_screen(etree.tostring(root), (1080, 2340)).rejected_posts
