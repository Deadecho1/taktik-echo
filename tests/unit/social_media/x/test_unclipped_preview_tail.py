"""The missing quote header can leave its article fully below the viewport edge."""

from dataclasses import replace
from pathlib import Path

import pytest
from lxml import etree
from unit.x_fixtures import xml_fixture

from taktik.core.social_media.x.services.browsing.navigation import XError, _alignment
from taktik.core.social_media.x.ui.screen import read_screen


def document(name):
    return xml_fixture(Path(__file__).parent / "fixtures" / f"{name}.xml")


def screens():
    return tuple(
        read_screen(document(f"unclipped-preview-tail-{s}"), (1080, 2340))
        for s in ("before", "after")
    )


def test_complete_preview_below_lost_header_preserves_only_article_text():
    before, after = screens()
    assert not after.rejected_posts
    assert _alignment(before, after, scrolling=True) == (0, True)
    assert len(after.fragments[0].preview_texts) == 2
    assert after.fragments[0].body is None
    assert not hasattr(after.fragments[0], "author")


@pytest.mark.parametrize(
    "mutation", ["title", "summary", "header_loss", "video_loss", "uncommanded"]
)
def test_article_tail_still_requires_exact_text_and_projected_prior_loss(mutation):
    before, after = screens()
    a, b = before.fragments[0], after.fragments[0]
    if mutation in {"title", "summary"}:
        texts = list(b.preview_texts)
        i = 0 if mutation == "title" else 1
        texts[i] = replace(texts[i], text="Changed")
        b = replace(b, preview_texts=tuple(texts))
    elif mutation == "header_loss":
        q = a.quoted_post
        a = replace(
            a,
            quoted_post=replace(
                q,
                header_visibility=replace(
                    q.header_visibility, bounds=(464, 710, 649, 759)
                ),
            ),
        )
    elif mutation == "video_loss":
        m = a.media[0]
        a = replace(
            a,
            media=(
                replace(
                    m, visibility=replace(m.visibility, bounds=(176, 0, 1047, 800))
                ),
            ),
        )
    with pytest.raises(XError):
        _alignment(
            replace(before, fragments=(a,)),
            replace(after, fragments=(b,)),
            scrolling=mutation != "uncommanded",
        )


def test_headerless_card_must_still_cross_the_viewport_boundary():
    root = etree.fromstring(document("unclipped-preview-tail-after").encode())
    wrapper = root.xpath('//*[@bounds="[176,47][1047,972]"]')[0]
    wrapper.set("bounds", "[176,137][1047,972]")
    wrapper[0].set("bounds", "[176,137][1047,972]")
    assert read_screen(etree.tostring(root), (1080, 2340)).rejected_posts
