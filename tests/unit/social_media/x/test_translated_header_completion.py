"""An offscreen quote header can reveal translated text under a covered author."""

from dataclasses import replace
from pathlib import Path

import pytest
from lxml import etree
from taktik.core.social_media.x.services.browsing.navigation import XError, _alignment
from taktik.core.social_media.x.ui.screen import read_screen


def document(name):
    return (Path(__file__).parent / "fixtures" / f"{name}.xml").read_text()


def screens():
    return tuple(
        read_screen(document(f"translated-header-completion-{s}"), (1080, 2340))
        for s in ("before", "after")
    )


def test_quote_translation_enters_beyond_the_old_capture():
    before, after = screens()
    old, new = before.posts[0], after.fragments[0]
    assert old.quoted_post.body is None
    assert old.quoted_post.translation is None
    assert new.quoted_post.translation == "Translated from Indonesian"
    assert new.quoted_post.translation_visibility.bounds == (283, 1740, 725, 1783)
    assert not hasattr(new, "author")
    assert new.covered_handle.text == old.author
    assert _alignment(before, after, scrolling=True) == (1, True)


@pytest.mark.parametrize(
    "mutation",
    [
        "early_label",
        "missing_geometry",
        "old_translation",
        "handle",
        "media_motion",
        "uncommanded",
    ],
)
def test_translation_revelation_requires_independent_motion_and_prior_absence(mutation):
    before, after = screens()
    p = after.fragments[0]
    q = p.quoted_post
    if mutation == "early_label":
        q = replace(
            q,
            translation_visibility=replace(
                q.translation_visibility, bounds=(283, 1700, 725, 1743)
            ),
        )
    elif mutation == "missing_geometry":
        q = replace(q, translation_visibility=None)
    elif mutation == "old_translation":
        old = before.posts[0]
        before = replace(
            before,
            posts=(
                replace(
                    old,
                    quoted_post=replace(
                        old.quoted_post, translation="Translated from French"
                    ),
                ),
            ),
        )
    elif mutation == "handle":
        p = replace(p, covered_handle=replace(p.covered_handle, text="@changed"))
    elif mutation == "media_motion":
        m = p.media[0]
        p = replace(
            p,
            media=(
                replace(
                    m, visibility=replace(m.visibility, bounds=(176, 341, 1047, 1648))
                ),
            ),
        )
    after = replace(after, fragments=(replace(p, quoted_post=q),))
    with pytest.raises(XError):
        _alignment(before, after, scrolling=mutation != "uncommanded")


@pytest.mark.parametrize(
    "mutation", ["no_cover", "interactive", "overlap_name", "no_prefix"]
)
def test_unbadged_partial_handle_still_requires_exact_native_cover(mutation):
    root = etree.fromstring(document("translated-header-completion-after").encode())
    handle = root.xpath('//*[@resource-id="timeline_post"]')[0][-1]
    if mutation == "no_cover":
        n = root.xpath('//*[@resource-id="ntp"]')[0]
        n.getparent().remove(n)
    elif mutation == "interactive":
        handle.set("clickable", "true")
    else:
        handle.set(
            "bounds",
            "[230,194][389,243]"
            if mutation == "overlap_name"
            else "[389,194][400,243]",
        )
    after = read_screen(etree.tostring(root), (1080, 2340))
    assert not after.fragments
