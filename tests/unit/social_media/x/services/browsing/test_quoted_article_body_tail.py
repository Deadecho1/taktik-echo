"""A quoted body and article survive loss of the outer video and quote header."""

from dataclasses import replace

import pytest
from lxml import etree
from unit.paths import CORE

from taktik.core.shared.ui.geometry import bounds
from taktik.core.social_media.x.services.browsing.navigation import XError, _alignment
from taktik.core.social_media.x.ui.screen import read_screen


def document(name):
    return (CORE / "tests/unit/social_media/x/fixtures" / f"{name}.xml").read_text()


def screens():
    return tuple(
        read_screen(document(f"quoted-article-body-tail-{s}"), (1080, 2340))
        for s in ("before", "after")
    )


def test_original_article_body_tail_preserves_exact_quoted_text_and_preview():
    before, after = screens()
    assert _alignment(before, after, scrolling=True) == (0, True)
    assert after.fragments[0].body is None
    assert after.fragments[0].quoted_body.text == before.fragments[0].quoted_post.body
    assert after.fragments[0].media[0].kind == "preview"
    assert _alignment(after, after) == (0, False)


@pytest.mark.parametrize(
    "mutation", ["body", "title", "summary", "outer_video", "header", "preview_motion"]
)
def test_article_tail_requires_exact_content_and_projected_outer_loss(mutation):
    before, after = screens()
    old, new = before.fragments[0], after.fragments[0]
    if mutation == "body":
        new = replace(new, quoted_body=replace(new.quoted_body, text="Changed"))
    elif mutation in {"title", "summary", "preview_motion"}:
        m = new.media[0]
        if mutation == "preview_motion":
            v = m.description_visibility
            x1, y1, x2, y2 = v.bounds
            m = replace(
                m, description_visibility=replace(v, bounds=(x1, y1 + 20, x2, y2 + 20))
            )
        else:
            m = replace(
                m,
                **{"description" if mutation == "title" else "preview_text": "Changed"},
            )
        new = replace(new, media=(m,))
    elif mutation == "outer_video":
        m = old.media[0]
        old = replace(
            old,
            media=(
                replace(
                    m, visibility=replace(m.visibility, bounds=(176, 0, 1047, 900))
                ),
            ),
        )
    else:
        q = old.quoted_post
        old = replace(
            old,
            quoted_post=replace(
                q,
                header_visibility=replace(
                    q.header_visibility, bounds=(457, 800, 661, 849)
                ),
            ),
        )
    with pytest.raises(XError):
        _alignment(
            replace(before, fragments=(old,)),
            replace(after, fragments=(new,)),
            scrolling=True,
        )


def test_article_text_remains_when_its_quoted_body_scrolls_away():
    root = etree.fromstring(document("quoted-article-body-tail-after").encode())
    feed = root.xpath('//*[@resource-id="timeline_post"]')[0].getparent().getparent()
    card = feed[0][0][0]
    card.remove(card[0])
    for node in feed.iter():
        if node is feed:
            continue
        x1, y1, x2, y2 = bounds(node)
        node.set("bounds", f"[{x1},{max(0, y1 - 300)}][{x2},{max(0, y2 - 300)}]")
    before = screens()[1]
    after = read_screen(etree.tostring(root), (1080, 2340))
    assert after.fragments[0].preview_texts
    assert _alignment(before, after, scrolling=True) == (0, True)
