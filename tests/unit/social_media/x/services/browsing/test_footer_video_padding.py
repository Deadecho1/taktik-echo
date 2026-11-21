"""Video touch padding may disappear under its retained complete action row."""

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
        read_screen(document(f"footer-video-padding-{s}"), (1080, 2340))
        for s in ("before", "after")
    )


def test_video_padding_covered_by_its_footer_does_not_erase_neighbor_continuity():
    before, after = screens()
    assert _alignment(before, after, scrolling=True) == (0, True)
    assert after.fragments[0].body is None and not after.fragments[0].media


@pytest.mark.parametrize(
    "mutation", ["no_neighbor", "uncovered_padding", "wrong_cover", "no_visible_extent"]
)
def test_padding_loss_requires_actual_footer_coverage_and_independent_content(mutation):
    before, after = screens()
    (old,) = before.fragments
    (video,) = old.media
    if mutation == "no_neighbor":
        before = replace(before, posts=())
        after = replace(after, posts=())
    elif mutation == "uncovered_padding":
        x1, y1, x2, _ = video.visibility.bounds
        video = replace(
            video, visibility=replace(video.visibility, bounds=(x1, y1, x2, 900))
        )
    elif mutation == "wrong_cover":
        x1, y1, x2, y2 = video.visibility.visible_bounds
        video = replace(
            video,
            visibility=replace(video.visibility, visible_bounds=(x1, y1, x2, y2 - 20)),
        )
    else:
        video = replace(
            video, visibility=replace(video.visibility, visible_bounds=None)
        )
    before = replace(before, fragments=(replace(old, media=(video,)),))
    with pytest.raises(XError):
        _alignment(before, after, scrolling=True)
