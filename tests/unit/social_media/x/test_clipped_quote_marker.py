"""A quote glyph can outlive the author row while its body remains below it."""

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
        read_screen(document(f"clipped-quote-marker-{s}"), (1080, 2340))
        for s in ("before", "after")
    )


def test_clipped_marker_preserves_unattributed_quoted_body_and_article():
    before, after = screens()
    assert not after.rejected_posts
    assert _alignment(before, after, scrolling=True) == (0, True)
    p = after.fragments[0]
    assert p.body is p.quoted_post is None
    assert p.quoted_body.text == before.fragments[0].quoted_post.body
    assert p.quoted_body.visibility.bounds[1] > after.content_viewport[1]
    assert not hasattr(p, "author")


@pytest.mark.parametrize(
    "mutation",
    [
        "visible_marker",
        "interactive_marker",
        "marker_text",
        "body_overlap",
        "extra_header",
    ],
)
def test_retained_marker_requires_a_clipped_plain_glyph_and_known_body_layout(mutation):
    root = etree.fromstring(document("clipped-quote-marker-after").encode())
    marker = root.xpath('//*[@content-desc="Quote"]')[0]
    if mutation == "visible_marker":
        marker.set("bounds", "[209,140][264,195]")
    elif mutation == "interactive_marker":
        marker.set("clickable", "true")
    elif mutation == "marker_text":
        marker.set("text", "Unknown")
    elif mutation == "body_overlap":
        marker.getnext().set("bounds", "[209,130][1014,432]")
    else:
        etree.SubElement(marker.getparent(), "node", text="Unrecognized header")
    after = read_screen(etree.tostring(root), (1080, 2340))
    assert not after.fragments


@pytest.mark.parametrize(
    "mutation", ["body", "header_loss", "video_loss", "article", "uncommanded"]
)
def test_partial_marker_cannot_bypass_exact_text_motion_or_projected_header_loss(
    mutation,
):
    before, after = screens()
    a, b = before.fragments[0], after.fragments[0]
    if mutation == "body":
        b = replace(b, quoted_body=replace(b.quoted_body, text="Changed"))
    elif mutation == "header_loss":
        q = a.quoted_post
        a = replace(
            a,
            quoted_post=replace(
                q,
                header_visibility=replace(
                    q.header_visibility, bounds=(464, 713, 651, 762)
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
    elif mutation == "article":
        m = b.media[0]
        b = replace(b, media=(replace(m, description="Changed"),))
    with pytest.raises(XError):
        _alignment(
            replace(before, fragments=(a,)),
            replace(after, fragments=(b,)),
            scrolling=mutation != "uncommanded",
        )
