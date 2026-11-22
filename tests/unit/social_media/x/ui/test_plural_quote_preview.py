"""A native compact quote can advertise several additional media items."""

from dataclasses import replace

import pytest
from lxml import etree
from unit.paths import CORE
from unit.x_fixtures import xml_fixture

from taktik.core.social_media.x.services.browsing.navigation import XError, _alignment
from taktik.core.social_media.x.ui.screen import read_screen


def document(name):
    return xml_fixture(CORE / "tests/unit/social_media/x/fixtures" / f"{name}.xml")


def screen(xml=None):
    return read_screen(xml or document("plural-quote-preview-after"), (1080, 2340))


def test_translated_quote_keeps_plural_count_separate_from_authored_body():
    p = screen().posts[0]
    q = p.quoted_post
    assert q.media[0].description == "3 more media items"
    assert q.media[0].kind == "preview"
    assert q.translation == "Translated from Japanese"
    assert "+3" not in q.body
    assert [m.kind for m in p.media] == ["video", "image"]


def test_original_sequence_keeps_plural_preview_entry():
    before = read_screen(document("plural-quote-preview-selected"), (1080, 2340))
    for stage in ("first", "before", "after"):
        after = read_screen(document(f"plural-quote-preview-{stage}"), (1080, 2340))
        assert _alignment(before, after, scrolling=True)[1]
        assert len(after.posts) == 1
        before = after


@pytest.mark.parametrize(
    "mutation",
    [
        "description",
        "kind",
        "movement",
        "width",
        "overlap",
        "order",
        "missing",
        "body",
        "early_quote",
    ],
)
def test_quote_entry_requires_every_retained_row_item_and_text(mutation):
    before = read_screen(document("plural-quote-preview-selected"), (1080, 2340))
    after = read_screen(document("plural-quote-preview-first"), (1080, 2340))
    p = after.posts[0]
    video, picture = p.media
    if mutation == "description":
        picture = replace(picture, description="Image: different")
    elif mutation == "kind":
        picture = replace(picture, kind="gif")
    elif mutation in ("movement", "width", "overlap"):
        rect = picture.visibility.bounds
        rect = (
            (rect[0], rect[1] + 10, rect[2], rect[3] + 10)
            if mutation == "movement"
            else (
                rect[0] - (10 if mutation == "width" else 50),
                rect[1],
                rect[2],
                rect[3],
            )
        )
        picture = replace(picture, visibility=replace(picture.visibility, bounds=rect))
    p = replace(p, media=(video, picture))
    if mutation == "order":
        p = replace(p, media=tuple(reversed(p.media)))
    elif mutation == "missing":
        p = replace(p, media=p.media[:1])
    elif mutation == "body":
        p = replace(p, body="Changed body")
    elif mutation == "early_quote":
        q = p.quoted_post
        p = replace(
            p,
            quoted_post=replace(
                q, visibility=replace(q.visibility, bounds=(176, 1900, 1047, 2340))
            ),
        )
    with pytest.raises(XError):
        _alignment(before, replace(after, posts=(p,)), scrolling=True)


@pytest.mark.parametrize("count", [1, 2, 3, 12])
def test_synthetic_counts_preserve_literal_number_and_native_grammar(count):
    root = etree.fromstring(document("plural-quote-preview-after").encode())
    preview = root.xpath('//*[@content-desc="3 more media items"]')[0]
    label = f"{count} more media " + ("item" if count == 1 else "items")
    preview.set("content-desc", label)
    preview[0].set("text", f"+{count}")
    assert (
        screen(etree.tostring(root)).posts[0].quoted_post.media[0].description == label
    )


@pytest.mark.parametrize(
    "mutation",
    [
        "mismatch",
        "singular",
        "zero",
        "leading_zero",
        "missing",
        "interactive",
        "outside",
    ],
)
def test_plural_preview_requires_matching_native_label_and_glyph(mutation):
    root = etree.fromstring(document("plural-quote-preview-after").encode())
    preview = root.xpath('//*[@content-desc="3 more media items"]')[0]
    if mutation == "mismatch":
        preview[0].set("text", "+2")
    elif mutation == "singular":
        preview.set("content-desc", "3 more media item")
    elif mutation in ("zero", "leading_zero"):
        count = "0" if mutation == "zero" else "03"
        preview.set("content-desc", f"{count} more media items")
        preview[0].set("text", f"+{count}")
    elif mutation == "missing":
        preview.remove(preview[0])
    elif mutation == "interactive":
        preview.set("clickable", "true")
    else:
        preview[0].set("bounds", "[400,1910][450,1956]")
    assert not screen(etree.tostring(root)).posts
