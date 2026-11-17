"""Captured video-gap geometry with synthetic text and no independent neighbor."""

from dataclasses import replace
from pathlib import Path

import pytest
from lxml import etree

from taktik.core.social_media.x.services.browsing.navigation import XError, _alignment
from taktik.core.social_media.x.ui.screen import QuotedPost, read_screen

FIXTURES = Path(__file__).parent / "fixtures"
SIZE = (1080, 2340)


def document(stage):
    return (FIXTURES / f"video-inset-{stage}.xml").read_bytes()


def screens():
    return [read_screen(document(stage), SIZE) for stage in ("before", "after")]


def test_body_loss_into_text_video_gap_retains_unattributed_continuity():
    before, after = screens()
    assert not after.rejected_posts
    assert not after.posts
    fragment = after.fragments[0]
    assert fragment.body is fragment.body_visibility is None
    assert not hasattr(fragment, "author")
    assert not hasattr(fragment, "content_key")
    assert fragment.media[0].source_label == "Fixture Source"
    assert fragment.media[0].visibility.bounds[1] == 154
    assert after.content_viewport[1] == 136
    assert _alignment(before, after, scrolling=True) == (1, True)


def test_same_inset_fragment_can_be_reread_without_inventing_movement():
    _, after = screens()
    assert _alignment(after, after) == (0, False)
    assert _alignment(after, after, scrolling=True) == (0, False)


def test_inset_fragment_can_scroll_on_into_a_clipped_video_tail():
    _, before = screens()
    root = etree.fromstring(document("after"))
    container = root.xpath('//*[@content-desc="Video"]')[0].getparent().getparent()
    for node in container.iter():
        x1, y1, x2, y2 = map(
            int, node.get("bounds").replace("][", ",").strip("[]").split(",")
        )
        node.set("bounds", f"[{x1},{max(0, y1 - 200)}][{x2},{max(0, y2 - 200)}]")
    after = read_screen(etree.tostring(root), SIZE)

    assert _alignment(before, after, scrolling=True) == (0, True)
    assert after.fragments[0].media[0].visibility.bounds[1] == 0


def test_video_start_exactly_at_viewport_edge_retains_refresh_continuity():
    before, after = screens()
    for name in ("before", "after"):
        original = before if name == "before" else after
        adjusted = replace(original, content_viewport=(0, 154, 1080, 2230))
        if name == "before":
            before = adjusted
        else:
            after = adjusted

    assert _alignment(before, after, scrolling=True) == (1, True)
    assert _alignment(after, after) == (0, False)


@pytest.mark.parametrize(
    "mutation",
    [
        "body_still_visible",
        "header_still_visible",
        "video_top",
        "video_bottom",
        "video_width",
        "source",
        "source_prefix",
        "action_top",
        "action_width",
        "missing_action",
        "clipped_old_video_top",
        "missing_prior_body",
        "lost_quote_header",
        "duplicate_before",
        "duplicate_after",
        "downward",
    ],
)
def test_inset_tail_requires_projected_loss_consistent_geometry_and_unique_match(
    mutation,
):
    before, after = screens()
    old, fragment = before.posts[0], after.fragments[0]
    video = fragment.media[0]
    if mutation == "body_still_visible":
        old = replace(
            old,
            body_visibility=replace(old.body_visibility, bounds=(176, 538, 1047, 739)),
        )
    elif mutation == "header_still_visible":
        old = replace(
            old,
            header_visibility=replace(
                old.header_visibility, bounds=(176, 700, 876, 749)
            ),
        )
    elif mutation in {"video_top", "video_bottom", "video_width"}:
        rect = list(video.visibility.bounds)
        rect[{"video_top": 1, "video_bottom": 3, "video_width": 0}[mutation]] += 10
        video = replace(video, visibility=replace(video.visibility, bounds=tuple(rect)))
    elif mutation in {"source", "source_prefix"}:
        field = "source_label" if mutation == "source" else "source_prefix"
        video = replace(video, **{field: "Changed"})
    elif mutation in {"action_top", "action_width", "missing_action"}:
        actions = list(fragment.actions)
        action = actions[0]
        rect = list(action.visibility.bounds)
        rect[1 if mutation == "action_top" else 0] += 10
        actions[0] = replace(
            action, visibility=replace(action.visibility, bounds=tuple(rect))
        )
        fragment = replace(
            fragment,
            actions=tuple(actions[1:] if mutation == "missing_action" else actions),
        )
    elif mutation == "clipped_old_video_top":
        old_video = old.media[0]
        old = replace(
            old,
            media=(
                replace(
                    old_video,
                    visibility=replace(
                        old_video.visibility, bounds=(176, 0, 1047, 1845)
                    ),
                ),
            ),
        )
    elif mutation == "missing_prior_body":
        old = replace(old, body=None, body_visibility=None)
    elif mutation == "lost_quote_header":
        quote = QuotedPost(
            "@fixture_quote",
            "Fixture Quote",
            None,
            False,
            old.media,
            old.visibility,
            replace(old.header_visibility, bounds=(176, 700, 876, 749)),
            None,
        )
        old = replace(old, body=None, body_visibility=None, media=(), quoted_post=quote)
    before = replace(
        before, posts=(old,) * (2 if mutation == "duplicate_before" else 1)
    )
    fragment = replace(fragment, media=(video,))
    after = replace(
        after, fragments=(fragment,) * (2 if mutation == "duplicate_after" else 1)
    )
    if mutation == "downward":
        before, after = after, before

    with pytest.raises(XError, match="uniquely"):
        _alignment(before, after, scrolling=True)


@pytest.mark.parametrize("mutation", ["unknown_content", "missing_action", "header"])
def test_inset_video_still_requires_an_understood_headerless_container(mutation):
    root = etree.fromstring(document("after"))
    video = root.xpath('//*[@content-desc="Video"]')[0]
    container = video.getparent().getparent()
    if mutation == "unknown_content":
        video.getparent().set("content-desc", "Unrecognized post content")
    elif mutation == "missing_action":
        container.remove(container[-1])
    else:
        video.getparent().set("resource-id", "timeline_post")

    after = read_screen(etree.tostring(root), SIZE)

    assert not after.fragments
    assert after.rejected_posts


@pytest.mark.parametrize("mutation", ["body_loss", "top_changed", "source_changed"])
def test_inset_fragment_does_not_permit_content_change_during_refresh(mutation):
    before, after = screens()
    if mutation != "body_loss":
        before = after
        fragment = after.fragments[0]
        video = fragment.media[0]
        if mutation == "top_changed":
            video = replace(
                video,
                visibility=replace(video.visibility, bounds=(176, 164, 1047, 1243)),
            )
        else:
            video = replace(video, source_label="Changed")
        after = replace(after, fragments=(replace(fragment, media=(video,)),))

    with pytest.raises(XError, match="outside adapter scrolling"):
        _alignment(before, after)
