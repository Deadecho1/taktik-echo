"""Captured quote completion while the retained outer body becomes clipped."""

from dataclasses import replace

import pytest
from unit.paths import CORE

from taktik.core.social_media.x.services.browsing.navigation import XError, _alignment
from taktik.core.social_media.x.ui.screen import read_screen

FIXTURES = CORE / "tests/unit/social_media/x/fixtures"


def document(name):
    return (FIXTURES / f"{name}.xml").read_text()


def screens():
    return tuple(
        read_screen(document(f"quote-tail-{stage}"), (1080, 2340))
        for stage in ("before", "after")
    )


def test_quote_completion_retains_body_and_independent_video_header_motion():
    before, after = screens()
    assert not before.posts[-1].observable
    assert _alignment(before, after, scrolling=True) == (1, True)
    assert not after.observable_posts


@pytest.mark.parametrize(
    "mutation", ["body", "video_bottom", "quote_header", "preview_early", "author"]
)
def test_incomplete_quote_does_not_bypass_content_or_motion_proof(mutation):
    before, after = screens()
    (new,) = after.fragments
    if mutation == "body":
        new = replace(new, body="Changed body")
    elif mutation == "video_bottom":
        (video,) = new.media
        x1, y1, x2, y2 = video.visibility.bounds
        new = replace(
            new,
            media=(
                replace(
                    video,
                    visibility=replace(video.visibility, bounds=(x1, y1, x2, y2 + 20)),
                ),
            ),
        )
    else:
        quote = new.quoted_post
        if mutation == "author":
            quote = replace(quote, author="@another_author")
        elif mutation == "quote_header":
            view = quote.header_visibility
            x1, y1, x2, y2 = view.bounds
            quote = replace(
                quote, header_visibility=replace(view, bounds=(x1, y1, x2, y2 + 20))
            )
        else:
            (preview,) = quote.media
            x1, _, x2, y2 = preview.visibility.bounds
            preview = replace(
                preview,
                visibility=replace(preview.visibility, bounds=(x1, 1500, x2, y2)),
            )
            quote = replace(quote, media=(preview,))
        new = replace(new, quoted_post=quote)
    with pytest.raises(XError):
        _alignment(before, replace(after, fragments=(new,)), scrolling=True)
