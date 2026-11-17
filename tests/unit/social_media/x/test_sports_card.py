"""Native sports results below media are displayed context, not post body."""

from dataclasses import replace
from itertools import pairwise
from pathlib import Path

import pytest
from lxml import etree

from taktik.core.shared.ui.geometry import bounds
from taktik.core.social_media.x.services.browsing.browser import post_context
from taktik.core.social_media.x.services.browsing.navigation import XError, _alignment
from taktik.core.social_media.x.ui.screen import read_screen


def document(name):
    return (Path(__file__).parent / "fixtures" / f"{name}.xml").read_text()


def screen(stage):
    return read_screen(document(f"sports-card-{stage}"), (1080, 2340))


def test_result_card_enters_below_gif_without_changing_post_identity():
    before, after = screen("before"), screen("after")
    p = after.posts[0]
    assert p.content_key == before.posts[0].content_key
    assert p.body == before.posts[0].body
    assert p.sports_card.teams == ("CAR", "NO")
    assert p.sports_card.status == "Final"
    assert post_context(p)["sports_card"]["teams"] == ["CAR", "NO"]
    assert _alignment(before, after, scrolling=True) == (0, True)


def synthetic_sports_screens():
    screens = [replace(screen("after"), fragments=(), rejected_posts=())]
    for travel in (400, 800, 1200):
        root = etree.fromstring(document("sports-card-after").encode())
        card = root.xpath('//*[@text="CAR"]')[0].getparent()
        post = card.getparent()
        for sibling in list(post.getparent()):
            if sibling is not post:
                post.getparent().remove(sibling)
        for child in list(post):
            if bounds(child)[3] - travel <= 136:
                post.remove(child)
        for node in post.iter():
            x1, y1, x2, y2 = bounds(node)
            node.set(
                "bounds", f"[{x1},{max(0, y1 - travel)}][{x2},{max(0, y2 - travel)}]"
            )
        screens.append(read_screen(etree.tostring(root), (1080, 2340)))
    return screens


def test_synthetic_header_and_body_loss_retains_unattributed_sports_card():
    screens = synthetic_sports_screens()
    for before, after in pairwise(screens):
        assert not after.rejected_posts
        assert _alignment(before, after, scrolling=True)[1]
    p = screens[-1].fragments[0]
    assert not hasattr(p, "author")
    assert p.body is None
    assert p.sports_card.teams == screens[0].posts[0].sports_card.teams


def test_sports_card_cannot_justify_a_disjoint_media_jump():
    screens = synthetic_sports_screens()
    with pytest.raises(XError):
        _alignment(screens[0], screens[-1], scrolling=True)


@pytest.mark.parametrize("mutation", ["teams", "status", "motion", "loss"])
def test_sports_tail_requires_retained_context_and_independent_motion(mutation):
    before, after = synthetic_sports_screens()[-2:]
    p = after.fragments[0]
    c = p.sports_card
    if mutation == "teams":
        c = replace(c, teams=("XX", "YY"))
    elif mutation == "status":
        c = replace(c, status="Changed")
    elif mutation == "motion":
        c = replace(c, visibility=replace(c.visibility, bounds=(176, 646, 1047, 743)))
    else:
        c = None
    with pytest.raises(XError):
        _alignment(
            before,
            replace(after, fragments=(replace(p, sports_card=c),)),
            scrolling=True,
        )


@pytest.mark.parametrize(
    "mutation", ["team", "status", "interactive", "outside", "order", "gap"]
)
def test_sports_card_requires_native_labels_and_media_footer_geometry(mutation):
    root = etree.fromstring(document("sports-card-after").encode())
    team = root.xpath('//*[@text="CAR"]')[0]
    card = team.getparent()
    if mutation == "team":
        team.set("text", "Unknown team!")
    elif mutation == "status":
        card[-1].set("text", "Unknown")
    elif mutation == "interactive":
        team.set("clickable", "true")
    elif mutation == "outside":
        team.set("bounds", "[100,1881][348,1924]")
    elif mutation == "order":
        card.insert(0, card[-1])
    else:
        card.set("bounds", "[176,1836][1047,1940]")
    assert not read_screen(etree.tostring(root), (1080, 2340)).posts


@pytest.mark.parametrize(
    "mutation", ["early", "changed", "missing", "motion", "uncommanded"]
)
def test_sports_context_cannot_change_or_disappear_without_explained_movement(mutation):
    before, after = screen("before"), screen("after")
    p = after.posts[0]
    c = p.sports_card
    if mutation == "early":
        c = replace(c, visibility=replace(c.visibility, bounds=(176, 1700, 1047, 1943)))
        after = replace(after, posts=(replace(p, sports_card=c),))
    elif mutation != "uncommanded":
        before = after
        if mutation == "changed":
            c = replace(c, teams=("NY", "NO"))
        elif mutation == "missing":
            c = None
        else:
            c = replace(
                c, visibility=replace(c.visibility, bounds=(176, 1856, 1047, 1943))
            )
        after = replace(after, posts=(replace(p, sports_card=c),))
    with pytest.raises(XError):
        _alignment(before, after, scrolling=mutation == "early")
