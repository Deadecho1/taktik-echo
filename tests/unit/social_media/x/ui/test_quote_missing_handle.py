"""Native long-name quotes can omit their handle but cannot become observations."""

from dataclasses import replace

import pytest
from lxml import etree
from unit.paths import CORE

from taktik.core.social_media.x.services.browsing.browser import post_context
from taktik.core.social_media.x.services.browsing.navigation import XError, _alignment
from taktik.core.social_media.x.ui.screen import read_screen


def document(name):
    return (CORE / "tests/unit/social_media/x/fixtures" / f"{name}.xml").read_text()


def screen(stage):
    return read_screen(document(f"quote-missing-handle-{stage}"), (1080, 2340))


def test_missing_quote_handle_stays_unknown_and_unobservable():
    p = screen("after").posts[0]
    q = p.quoted_post
    assert q.author is None
    assert q.display_name
    assert q.body
    assert not q.observable and not p.observable
    assert post_context(p)["quoted_post"]["username"] is None
    assert _alignment(screen("before"), screen("after"), scrolling=True) == (0, True)


def test_unknown_author_blocks_observation_even_when_all_quote_content_is_clear():
    p = screen("after").posts[0]
    q = p.quoted_post

    def clear(v):
        return replace(v, visible_bounds=v.bounds, overlaps=(), clipped=False)

    q = replace(
        q,
        header_visibility=clear(q.header_visibility),
        body_visibility=clear(q.body_visibility),
        media=tuple(replace(m, visibility=clear(m.visibility)) for m in q.media),
    )
    assert not q.observable


@pytest.mark.parametrize(
    "mutation",
    [
        "name",
        "age",
        "badge",
        "badge_control",
        "name_control",
        "disabled",
        "age_edge",
        "height",
        "order",
    ],
)
def test_missing_handle_requires_the_native_name_badge_age_arrangement(mutation):
    root = etree.fromstring(document("quote-missing-handle-after").encode())
    card = root.xpath('//*[@content-desc="Quote"]')[0].getparent()
    name, badge, age = list(card)[1:4]
    if mutation == "name":
        name.set("text", "@partial...")
    elif mutation == "age":
        age.set("text", "Unknown")
    elif mutation == "badge":
        badge.set("content-desc", "Unknown")
    elif mutation == "badge_control":
        badge.set("clickable", "true")
    elif mutation == "name_control":
        name.set("clickable", "true")
    elif mutation == "disabled":
        badge.set("enabled", "false")
    elif mutation == "age_edge":
        age.set("bounds", "[950,2041][1020,2090]")
    elif mutation == "height":
        age.set("bounds", "[956,2037][1026,2090]")
    else:
        name.addprevious(age)
    assert not read_screen(etree.tostring(root), (1080, 2340)).posts


@pytest.mark.parametrize(
    "mutation",
    [
        "name",
        "labels",
        "invented_handle",
        "body",
        "video_motion",
        "early_quote",
        "uncommanded",
    ],
)
def test_unattributed_quote_requires_stable_context_and_commanded_entry(mutation):
    before, after = screen("before"), screen("after")
    p = after.posts[0]
    q = p.quoted_post
    if mutation in {"name", "labels", "invented_handle"}:
        before = after
        q = replace(
            q,
            **{
                "name": {"display_name": "Different name"},
                "labels": {"labels": ()},
                "invented_handle": {"author": "@invented"},
            }[mutation],
        )
        p = replace(p, quoted_post=q)
    elif mutation == "body":
        p = replace(p, body="Different outer body")
    elif mutation == "video_motion":
        m = p.media[0]
        p = replace(
            p,
            media=(
                replace(
                    m, visibility=replace(m.visibility, bounds=(176, 700, 1047, 1994))
                ),
            ),
        )
    elif mutation == "early_quote":
        p = replace(
            p,
            quoted_post=replace(
                q, visibility=replace(q.visibility, bounds=(176, 1700, 1047, 2313))
            ),
        )
    after = replace(after, posts=(p,))
    with pytest.raises(XError):
        _alignment(
            before,
            after,
            scrolling=mutation
            not in {"name", "labels", "invented_handle", "uncommanded"},
        )
