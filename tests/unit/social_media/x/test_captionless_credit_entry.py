"""A newly entering video credit needs prior author and independent motion."""

from dataclasses import replace
from pathlib import Path

import pytest
from taktik.core.social_media.x.services.browsing.navigation import XError, _alignment
from taktik.core.social_media.x.ui.screen import read_screen


def document(name):
    return (Path(__file__).with_name("fixtures") / f"{name}.xml").read_text()


def screen(stage):
    return read_screen(document(f"captionless-credit-entry-{stage}"), (1080, 2340))


def test_credit_entry_keeps_distinct_observation_identity():
    before, after = screen("before"), screen("after")
    assert before.posts[0].body is None and after.posts[0].body is None
    assert before.posts[0].content_key != after.posts[0].content_key
    assert before.posts[0].media[0].source_label is None
    assert after.posts[0].media[0].source_label
    assert _alignment(before, after, scrolling=True) == (0, True)


@pytest.mark.parametrize(
    "mutation",
    [
        "author",
        "body",
        "translation",
        "header_motion",
        "video_motion",
        "video_width",
        "early_credit",
        "missing_credit_geometry",
        "previous_credit",
        "uncommanded",
    ],
)
def test_credit_revelation_requires_prior_content_and_projected_entry(mutation):
    before, after = screen("before"), screen("after")
    old, new = before.posts[0], after.posts[0]
    media = new.media[0]
    if mutation == "author":
        new = replace(new, author="@different")
    elif mutation == "body":
        new = replace(new, body="Unexpected body")
    elif mutation == "translation":
        new = replace(new, translation="Translated from French")
    elif mutation == "header_motion":
        v = new.header_visibility
        x1, y1, x2, y2 = v.bounds
        new = replace(new, header_visibility=replace(v, bounds=(x1, y1, x2, y2 + 20)))
    elif mutation in {"video_motion", "video_width"}:
        v = media.visibility
        x1, y1, x2, y2 = v.bounds
        media = replace(
            media,
            visibility=replace(
                v,
                bounds=(
                    x1 + (20 if mutation == "video_width" else 0),
                    y1 + (20 if mutation == "video_motion" else 0),
                    x2,
                    y2,
                ),
            ),
        )
    elif mutation == "early_credit":
        media = replace(
            media,
            source_visibility=replace(
                media.source_visibility, bounds=(198, 1600, 548, 1702)
            ),
            source_content=(),
        )
    elif mutation == "missing_credit_geometry":
        media = replace(media, source_visibility=None, source_content=())
    elif mutation == "previous_credit":
        old = replace(
            old, media=(replace(old.media[0], source_label="Different source"),)
        )
    new = replace(new, media=(media,))
    before = replace(before, posts=(old,))
    after = replace(after, posts=(new, *after.posts[1:]))
    with pytest.raises(XError):
        _alignment(before, after, scrolling=mutation != "uncommanded")
