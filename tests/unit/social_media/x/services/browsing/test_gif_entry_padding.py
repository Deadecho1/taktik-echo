"""Native GIF entry is anchored by retained text despite clipped-container padding."""

from dataclasses import replace

import pytest
from unit.paths import CORE
from unit.x_fixtures import xml_fixture

from taktik.core.social_media.x.services.browsing.navigation import XError, _alignment
from taktik.core.social_media.x.ui.screen import read_screen


def document(name):
    return xml_fixture(CORE / "tests/unit/social_media/x/fixtures" / f"{name}.xml")


def screens():
    return tuple(
        read_screen(document(f"gif-entry-padding-{s}"), (1080, 2340))
        for s in ("before", "after")
    )


def test_native_gif_and_body_padding_preserve_independent_neighbor_motion():
    before, after = screens()
    assert (
        before.posts[0].body_visibility.bounds[3] < before.posts[0].visibility.bounds[3]
    )
    assert after.posts[0].media[0].kind == "gif"
    assert _alignment(before, after, scrolling=True) == (0, True)


@pytest.mark.parametrize(
    "mutation",
    [
        "body",
        "header",
        "early_media",
        "gif_label",
        "unclipped_body",
        "body_overflow",
        "missing_neighbor",
        "uncommanded",
    ],
)
def test_gif_entry_requires_exact_text_native_media_and_preexisting_anchors(mutation):
    before, after = screens()
    p = after.posts[0]
    if mutation == "body":
        p = replace(p, body="Changed", content_key="changed")
    elif mutation == "header":
        p = replace(
            p,
            header_visibility=replace(
                p.header_visibility, bounds=(176, 1200, 876, 1249)
            ),
        )
    elif mutation == "early_media":
        m = p.media[0]
        p = replace(
            p,
            media=(
                replace(
                    m, visibility=replace(m.visibility, bounds=(176, 1720, 1047, 2340))
                ),
            ),
        )
    elif mutation == "gif_label":
        p = replace(p, media=(replace(p.media[0], description="Video"),))
    elif mutation in {"unclipped_body", "body_overflow"}:
        old = before.posts[0]
        end = 2220 if mutation == "unclipped_body" else 2360
        old = replace(
            old,
            body_visibility=replace(old.body_visibility, bounds=(176, 1846, 1047, end)),
        )
        before = replace(before, posts=(old,))
    after = replace(after, posts=(p,))
    if mutation == "missing_neighbor":
        before, after = replace(before, posts=()), replace(after, posts=())
    with pytest.raises(XError):
        _alignment(before, after, scrolling=mutation != "uncommanded")
