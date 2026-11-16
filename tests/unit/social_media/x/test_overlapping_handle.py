"""A native handle overlapping New posts without its age remains unattributed."""

from pathlib import Path

import pytest
from lxml import etree
from taktik.core.social_media.x.services.browsing.navigation import _alignment
from taktik.core.social_media.x.ui.screen import read_screen


def document(name):
    return (Path(__file__).parent / "fixtures" / f"{name}.xml").read_text()


def test_overlapping_handle_retains_unattributed_body_and_verified_movement():
    before, after = [
        read_screen(document(f"overlapping-handle-{s}"), (1080, 2340))
        for s in ("before", "after")
    ]
    assert not after.rejected_posts
    p = after.fragments[-1]
    assert p.covered_handle.visibility.overlaps
    assert p.body == before.posts[0].body
    assert not hasattr(p, "author")
    assert _alignment(before, after, scrolling=True) == (1, True)


@pytest.mark.parametrize(
    "mutation",
    [
        "disjoint",
        "outside_cover",
        "missing_cover",
        "missing_prefix",
        "invalid_handle",
        "interactive",
    ],
)
def test_overlapping_header_requires_known_cover_and_native_partial_structure(mutation):
    root = etree.fromstring(document("overlapping-handle-after").encode())
    handle = root.xpath('//*[@text="@fixture_1"]')[0]
    if mutation == "disjoint":
        handle.set("bounds", "[376,280][587,296]")
    elif mutation == "outside_cover":
        handle.set("bounds", "[376,240][700,289]")
    elif mutation == "missing_cover":
        cover = root.xpath('//*[@resource-id="ntp"]')[0]
        cover.getparent().remove(cover)
    elif mutation == "missing_prefix":
        handle.set("bounds", "[400,240][587,289]")
    elif mutation == "invalid_handle":
        handle.set("text", "@Tiwari...")
    else:
        handle.set("clickable", "true")
    assert read_screen(etree.tostring(root), (1080, 2340)).rejected_posts
