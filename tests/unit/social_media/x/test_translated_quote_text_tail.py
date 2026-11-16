"""A translated quote retains text after its outer video and author disappear."""

from dataclasses import replace
from pathlib import Path

import pytest
from lxml import etree
from taktik.core.social_media.x.services.browsing.navigation import XError, _alignment
from taktik.core.social_media.x.ui.screen import read_screen


def document(name):
    return (Path(__file__).parent / "fixtures" / f"{name}.xml").read_text()


def screen(stage):
    return read_screen(document(f"translated-quote-text-tail-{stage}"), (1080, 2340))


def test_text_tail_remains_unattributed_after_quote_header_and_video_loss():
    before, after = screen("before"), screen("after")
    tail = after.fragments[0]
    assert tail.quoted_body.text == before.fragments[0].quoted_post.body
    assert tail.quoted_translation.text == "Translated from Indonesian"
    assert tail.body is None and not tail.media
    assert not hasattr(tail, "author")
    assert _alignment(before, after, scrolling=True) == (0, True)


@pytest.mark.parametrize(
    "mutation",
    [
        "body",
        "translation",
        "translation_motion",
        "body_motion",
        "footer_motion",
        "header_visible",
        "video_visible",
        "ambiguous",
        "uncommanded",
    ],
)
def test_text_tail_requires_exact_context_motion_and_projected_content_loss(mutation):
    before, after = screen("before"), screen("after")
    old, p = before.fragments[0], after.fragments[0]
    if mutation == "body":
        p = replace(p, quoted_body=replace(p.quoted_body, text="Different body"))
    elif mutation == "translation":
        p = replace(
            p,
            quoted_translation=replace(
                p.quoted_translation, text="Translated from French"
            ),
        )
    elif mutation == "translation_motion":
        t = p.quoted_translation
        p = replace(
            p,
            quoted_translation=replace(
                t, visibility=replace(t.visibility, bounds=(283, 136, 725, 179))
            ),
        )
    elif mutation == "body_motion":
        t = p.quoted_body
        p = replace(
            p,
            quoted_body=replace(
                t, visibility=replace(t.visibility, bounds=(198, 179, 1025, 338))
            ),
        )
    elif mutation == "footer_motion":
        t = p.actions[0]
        p = replace(
            p,
            actions=(
                replace(
                    t, visibility=replace(t.visibility, bounds=(137, 368, 322, 486))
                ),
                *p.actions[1:],
            ),
        )
    elif mutation == "header_visible":
        q = old.quoted_post
        old = replace(
            old,
            quoted_post=replace(
                q,
                header_visibility=replace(
                    q.header_visibility, bounds=(393, 600, 615, 649)
                ),
            ),
        )
    elif mutation == "video_visible":
        m = old.media[0]
        old = replace(
            old,
            media=(
                replace(
                    m, visibility=replace(m.visibility, bounds=(176, 0, 1047, 700))
                ),
            ),
        )
    elif mutation == "ambiguous":
        before = replace(before, fragments=before.fragments * 2)
    if mutation in {"header_visible", "video_visible"}:
        before = replace(before, fragments=(old,))
    after = replace(after, fragments=(p,))
    with pytest.raises(XError):
        _alignment(before, after, scrolling=mutation != "uncommanded")


@pytest.mark.parametrize(
    "mutation",
    [
        "unknown_translation",
        "translation_control",
        "wrapper_control",
        "body_control",
        "body_outside",
        "translation_gap",
    ],
)
def test_text_tail_requires_exact_native_wrapper_translation_and_body(mutation):
    root = etree.fromstring(document("translated-quote-text-tail-after").encode())
    label = root.xpath('//*[@text="Translated from Indonesian"]')[0]
    body, card = label.getnext(), label.getparent()
    if mutation == "unknown_translation":
        label.set("text", "Unknown context")
    elif mutation == "translation_control":
        label.set("clickable", "true")
    elif mutation == "wrapper_control":
        card.getparent().set("clickable", "true")
    elif mutation == "body_control":
        body.set("clickable", "true")
    elif mutation == "body_outside":
        body.set("bounds", "[160,169][1025,328]")
    else:
        label.set("bounds", "[283,126][725,160]")
    assert not read_screen(etree.tostring(root), (1080, 2340)).fragments


def test_translated_text_tail_can_lose_translation_only_above_the_viewport():
    from taktik.core.shared.ui.geometry import bounds

    root = etree.fromstring(document("translated-quote-text-tail-after").encode())
    label = root.xpath('//*[@text="Translated from Indonesian"]')[0]
    container = label.getparent().getparent().getparent()
    label.getparent().remove(label)
    for n in container.iter():
        x1, y1, x2, y2 = bounds(n)
        n.set("bounds", f"[{x1},{max(0, y1 - 150)}][{x2},{max(0, y2 - 150)}]")
    after = read_screen(etree.tostring(root), (1080, 2340))
    assert after.fragments[0].quoted_translation is None
    assert _alignment(screen("after"), after, scrolling=True) == (0, True)


def test_counter_refresh_does_not_replace_the_independent_text_motion_proof():
    before, after = screen("before"), screen("after")
    p = after.fragments[0]
    p = replace(p, actions=tuple(replace(a, count="123") for a in p.actions))
    assert _alignment(before, replace(after, fragments=(p,)), scrolling=True) == (
        0,
        True,
    )
