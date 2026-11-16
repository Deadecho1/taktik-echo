"""GIF padding covered by its footer cannot obscure independent post movement."""

from dataclasses import replace
from pathlib import Path

import pytest
from taktik.core.social_media.x.services.browsing.navigation import XError, _alignment
from taktik.core.social_media.x.ui.screen import read_screen


def document(name):
    return (Path(__file__).with_name("fixtures") / f"{name}.xml").read_text()


def screen(stage):
    return read_screen(document(f"footer-gif-padding-{stage}"), (1080, 2340))


def test_gif_retains_its_kind_until_only_the_covered_footer_remains():
    before, after = screen("before"), screen("after")
    assert before.fragments[0].media[0].kind == "gif"
    assert not after.fragments[0].media
    assert _alignment(before, after, scrolling=True) == (0, True)


@pytest.mark.parametrize(
    "mutation",
    [
        "no_neighbor",
        "uncovered_padding",
        "wrong_cover",
        "no_visible_extent",
        "footer_count",
        "footer_motion",
        "unknown_kind",
        "uncommanded",
    ],
)
def test_gif_loss_requires_coverage_and_independent_commanded_movement(mutation):
    before, after = screen("before"), screen("after")
    old = before.fragments[0]
    media = old.media[0]
    if mutation == "no_neighbor":
        before, after = replace(before, posts=()), replace(after, posts=())
    elif mutation == "uncovered_padding":
        x1, y1, x2, _ = media.visibility.bounds
        media = replace(
            media, visibility=replace(media.visibility, bounds=(x1, y1, x2, 900))
        )
    elif mutation == "wrong_cover":
        x1, y1, x2, y2 = media.visibility.visible_bounds
        media = replace(
            media,
            visibility=replace(media.visibility, visible_bounds=(x1, y1, x2, y2 - 20)),
        )
    elif mutation == "no_visible_extent":
        media = replace(
            media, visibility=replace(media.visibility, visible_bounds=None)
        )
    elif mutation == "unknown_kind":
        media = replace(media, kind="unknown")
    elif mutation in {"footer_count", "footer_motion"}:
        current = after.fragments[0]
        action = current.actions[0]
        if mutation == "footer_count":
            action = replace(action, count="500")
        else:
            x1, y1, x2, y2 = action.visibility.bounds
            action = replace(
                action,
                visibility=replace(action.visibility, bounds=(x1, y1, x2, y2 + 20)),
            )
        after = replace(
            after, fragments=(replace(current, actions=(action, *current.actions[1:])),)
        )
    before = replace(before, fragments=(replace(old, media=(media,)),))
    with pytest.raises(XError):
        _alignment(before, after, scrolling=mutation != "uncommanded")
