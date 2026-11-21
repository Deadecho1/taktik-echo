from dataclasses import replace

import pytest
from unit.paths import CORE

from taktik.core.social_media.x.services.browsing.navigation import XError, _alignment
from taktik.core.social_media.x.ui.screen import read_screen

FIXTURES = CORE / "tests/unit/social_media/x/fixtures"


def screens():
    return tuple(
        read_screen((FIXTURES / f"quote-summary-{stage}.xml").read_text(), (1080, 2340))
        for stage in ("before", "after")
    )


def test_quote_title_remains_while_its_summary_enters_below_the_old_capture():
    before, after = screens()
    assert not before.posts[0].observable
    assert _alignment(before, after, scrolling=True) == (1, True)
    assert not after.observable_posts


@pytest.mark.parametrize(
    "field",
    [
        "title",
        "summary_top",
        "title_top",
        "source",
        "labels",
        "video_bottom",
        "video_source",
        "header_height",
        "body",
    ],
)
def test_summary_revelation_requires_stable_content_and_independent_geometry(field):
    before, after = screens()
    (fragment,) = after.fragments
    quote = fragment.quoted_post
    (media,) = quote.media
    if field == "title":
        media = replace(media, description="Changed")
    elif field == "source":
        media = replace(media, source_label="Changed")
    elif field in {"summary_top", "title_top"}:
        name = (
            "preview_text_visibility"
            if field == "summary_top"
            else "description_visibility"
        )
        view = getattr(media, name)
        x1, y1, x2, y2 = view.bounds
        media = replace(media, **{name: replace(view, bounds=(x1, y1 - 20, x2, y2))})
    elif field == "labels":
        quote = replace(quote, labels=("Changed",))
    elif field == "header_height":
        view = quote.header_visibility
        x1, y1, x2, y2 = view.bounds
        quote = replace(
            quote, header_visibility=replace(view, bounds=(x1, y1, x2, y2 + 20))
        )
    elif field == "body":
        fragment = replace(fragment, body="Changed")
    else:
        (video,) = fragment.media
        if field == "video_source":
            video = replace(video, source_label="Changed")
        else:
            x1, y1, x2, y2 = video.visibility.bounds
            video = replace(
                video,
                visibility=replace(video.visibility, bounds=(x1, y1, x2, y2 + 20)),
            )
        fragment = replace(fragment, media=(video,))
    quote = replace(quote, media=(media,))
    after = replace(after, fragments=(replace(fragment, quoted_post=quote),))
    with pytest.raises(XError):
        _alignment(before, after, scrolling=True)
