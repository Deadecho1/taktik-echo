"""Outer text leaves while a retained quoted body reveals its article card."""

from dataclasses import replace

import pytest
from unit.paths import CORE

from taktik.core.social_media.x.services.browsing.navigation import XError, _alignment
from taktik.core.social_media.x.ui.screen import PostFragment, read_screen

FIXTURES = CORE / "tests/unit/social_media/x/fixtures"


def screens(family="quote-body-preview"):
    return [
        read_screen((FIXTURES / f"{family}-{stage}.xml").read_bytes(), (1080, 2340))
        for stage in ("before", "after")
    ]


@pytest.fixture(params=["quote-body-preview", "quoted-video-inset"])
def captured_screens(request):
    return screens(request.param)


def test_lost_body_and_new_preview_use_retained_quote_and_video_movement(
    captured_screens,
):
    before, after = captured_screens

    assert _alignment(before, after, scrolling=True) == (1, True)
    assert not before.observable_posts and not after.observable_posts
    fragment = after.fragments[0]
    assert fragment.body is None and not hasattr(fragment, "author")
    quote = fragment.quoted_post
    assert quote.author == "@fixture_quoted"
    assert quote.body == "Fixture quoted body with a later article."
    assert quote.body_complete
    assert quote.media[0].description == "Fixture article title"
    assert _alignment(after, after) == (0, False)
    assert _alignment(after, after, scrolling=True) == (0, False)


def test_previous_outer_header_loss_does_not_change_the_required_evidence(
    captured_screens,
):
    before, after = captured_screens
    old = before.posts[0]
    fragment = PostFragment(
        old.body,
        old.media,
        old.visibility,
        old.body_visibility,
        old.actions,
        quoted_post=old.quoted_post,
    )

    assert _alignment(
        replace(before, posts=(), fragments=(fragment,)), after, scrolling=True
    ) == (0, True)


@pytest.mark.parametrize(
    "mutation",
    [
        "body_still_visible",
        "header_still_visible",
        "replacement_body",
        "body_annotation",
        "outer_translation",
        "quote_author",
        "quote_body",
        "quote_translation",
        "quote_label",
        "quote_body_width",
        "quote_body_shift",
        "quote_header_width",
        "quote_header_height",
        "quote_header_hidden",
        "quote_header_covered",
        "unclipped_quote",
        "visible_preview",
        "preview_width",
        "visible_title",
        "missing_title_geometry",
        "known_preview",
        "video_description",
        "video_source",
        "video_prefix",
        "video_width",
        "video_bottom",
        "missing_video",
        "duplicate_before",
        "duplicate_after",
    ],
)
def test_revelation_preserves_projected_loss_content_geometry_and_uniqueness(
    mutation, captured_screens
):
    before, after = captured_screens
    old, new = before.posts[0], after.fragments[0]
    quote, preview = new.quoted_post, new.quoted_post.media[0]
    if mutation in {"body_still_visible", "header_still_visible"}:
        field = (
            "body_visibility" if mutation.startswith("body") else "header_visibility"
        )
        view = getattr(old, field)
        old = replace(old, **{field: replace(view, bounds=(176, 179, 1047, 800))})
    elif mutation == "replacement_body":
        new = replace(new, body="Replacement", body_visibility=old.body_visibility)
    elif mutation == "body_annotation":
        new = replace(new, body_annotations=("Changed",))
    elif mutation == "outer_translation":
        new = replace(new, translation="Translated from Chinese")
    elif mutation in {"quote_author", "quote_body", "quote_translation"}:
        quote = replace(quote, **{mutation.removeprefix("quote_"): "Changed"})
    elif mutation == "quote_label":
        quote = replace(quote, labels=("Changed",))
    elif mutation in {"quote_body_width", "quote_body_shift"}:
        x1, y1, x2, y2 = quote.body_visibility.bounds
        rect = (
            (x1 + 20, y1, x2, y2)
            if mutation.endswith("width")
            else (x1, y1 + 20, x2, y2)
        )
        quote = replace(
            quote, body_visibility=replace(quote.body_visibility, bounds=rect)
        )
    elif mutation in {"quote_header_width", "quote_header_height"}:
        x1, y1, x2, y2 = quote.header_visibility.bounds
        rect = (
            (x1 + 20, y1, x2, y2)
            if mutation.endswith("width")
            else (x1, y1, x2, y2 + 20)
        )
        quote = replace(
            quote, header_visibility=replace(quote.header_visibility, bounds=rect)
        )
    elif mutation == "quote_header_hidden":
        quote = replace(
            quote,
            header_visibility=replace(quote.header_visibility, visible_bounds=None),
        )
    elif mutation == "quote_header_covered":
        previous = old.quoted_post
        old = replace(
            old,
            quoted_post=replace(
                previous,
                header_visibility=replace(
                    previous.header_visibility,
                    overlaps=(previous.header_visibility.bounds,),
                ),
            ),
        )
    elif mutation == "unclipped_quote":
        previous = old.quoted_post
        old = replace(
            old,
            quoted_post=replace(
                previous,
                visibility=replace(
                    previous.visibility, visible_bounds=previous.visibility.bounds
                ),
            ),
        )
    elif mutation in {"visible_preview", "preview_width"}:
        x1, y1, x2, y2 = preview.visibility.bounds
        rect = (
            (x1, 1700, x2, y2)
            if mutation == "visible_preview"
            else (x1 + 20, y1, x2, y2)
        )
        preview = replace(preview, visibility=replace(preview.visibility, bounds=rect))
    elif mutation in {"visible_title", "missing_title_geometry"}:
        view = (
            None
            if mutation == "missing_title_geometry"
            else replace(preview.description_visibility, bounds=(209, 1700, 1014, 1800))
        )
        preview = replace(preview, description_visibility=view)
    elif mutation == "known_preview":
        old = replace(
            old,
            quoted_post=replace(
                old.quoted_post,
                media=(replace(preview, description="Previously known title"),),
            ),
        )
    elif mutation.startswith("video_"):
        video = new.media[0]
        if mutation in {"video_description", "video_source", "video_prefix"}:
            field = {
                "video_description": "description",
                "video_source": "source_label",
                "video_prefix": "source_prefix",
            }[mutation]
            video = replace(video, **{field: "Changed"})
        else:
            x1, y1, x2, y2 = video.visibility.bounds
            rect = (
                (x1 + 20, y1, x2, y2)
                if mutation == "video_width"
                else (x1, y1, x2, y2 + 20)
            )
            video = replace(video, visibility=replace(video.visibility, bounds=rect))
        new = replace(new, media=(video,))
    elif mutation == "missing_video":
        new = replace(new, media=())
    new = replace(new, quoted_post=replace(quote, media=(preview,)))
    before = replace(
        before, posts=(old,) * (2 if mutation == "duplicate_before" else 1)
    )
    after = replace(
        after, fragments=(new,) * (2 if mutation == "duplicate_after" else 1)
    )

    with pytest.raises(XError, match="uniquely"):
        _alignment(before, after, scrolling=True)


def test_revelation_outside_a_gesture_cannot_refresh_account_verification(
    captured_screens,
):
    with pytest.raises(XError, match="outside adapter scrolling"):
        _alignment(*captured_screens)
