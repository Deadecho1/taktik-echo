"""A quoted title can appear before the outer header leaves the hierarchy."""

from dataclasses import replace
from pathlib import Path

import pytest
from taktik.core.social_media.x.services.browsing.navigation import XError, _alignment
from taktik.core.social_media.x.ui.screen import read_screen

FIXTURES = Path(__file__).with_name("fixtures")


def document(name):
    return (FIXTURES / f"{name}.xml").read_text()


def screens():
    return tuple(
        read_screen(document(f"retained-author-preview-{s}"), (1080, 2340))
        for s in ("before", "after")
    )


def test_retained_author_and_quote_geometry_establish_the_new_title():
    before, after = screens()
    assert _alignment(before, after, scrolling=True) == (0, True)
    assert before.posts[0].author == after.posts[0].author
    assert not after.observable_posts


@pytest.mark.parametrize(
    "mutation", ["author", "body", "header", "video", "early_title"]
)
def test_retained_author_does_not_bypass_attribution_or_independent_motion(mutation):
    before, after = screens()
    (post,) = after.posts
    if mutation == "author":
        post = replace(post, author="@different")
    elif mutation == "body":
        post = replace(post, body="Changed")
    elif mutation == "video":
        (video,) = post.media
        x1, y1, x2, y2 = video.visibility.bounds
        post = replace(
            post,
            media=(
                replace(
                    video,
                    visibility=replace(video.visibility, bounds=(x1, y1, x2, y2 + 20)),
                ),
            ),
        )
    else:
        quote = post.quoted_post
        if mutation == "header":
            view = quote.header_visibility
            x1, y1, x2, y2 = view.bounds
            quote = replace(
                quote, header_visibility=replace(view, bounds=(x1, y1, x2, y2 + 20))
            )
        else:
            (preview,) = quote.media
            view = preview.description_visibility
            x1, _, x2, y2 = view.bounds
            preview = replace(
                preview, description_visibility=replace(view, bounds=(x1, 1000, x2, y2))
            )
            quote = replace(quote, media=(preview,))
        post = replace(post, quoted_post=quote)
    with pytest.raises(XError):
        _alignment(before, replace(after, posts=(post,)), scrolling=True)
