"""Keep only captured article text when the quoted header scrolls away."""

from dataclasses import replace
from pathlib import Path

import pytest
from lxml import etree
from taktik.core.shared.ui.geometry import bounds
from taktik.core.social_media.x.services.browsing.navigation import XError, _alignment
from taktik.core.social_media.x.ui.screen import read_screen

FIXTURES = Path(__file__).with_name("fixtures")


def document(name):
    return (FIXTURES / f"{name}.xml").read_text()


def screens():
    return tuple(
        read_screen(document(f"preview-tail-{stage}"), (1080, 2340))
        for stage in ("before", "after")
    )


def test_headerless_preview_retains_text_without_an_author_or_new_observation():
    before, after = screens()
    assert not after.rejected_posts
    (fragment,) = after.fragments
    assert fragment.body is None and fragment.quoted_post is None
    assert not hasattr(fragment, "author")
    old = before.fragments[0].quoted_post.media[0]
    assert [part.text for part in fragment.preview_texts] == [
        old.description,
        old.preview_text,
    ]
    assert _alignment(before, after, scrolling=True) == (0, True)


@pytest.mark.parametrize(
    "mutation", ["text", "position", "footer", "header_not_lost", "media_not_lost"]
)
def test_preview_tail_rejects_changed_text_or_contradictory_clipping(mutation):
    before, after = screens()
    (old,) = before.fragments
    (new,) = after.fragments
    if mutation == "text":
        first, *rest = new.preview_texts
        new = replace(new, preview_texts=(replace(first, text="Changed"), *rest))
    elif mutation == "position":
        first, *rest = new.preview_texts
        x1, y1, x2, y2 = first.visibility.bounds
        first = replace(
            first, visibility=replace(first.visibility, bounds=(x1, y1, x2, y2 + 20))
        )
        new = replace(new, preview_texts=(first, *rest))
    elif mutation == "footer":
        first, *rest = new.actions
        x1, y1, x2, y2 = first.visibility.bounds
        new = replace(
            new,
            actions=(
                replace(
                    first,
                    visibility=replace(first.visibility, bounds=(x1, y1 + 20, x2, y2)),
                ),
                *rest,
            ),
        )
    elif mutation == "header_not_lost":
        quote = old.quoted_post
        x1, y1, x2, y2 = quote.header_visibility.bounds
        old = replace(
            old,
            quoted_post=replace(
                quote,
                header_visibility=replace(
                    quote.header_visibility, bounds=(x1, 900, x2, 949)
                ),
            ),
        )
    else:
        (video,) = old.media
        x1, y1, x2, y2 = video.visibility.bounds
        old = replace(
            old,
            media=(
                replace(
                    video,
                    visibility=replace(video.visibility, bounds=(x1, y1, x2, 900)),
                ),
            ),
        )
    before = replace(before, fragments=(old,))
    after = replace(after, fragments=(new,))
    with pytest.raises(XError):
        _alignment(before, after, scrolling=True)


def test_synthetic_summary_only_exit_still_uses_text_and_footer_movement():
    _, before = screens()
    before = replace(before, posts=())
    (old,) = before.fragments

    def shifted(view):
        x1, y1, x2, y2 = view.bounds
        bounds = x1, max(0, y1 - 340), x2, y2 - 340
        return replace(
            view,
            bounds=bounds,
            visible_bounds=(x1, max(136, bounds[1]), x2, bounds[3]),
            overlaps=(),
        )

    summary = replace(
        old.preview_texts[-1], visibility=shifted(old.preview_texts[-1].visibility)
    )
    new = replace(
        old,
        preview_texts=(summary,),
        visibility=shifted(old.visibility),
        actions=tuple(
            replace(a, visibility=shifted(a.visibility)) for a in old.actions
        ),
    )
    after = replace(before, fragments=(new,))
    assert _alignment(before, after, scrolling=True) == (0, True)
    assert _alignment(after, after) == (0, False)
    changed = replace(new, preview_texts=(replace(summary, text="Different summary"),))
    with pytest.raises(XError):
        _alignment(after, replace(after, fragments=(changed,)))


@pytest.mark.parametrize(
    "mutation",
    ["wrapper_control", "card_label", "child_control", "outside", "overlap", "footer"],
)
def test_malformed_preview_tail_cannot_supply_continuity(mutation):
    _, after = screens()
    root = etree.fromstring(document("preview-tail-after").encode())
    title = root.xpath(
        "//*[@text=$text]", text=after.fragments[0].preview_texts[0].text
    )[0]
    preview = title.getparent()
    wrapper = preview.getparent().getparent()
    if mutation == "wrapper_control":
        wrapper.set("clickable", "true")
    elif mutation == "card_label":
        preview.getparent().set("text", "Unknown wrapper")
    elif mutation == "child_control":
        title.set("clickable", "true")
    elif mutation == "outside":
        title.set("bounds", "[0,0][1080,2300]")
    elif mutation == "overlap":
        preview[-1].set("bounds", title.get("bounds"))
    else:
        footer = wrapper.getnext()
        x1, y1, x2, y2 = bounds(footer)
        footer.set("bounds", f"[{x1},{y1 + 20}][{x2},{y2}]")
    screen = read_screen(etree.tostring(root), (1080, 2340))
    assert not screen.fragments
    assert screen.rejected_posts


@pytest.mark.parametrize("mutation", [None, "child_outside", "target_outside"])
def test_video_credit_padding_requires_all_label_children_inside_the_video(mutation):
    _, after = screens()
    post = next(p for p in after.posts if p.quoted_post is not None)
    source = post.quoted_post.media[0].source_label
    root = etree.fromstring(document("preview-tail-after").encode())
    label = root.xpath("//*[@text=$text]", text=source)[0]
    if mutation == "child_outside":
        x1, y1, x2, y2 = bounds(label)
        label.set("bounds", f"[{x1},{y1}][{x2},{y2 + 200}]")
    elif mutation == "target_outside":
        target = label.getparent()
        _, y1, x2, y2 = bounds(target)
        target.set("bounds", f"[0,{y1}][{x2},{y2}]")
    screen = read_screen(etree.tostring(root), (1080, 2340))
    assert any(p.author == post.author for p in screen.posts) == (mutation is None)
