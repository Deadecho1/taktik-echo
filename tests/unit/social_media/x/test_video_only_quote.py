"""A native video-only quote has its own author and full-width square media."""

from dataclasses import replace
from pathlib import Path

import pytest
from lxml import etree
from unit.x_fixtures import xml_fixture

from taktik.core.social_media.x.services.browsing.navigation import XError, _alignment
from taktik.core.social_media.x.ui.screen import read_screen


def document(name):
    return xml_fixture(Path(__file__).parent / "fixtures" / f"{name}.xml")


def screen(stage):
    return read_screen(document(f"video-only-quote-{stage}"), (1080, 2340))


def test_video_only_quote_keeps_media_separate_from_outer_body():
    before, after = screen("before"), screen("after")
    p = after.fragments[0]
    assert p.body == before.posts[0].body
    assert p.quoted_post.body is None
    assert not p.quoted_post.body_complete
    assert p.quoted_post.media[0].kind == "video"
    assert not hasattr(p, "author")
    assert p.quoted_post.author != before.posts[0].author
    assert _alignment(before, after, scrolling=True) == (1, True)


@pytest.mark.parametrize(
    "mutation",
    [
        "play",
        "control",
        "extra",
        "media_bounds",
        "header_overlap",
        "asymmetric",
        "unclipped",
    ],
)
def test_video_only_quote_requires_native_children_and_full_width_geometry(mutation):
    root = etree.fromstring(document("video-only-quote-after").encode())
    play = root.xpath('//*[@content-desc="play"]')[0]
    preview = play.getparent()
    if mutation == "play":
        play.set("content-desc", "Unknown")
    elif mutation == "control":
        play.set("clickable", "true")
    elif mutation == "extra":
        preview.append(etree.fromstring(etree.tostring(play)))
    elif mutation == "media_bounds":
        preview[0].set("bounds", "[198,1950][1025,2340]")
    else:
        rect = {
            "header_overlap": "[198,1900][1025,2340]",
            "asymmetric": "[208,1946][1025,2340]",
            "unclipped": "[198,1946][1025,2240]",
        }[mutation]
        for n in (preview, preview[0], preview[1]):
            n.set("bounds", rect)
        if mutation == "unclipped":
            play.set("bounds", "[586,2170][645,2229]")
    assert read_screen(etree.tostring(root), (1080, 2340)).rejected_posts


@pytest.mark.parametrize(
    "mutation",
    [
        "early_credit",
        "missing_credit_bounds",
        "missing_credit_content",
        "credit_outside",
        "video",
        "early_quote",
        "ambiguous",
        "uncommanded",
    ],
)
def test_credit_entry_requires_native_content_below_old_capture_and_independent_motion(
    mutation,
):
    before, after = screen("before"), screen("after")
    p = after.fragments[0]
    m = p.media[0]
    assert (
        m.source_visibility.bounds[1] + 606
        < before.posts[0].media[0].visibility.bounds[3]
    )
    assert all(v.bounds[1] + 606 > 2340 for v in m.source_content)
    if mutation == "early_credit":
        v = m.source_content[0]
        m = replace(
            m,
            source_content=(
                replace(v, bounds=(209, 1720, 253, 1764)),
                *m.source_content[1:],
            ),
        )
    elif mutation == "missing_credit_bounds":
        m = replace(m, source_visibility=None)
    elif mutation == "missing_credit_content":
        m = replace(m, source_content=())
    elif mutation == "credit_outside":
        m = replace(
            m,
            source_visibility=replace(
                m.source_visibility, bounds=(198, 1600, 569, 1700)
            ),
        )
    elif mutation == "video":
        m = replace(m, visibility=replace(m.visibility, bounds=(176, 538, 1047, 1835)))
    elif mutation == "early_quote":
        q = p.quoted_post
        p = replace(
            p,
            quoted_post=replace(
                q, visibility=replace(q.visibility, bounds=(176, 1500, 1047, 2340))
            ),
        )
    elif mutation == "ambiguous":
        before = replace(before, posts=before.posts * 2)
    after = replace(after, fragments=(replace(p, media=(m,)),))
    with pytest.raises(XError):
        _alignment(before, after, scrolling=mutation != "uncommanded")
