"""A native image-only quote supplies context and a usable scroll budget."""

import pytest
from lxml import etree
from unit.paths import CORE

from taktik.core.social_media.x.services.browsing.navigation import _alignment
from taktik.core.social_media.x.ui.screen import read_screen


def document(name):
    return (CORE / "tests/unit/social_media/x/fixtures" / f"{name}.xml").read_text()


def screen(stage="after"):
    return read_screen(document(f"image-only-quote-{stage}"), (1080, 2340))


def test_image_only_quote_keeps_its_own_author_and_native_image():
    s = screen()
    assert not s.rejected_posts
    q = s.posts[0].quoted_post
    assert q.body is None and not q.body_complete
    assert len(q.media) == 1 and q.media[0].kind == "image"
    assert q.media[0].description == "Image"
    assert q.media[0].visibility.bounds == (198, 1914, 1025, 2340)
    assert not q.observable


def test_original_captured_entry_gestures_remain_verified():
    assert _alignment(screen("before"), screen("first"), scrolling=True)[1]
    assert _alignment(screen("first"), screen(), scrolling=True)[1]


@pytest.mark.parametrize(
    "mutation",
    [
        "wrapper_control",
        "image_control",
        "class",
        "text",
        "extra",
        "image_bounds",
        "header_overlap",
        "outside",
    ],
)
def test_image_only_quote_requires_native_wrapper_and_header_order(mutation):
    root = etree.fromstring(document("image-only-quote-after").encode())
    card = root.xpath('//*[@content-desc="Quote"]')[0].getparent()
    wrapper = card[-1]
    image = wrapper[0]
    if mutation == "wrapper_control":
        wrapper.set("clickable", "true")
    elif mutation == "image_control":
        image.set("clickable", "false")
    elif mutation == "class":
        image.set("class", "android.view.View")
    elif mutation == "text":
        image.set("text", "Unknown")
    elif mutation == "extra":
        wrapper.append(etree.fromstring(etree.tostring(image)))
    elif mutation == "image_bounds":
        image.set("bounds", "[198,1920][1025,2340]")
    else:
        rect = (
            "[198,1890][1025,2340]"
            if mutation == "header_overlap"
            else "[150,1914][1025,2340]"
        )
        wrapper.set("bounds", rect)
        image.set("bounds", rect)
    assert read_screen(etree.tostring(root), (1080, 2340)).rejected_posts
