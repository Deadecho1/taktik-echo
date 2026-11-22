"""Inset video with a retained quote must keep independent movement evidence."""

from dataclasses import replace

import pytest
from lxml import etree
from unit.social_media.x.services.browsing.test_quote_body_preview import (
    FIXTURES,
    screens,
)
from unit.x_fixtures import xml_fixture

from taktik.core.social_media.x.services.browsing.navigation import (
    XError,
    _alignment,
    scroll_region,
)
from taktik.core.social_media.x.ui.screen import read_screen


def test_inset_video_with_quote_supplies_a_scroll_region_without_outer_attribution():
    before, after = screens("quoted-video-inset")
    assert not after.posts and not after.rejected_posts
    fragment = after.fragments[0]
    assert fragment.media[0].visibility.bounds[1] == 137
    assert after.content_viewport[1] == 136
    assert fragment.body is None and not hasattr(fragment, "author")
    assert _alignment(before, after, scrolling=True) == (1, True)
    region, distance, exclusions = scroll_region(after)
    assert distance > 0
    assert region[2] <= fragment.media[0].visibility.bounds[0]
    assert fragment.media[0].visibility.bounds in exclusions


@pytest.mark.parametrize("reveal", [True, False])
@pytest.mark.parametrize("mutation", ["bottom", "source", "prefix", "header", "labels"])
def test_inset_quote_cannot_bypass_geometry_checks_through_unchanged_content(
    reveal, mutation
):
    before, after = screens("quoted-video-inset")
    fragment = after.fragments[0]
    if not reveal:
        fragment = replace(
            fragment, quoted_post=replace(fragment.quoted_post, media=())
        )
    if mutation in {"bottom", "source", "prefix"}:
        video = fragment.media[0]
        if mutation == "bottom":
            x1, y1, x2, y2 = video.visibility.bounds
            video = replace(
                video,
                visibility=replace(video.visibility, bounds=(x1, y1, x2, y2 + 20)),
            )
        else:
            video = replace(
                video,
                **{
                    "source_label"
                    if mutation == "source"
                    else "source_prefix": "Changed"
                },
            )
        fragment = replace(fragment, media=(video,))
    else:
        quote = fragment.quoted_post
        if mutation == "labels":
            quote = replace(quote, labels=("Changed",))
        else:
            x1, y1, x2, y2 = quote.header_visibility.bounds
            quote = replace(
                quote,
                header_visibility=replace(
                    quote.header_visibility, bounds=(x1, y1, x2, y2 + 20)
                ),
            )
        fragment = replace(fragment, quoted_post=quote)

    with pytest.raises(XError, match="uniquely"):
        _alignment(before, replace(after, fragments=(fragment,)), scrolling=True)


@pytest.mark.parametrize("scrolling", [False, True])
@pytest.mark.parametrize("mutation", ["bottom", "source", "header", "labels"])
def test_inset_quote_reread_rejects_uncommanded_changes(scrolling, mutation):
    _, before = screens("quoted-video-inset")
    fragment = before.fragments[0]
    if mutation in {"bottom", "source"}:
        video = fragment.media[0]
        if mutation == "source":
            video = replace(video, source_label="Changed")
        else:
            x1, y1, x2, y2 = video.visibility.bounds
            video = replace(
                video,
                visibility=replace(video.visibility, bounds=(x1, y1, x2, y2 + 20)),
            )
        fragment = replace(fragment, media=(video,))
    else:
        quote = fragment.quoted_post
        if mutation == "labels":
            quote = replace(quote, labels=("Changed",))
        else:
            x1, y1, x2, y2 = quote.header_visibility.bounds
            quote = replace(
                quote,
                header_visibility=replace(
                    quote.header_visibility, bounds=(x1, y1, x2, y2 + 20)
                ),
            )
        fragment = replace(fragment, quoted_post=quote)

    with pytest.raises(XError):
        _alignment(before, replace(before, fragments=(fragment,)), scrolling=scrolling)


@pytest.mark.parametrize(
    "mutation", ["unknown_content", "header", "quote_content", "incomplete_footer"]
)
def test_inset_video_and_quote_require_an_understood_container(mutation):
    root = etree.fromstring(
        xml_fixture(FIXTURES / "quoted-video-inset-after.xml").encode()
    )
    video = root.xpath('//*[@content-desc="Video"]')[0]
    container = video.getparent().getparent()
    quote = root.xpath('//*[@content-desc="Quote"]')[0]
    if mutation == "unknown_content":
        video.getparent().set("content-desc", "Unrecognized content")
    elif mutation == "header":
        video.getparent().set("resource-id", "timeline_post")
    elif mutation == "quote_content":
        quote.set("content-desc", "Unrecognized quote marker")
    else:
        container.set("bounds", "[0,0][1080,2100]")

    after = read_screen(etree.tostring(root), (1080, 2340))

    assert not after.fragments
    assert after.rejected_posts
