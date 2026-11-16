"""A clipped video may reveal its native source credit and a quote together."""

from dataclasses import replace
from pathlib import Path

import pytest
from taktik.core.social_media.x.services.browsing.navigation import XError, _alignment
from taktik.core.social_media.x.ui.screen import read_screen


def document(name):
    return (Path(__file__).parent / "fixtures" / f"{name}.xml").read_text()


def screens():
    return tuple(
        read_screen(document(f"video-credit-quote-entry-{s}"), (1080, 2340))
        for s in ("before", "after")
    )


def test_credit_and_quote_enter_below_the_prior_capture():
    before, after = screens()
    old, new = before.posts[0].media[0], after.posts[0].media[0]
    assert old.source_label is None and old.source_visibility is None
    assert new.source_label and new.source_visibility
    assert new.source_visibility.bounds[1] + 596 >= old.visibility.bounds[3]
    assert before.posts[0].quoted_post is None
    assert after.posts[0].quoted_post is not None
    assert _alignment(before, after, scrolling=True) == (0, True)


@pytest.mark.parametrize(
    "mutation",
    [
        "early_credit",
        "missing_geometry",
        "changed_credit",
        "old_prefix",
        "video_motion",
        "early_quote",
        "uncommanded",
    ],
)
def test_credit_entry_requires_prior_absence_and_projected_native_geometry(mutation):
    before, after = screens()
    p = after.posts[0]
    m = p.media[0]
    if mutation == "early_credit":
        m = replace(
            m,
            source_visibility=replace(
                m.source_visibility, bounds=(198, 1700, 600, 1770)
            ),
        )
    elif mutation == "missing_geometry":
        m = replace(m, source_visibility=None)
    elif mutation in {"changed_credit", "old_prefix"}:
        old = before.posts[0]
        old_m = (
            replace(old.media[0], source_label="Different source")
            if mutation == "changed_credit"
            else replace(old.media[0], source_prefix="Clip from")
        )
        before = replace(before, posts=(replace(old, media=(old_m,)),))
    elif mutation == "video_motion":
        m = replace(m, visibility=replace(m.visibility, bounds=(176, 936, 1047, 2077)))
    elif mutation == "early_quote":
        q = p.quoted_post
        p = replace(
            p,
            quoted_post=replace(
                q, visibility=replace(q.visibility, bounds=(176, 1600, 1047, 2340))
            ),
        )
    after = replace(after, posts=(replace(p, media=(m,)),))
    with pytest.raises(XError):
        _alignment(before, after, scrolling=mutation != "uncommanded")
