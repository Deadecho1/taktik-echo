"""Synthetic text on captured geometry, with explicit adversarial mutations."""

from dataclasses import replace
from pathlib import Path

import pytest
from taktik.core.social_media.x.services.browsing.navigation import XError, _alignment
from taktik.core.social_media.x.ui.screen import read_screen

FIXTURES = Path(__file__).parent / "fixtures"


def screens():
    return [
        read_screen(
            (FIXTURES / f"quote-body-loss-{stage}.xml").read_bytes(), (1080, 2340)
        )
        for stage in ("before", "after")
    ]


def test_lost_outer_body_and_new_article_text_use_retained_quote_movement():
    before, after = screens()

    assert _alignment(before, after, scrolling=True) == (0, True)
    assert not after.posts and not after.observable_posts
    fragment = after.fragments[0]
    assert fragment.body is None and not hasattr(fragment, "author")
    quote = fragment.quoted_post
    assert quote.author == "@fixture_author"
    assert quote.body is None
    assert quote.media[0].description == "Fixture article title"
    assert quote.media[0].preview_text == "Fixture article summary"


@pytest.mark.parametrize(
    "mutation",
    [
        "body_still_visible",
        "replacement_body",
        "quote_author",
        "quote_body",
        "quote_translation",
        "quote_label",
        "outer_translation",
        "quote_width",
        "header_height",
        "header_hidden",
        "header_covered",
        "preview_width",
        "preview_shift",
        "known_title",
        "known_summary",
        "visible_title",
        "missing_title_geometry",
        "unclipped_preview",
        "video_description",
        "video_source",
        "video_width",
        "video_bottom",
        "missing_video",
        "duplicate_before",
        "duplicate_after",
        "stationary",
    ],
)
def test_combined_revelation_cannot_bypass_content_geometry_or_ambiguity(mutation):
    before, after = screens()
    old, new = before.fragments[0], after.fragments[0]
    quote, preview = new.quoted_post, new.quoted_post.media[0]
    if mutation == "body_still_visible":
        old = replace(
            old,
            body_visibility=replace(old.body_visibility, bounds=(176, 83, 1047, 800)),
        )
    elif mutation == "replacement_body":
        new = replace(new, body="Unrelated body", body_visibility=old.body_visibility)
    elif mutation in {"quote_author", "quote_body", "quote_translation"}:
        quote = replace(quote, **{mutation.removeprefix("quote_"): "Changed"})
    elif mutation == "quote_label":
        quote = replace(quote, labels=("Changed",))
    elif mutation == "outer_translation":
        new = replace(new, translation="Translated from Chinese")
    elif mutation == "quote_width":
        quote = replace(
            quote,
            header_visibility=replace(
                quote.header_visibility, bounds=(500, 1381, 728, 1430)
            ),
        )
    elif mutation == "header_height":
        quote = replace(
            quote,
            header_visibility=replace(
                quote.header_visibility, bounds=(520, 1381, 728, 1440)
            ),
        )
    elif mutation == "header_hidden":
        quote = replace(
            quote,
            header_visibility=replace(quote.header_visibility, visible_bounds=None),
        )
    elif mutation == "header_covered":
        old = replace(
            old,
            quoted_post=replace(
                old.quoted_post,
                header_visibility=replace(
                    old.quoted_post.header_visibility,
                    overlaps=((520, 1959, 728, 2008),),
                ),
            ),
        )
    elif mutation in {"preview_width", "preview_shift"}:
        rect = (
            (170, 1466, 1047, 2270)
            if mutation == "preview_width"
            else (176, 1476, 1047, 2270)
        )
        preview = replace(preview, visibility=replace(preview.visibility, bounds=rect))
    elif mutation in {"known_title", "known_summary", "unclipped_preview"}:
        previous = old.quoted_post.media[0]
        if mutation == "unclipped_preview":
            previous = replace(
                previous,
                visibility=replace(
                    previous.visibility, visible_bounds=previous.visibility.bounds
                ),
            )
        else:
            previous = replace(
                previous,
                **{
                    "description"
                    if mutation == "known_title"
                    else "preview_text": "Already known"
                },
            )
        old = replace(old, quoted_post=replace(old.quoted_post, media=(previous,)))
    elif mutation in {"visible_title", "missing_title_geometry"}:
        view = (
            None
            if mutation == "missing_title_geometry"
            else replace(preview.description_visibility, bounds=(209, 1700, 1014, 1800))
        )
        preview = replace(preview, description_visibility=view)
    elif mutation.startswith("video_"):
        video = new.media[0]
        if mutation in {"video_description", "video_source"}:
            video = replace(
                video,
                **{
                    "description"
                    if mutation == "video_description"
                    else "source_label": "Changed"
                },
            )
        else:
            rect = (
                (170, 16, 1047, 1323)
                if mutation == "video_width"
                else (176, 16, 1047, 1343)
            )
            video = replace(video, visibility=replace(video.visibility, bounds=rect))
        new = replace(new, media=(video,))
    elif mutation == "missing_video":
        new = replace(new, media=())
    elif mutation == "stationary":
        old = replace(
            new,
            quoted_post=replace(
                new.quoted_post,
                media=(
                    replace(
                        preview,
                        description=None,
                        preview_text=None,
                        description_visibility=None,
                        preview_text_visibility=None,
                    ),
                ),
            ),
        )
    new = replace(new, quoted_post=replace(quote, media=(preview,)))
    before = replace(
        before, fragments=(old,) * (2 if mutation == "duplicate_before" else 1)
    )
    after = replace(
        after, fragments=(new,) * (2 if mutation == "duplicate_after" else 1)
    )

    with pytest.raises(XError, match="uniquely"):
        _alignment(before, after, scrolling=True)


def test_combined_revelation_outside_scrolling_requires_account_reverification():
    with pytest.raises(XError, match="outside adapter scrolling"):
        _alignment(*screens())
