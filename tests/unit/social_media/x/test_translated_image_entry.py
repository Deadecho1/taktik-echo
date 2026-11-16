"""A translated quote can reveal a native image thumbnail beside its body."""

from pathlib import Path

import pytest
from lxml import etree
from taktik.core.social_media.x.services.browsing.navigation import XError, _alignment
from taktik.core.social_media.x.ui.screen import read_screen


def document(name):
    return (Path(__file__).parent / "fixtures" / f"{name}.xml").read_text()


def screens():
    return tuple(
        read_screen(document(f"translated-image-entry-{s}"), (1080, 2340))
        for s in ("before", "after")
    )


def test_translated_image_quote_remains_separate_and_clipped():
    before, after = screens()
    assert not after.rejected_posts
    post = after.posts[0]
    quote = post.quoted_post
    assert quote.translation == "Translated from Indonesian"
    assert quote.media[0].kind == "image"
    assert quote.media[0].description == "Image"
    assert quote.body and quote.body != post.body
    assert not quote.body_complete
    assert _alignment(before, after, scrolling=True) == (1, True)


@pytest.mark.parametrize(
    "mutation",
    [
        "wrapper_clickable",
        "extra",
        "label",
        "image_control",
        "image_text",
        "image_bounds",
        "body_overlap",
        "image_top",
        "label_overlap",
        "label_control",
    ],
)
def test_translated_image_requires_native_thumbnail_and_label_geometry(mutation):
    root = etree.fromstring(document("translated-image-entry-after").encode())
    label = root.xpath('//*[@text="Translated from Indonesian"]')[0]
    wrapper = label.getnext()
    image = wrapper[0]
    if mutation == "wrapper_clickable":
        wrapper.set("clickable", "true")
    elif mutation == "extra":
        wrapper.append(etree.fromstring(etree.tostring(image)))
    elif mutation == "label":
        image.set("content-desc", "Unknown media")
    elif mutation == "image_control":
        image.set("clickable", "false")
    elif mutation == "image_text":
        image.set("text", "Unexpected text")
    elif mutation == "image_bounds":
        image.set("bounds", "[198,2328][399,2340]")
    elif mutation == "body_overlap":
        wrapper.getnext().set("bounds", "[380,2327][1025,2340]")
    elif mutation == "image_top":
        wrapper.set("bounds", "[198,2320][399,2340]")
        image.set("bounds", wrapper.get("bounds"))
    elif mutation == "label_overlap":
        label.set("bounds", "[283,2284][725,2330]")
    else:
        label.set("clickable", "true")
    after = read_screen(etree.tostring(root), (1080, 2340))
    assert after.rejected_posts
    with pytest.raises(XError):
        _alignment(screens()[0], after, scrolling=True)
