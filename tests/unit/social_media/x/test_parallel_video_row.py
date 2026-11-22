"""Native side-by-side videos retain ordered continuity after header/body loss."""

from dataclasses import replace
from pathlib import Path

import pytest
from lxml import etree
from unit.x_fixtures import xml_fixture

from taktik.core.shared.ui.geometry import bounds
from taktik.core.social_media.x.services.browsing.navigation import XError, _alignment
from taktik.core.social_media.x.ui.screen import read_screen


def document(name):
    return xml_fixture(Path(__file__).parent / "fixtures" / f"{name}.xml")


def screen(stage):
    return read_screen(document(f"parallel-video-row-{stage}"), (1080, 2340))


def test_video_row_keeps_exact_body_and_separate_native_media():
    before, after = screen("before"), screen("after")
    assert not after.rejected_posts
    p = after.fragments[0]
    assert p.body == before.posts[0].body
    assert len(p.media) == 2 and all(m.kind == "video" for m in p.media)
    assert not hasattr(p, "author")
    assert _alignment(before, after, scrolling=True) == (1, True)


@pytest.mark.parametrize("axis", ["overlap", "height"])
def test_fragment_row_requires_nonoverlapping_media_with_matching_vertical_extent(axis):
    root = etree.fromstring(document("parallel-video-row-after").encode())
    container = root.xpath(
        '//*[@scrollable="true"]/*[@scrollable="true"]/*[@clickable="true"]'
    )[0]
    second = container.xpath('.//*[@content-desc="Video"]')[1]
    while second.get("clickable") != "true":
        second = second.getparent()
    for n in second.iter():
        x1, y1, x2, y2 = bounds(n)
        dx, dy = (-40, 0) if axis == "overlap" else (0, 10)
        n.set("bounds", f"[{x1 + dx},{y1 + dy}][{x2 + dx},{y2 + dy}]")
    assert read_screen(etree.tostring(root), (1080, 2340)).rejected_posts


def synthetic_bodyless_row():
    before = replace(screen("after"), posts=())
    root = etree.fromstring(document("parallel-video-row-after").encode())
    containers = root.xpath(
        '//*[@scrollable="true"]/*[@scrollable="true"]/*[@clickable="true"]'
    )
    container = containers[0]
    for other in containers[1:]:
        other.getparent().remove(other)
    body = next(n for n in container if n.get("text") == before.fragments[0].body)
    container.remove(body)
    for node in container.iter():
        x1, y1, x2, y2 = bounds(node)
        node.set("bounds", f"[{x1},{max(0, y1 - 500)}][{x2},{max(0, y2 - 500)}]")
    after = read_screen(etree.tostring(root), (1080, 2340))
    return before, after


def test_synthetic_body_loss_retains_both_overlapping_videos_and_footer():
    before, after = synthetic_bodyless_row()
    assert not after.rejected_posts
    assert after.fragments[0].body is None
    assert len(after.fragments[0].media) == 2
    assert _alignment(before, after, scrolling=True) == (0, True)


@pytest.mark.parametrize(
    "mutation",
    [
        "missing_video",
        "order",
        "video_motion",
        "source",
        "footer",
        "body_still_visible",
        "uncommanded",
    ],
)
def test_bodyless_row_requires_every_media_and_footer_anchor(mutation):
    before, after = synthetic_bodyless_row()
    p = after.fragments[0]
    if mutation == "missing_video":
        p = replace(p, media=p.media[:1])
    elif mutation == "order":
        p = replace(p, media=p.media[::-1])
    elif mutation in {"video_motion", "source"}:
        m = p.media[1]
        m = (
            replace(m, source_label="Different source")
            if mutation == "source"
            else replace(
                m, visibility=replace(m.visibility, bounds=(884, 18, 1080, 630))
            )
        )
        p = replace(p, media=(p.media[0], m))
    elif mutation == "footer":
        target = p.actions[0]
        x1, y1, x2, y2 = target.visibility.bounds
        target = replace(
            target,
            visibility=replace(target.visibility, bounds=(x1, y1 + 20, x2, y2 + 20)),
        )
        p = replace(p, actions=(target, *p.actions[1:]))
    elif mutation == "body_still_visible":
        old = before.fragments[0]
        old = replace(
            old,
            body_visibility=replace(old.body_visibility, bounds=(176, 0, 1047, 800)),
        )
        before = replace(before, fragments=(old,))
    after = replace(after, fragments=(p,))
    with pytest.raises(XError):
        _alignment(before, after, scrolling=mutation != "uncommanded")
