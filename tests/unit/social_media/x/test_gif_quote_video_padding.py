"""GIF quote entry and preceding captionless video wrapper padding."""

from dataclasses import replace
from pathlib import Path

import pytest
from lxml import etree

from taktik.core.social_media.x.services.browsing.navigation import XError, _alignment
from taktik.core.social_media.x.ui.screen import read_screen


def document(name):
    return (Path(__file__).with_name("fixtures") / f"{name}.xml").read_text()


def screen(stage):
    return read_screen(document(f"gif-quote-video-padding-{stage}"), (1080, 2340))


def test_captionless_video_stays_unattributed_while_gif_retains_its_kind():
    before, after = screen("before"), screen("after")
    assert after.fragments[0].media[0].kind == "video"
    assert not hasattr(after.fragments[0], "author")
    assert after.posts[0].media[0].kind == "gif"
    assert after.posts[0].quoted_post is not None
    assert _alignment(before, after, scrolling=True) == (1, True)


def test_captionless_video_tail_requires_projected_author_header_loss():
    before, after = screen("before"), screen("after")
    old = before.posts[0]
    old = replace(
        old,
        header_visibility=replace(old.header_visibility, bounds=(176, 513, 876, 600)),
    )
    before = replace(before, posts=(old, *before.posts[1:]))
    with pytest.raises(XError):
        _alignment(before, after, scrolling=True)


@pytest.mark.parametrize("mutation", ["width", "footer_gap", "footer_overlap"])
def test_video_prefix_requires_exact_wrapper_or_covered_padding(mutation):
    root = etree.fromstring(document("gif-quote-video-padding-after").encode())
    wrapper = root.xpath('//*[@bounds="[0,36][1080,823]"]')[0][3]
    wrapper.set(
        "bounds",
        {
            "width": "[180,147][1047,705]",
            "footer_gap": "[176,147][1047,700]",
            "footer_overlap": "[176,147][1047,730]",
        }[mutation],
    )
    assert not read_screen(etree.tostring(root), (1080, 2340)).fragments


@pytest.mark.parametrize(
    "mutation", ["kind", "body", "movement", "early_quote", "uncommanded"]
)
def test_gif_quote_entry_retains_identity_and_measured_motion(mutation):
    before, after = screen("before"), screen("after")
    p = after.posts[0]
    if mutation == "kind":
        p = replace(p, media=(replace(p.media[0], kind="video"),))
    elif mutation == "body":
        p = replace(p, body="Different body")
    elif mutation == "movement":
        m = p.media[0]
        p = replace(
            p,
            media=(
                replace(
                    m, visibility=replace(m.visibility, bounds=(176, 963, 1047, 1854))
                ),
            ),
        )
    elif mutation == "early_quote":
        q = p.quoted_post
        p = replace(
            p,
            quoted_post=replace(
                q, visibility=replace(q.visibility, bounds=(176, 1776, 1047, 2173))
            ),
        )
    after = replace(after, posts=(p,))
    with pytest.raises(XError):
        _alignment(before, after, scrolling=mutation != "uncommanded")
