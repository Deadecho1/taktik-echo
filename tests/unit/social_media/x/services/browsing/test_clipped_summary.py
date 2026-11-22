from dataclasses import replace

import pytest
from unit.paths import CORE
from unit.x_fixtures import xml_fixture

from taktik.core.social_media.x.services.browsing.navigation import (
    XError,
    _alignment,
)
from taktik.core.social_media.x.ui.screen import read_screen

FIXTURES = CORE / "tests/unit/social_media/x/fixtures"


def document(name):
    return xml_fixture(FIXTURES / f"{name}.xml")


def screens():
    return tuple(
        read_screen(document(f"clipped-summary-{stage}"), (1080, 2340))
        for stage in ("before", "after")
    )


def test_clipped_title_completion_keeps_independent_quote_and_video_movement():
    before, after = screens()
    assert _alignment(before, after, scrolling=True) == (0, True)


@pytest.mark.parametrize(
    "mutation",
    ["video_top", "video_bottom", "title_top", "not_clipped", "title", "header"],
)
def test_clipped_summary_still_rejects_contradictory_geometry(mutation):
    before, after = screens()
    (old,) = before.fragments
    (new,) = after.fragments
    if mutation.startswith("video_"):
        (video,) = new.media
        rect = list(video.visibility.bounds)
        rect[1 if mutation == "video_top" else 3] += 20
        new = replace(
            new,
            media=(
                replace(
                    video, visibility=replace(video.visibility, bounds=tuple(rect))
                ),
            ),
        )
    elif mutation == "header":
        quote = new.quoted_post
        rect = list(quote.header_visibility.bounds)
        rect[3] += 20
        new = replace(
            new,
            quoted_post=replace(
                quote,
                header_visibility=replace(quote.header_visibility, bounds=tuple(rect)),
            ),
        )
    elif mutation == "not_clipped":
        quote = old.quoted_post
        (media,) = quote.media
        old = replace(
            old,
            quoted_post=replace(
                quote,
                media=(
                    replace(
                        media,
                        description_visibility=replace(
                            media.description_visibility, clipped=False
                        ),
                    ),
                ),
            ),
        )
    else:
        quote = new.quoted_post
        (media,) = quote.media
        if mutation == "title":
            media = replace(media, description="Changed")
        else:
            rect = list(media.description_visibility.bounds)
            rect[1] += 20
            media = replace(
                media,
                description_visibility=replace(
                    media.description_visibility, bounds=tuple(rect)
                ),
            )
        new = replace(new, quoted_post=replace(quote, media=(media,)))
    with pytest.raises(XError):
        _alignment(
            replace(before, fragments=(old,)),
            replace(after, fragments=(new,)),
            scrolling=True,
        )
