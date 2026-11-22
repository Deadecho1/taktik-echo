"""A handle-shaped display name is not a second native username field."""

from copy import deepcopy

import pytest
from lxml import etree
from unit.x_fixtures import xml_fixture as document

from taktik.core.shared.ui.geometry import bounds
from taktik.core.social_media.x.services.browsing.navigation import _alignment
from taktik.core.social_media.x.ui.screen import read_screen


def screen(stage="after"):
    return read_screen(document(f"handle-display-name-{stage}"), (1080, 2340))


def test_identical_native_display_name_and_handle_keep_username_geometry():
    s = screen()
    assert not s.rejected_posts
    p = s.posts[0]
    assert p.author == p.display_name
    assert p.author_visibility.bounds == (446, 424, 694, 473)
    assert _alignment(screen("before"), s, scrolling=True)[1]


def test_different_handle_shaped_display_name_cannot_replace_actual_author():
    root = etree.fromstring(document("handle-display-name-after").encode())
    header = root.xpath('//*[@resource-id="timeline_post"]')[0]
    expected = header[1].get("text")
    header[0].set("text", "@different")
    p = read_screen(etree.tostring(root), (1080, 2340)).posts[0]
    assert p.author == expected and p.display_name == "@different"


@pytest.mark.parametrize(
    "mutation", ["extra_handle", "partial_handle", "missing_handle", "swapped_age"]
)
def test_native_header_still_requires_one_username_in_the_expected_position(mutation):
    root = etree.fromstring(document("handle-display-name-after").encode())
    header = root.xpath('//*[@resource-id="timeline_post"]')[0]
    if mutation == "extra_handle":
        header.append(deepcopy(header[1]))
    elif mutation == "partial_handle":
        header[1].set("text", "@partial...")
    elif mutation == "missing_handle":
        header.remove(header[1])
    else:
        header[1].addprevious(header[-1])
    assert read_screen(etree.tostring(root), (1080, 2340)).rejected_posts


@pytest.mark.parametrize("same_name", [True, False])
def test_quote_uses_the_same_native_username_selection(same_name):
    root = etree.fromstring(document("video-only-quote-after").encode())
    card = root.xpath('//*[@content-desc="Quote"]')[0].getparent()
    texts = [n for n in card if n.get("text")]
    name, handle = texts[:2]
    expected = handle.get("text")
    name.set("text", expected if same_name else "@different")
    q = read_screen(etree.tostring(root), (1080, 2340)).fragments[0].quoted_post
    assert q.author == expected
    assert q.header_visibility.bounds == bounds(handle)
