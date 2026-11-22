"""A wholly offscreen quote may expose a translation before its body arrives."""

from dataclasses import replace

import pytest
from lxml import etree
from unit.paths import CORE
from unit.x_fixtures import xml_fixture

from taktik.core.social_media.x.services.browsing.navigation import XError, _alignment
from taktik.core.social_media.x.ui.screen import PostFragment, read_screen


def document(name):
    return xml_fixture(CORE / "tests/unit/social_media/x/fixtures" / f"{name}.xml")


def screen(stage):
    return read_screen(document(f"offscreen-quote-translation-{stage}"), (1080, 2340))


def test_offscreen_translation_does_not_invent_a_quoted_body():
    s = screen("after")
    assert not s.rejected_posts
    q = s.posts[0].quoted_post
    assert q.translation == "Translated from Arabic"
    assert q.body is None and not q.body_complete and not q.media
    assert q.translation_visibility.visible_bounds is None
    assert q.header_visibility.visible_bounds is None
    assert not q.observable and not s.observable_posts


@pytest.mark.parametrize(
    "mutation",
    [
        "visible_header",
        "label_control",
        "label_disabled",
        "label_overlap",
        "label_inset",
        "label_bottom",
        "bad_language",
    ],
)
def test_translation_without_body_requires_an_offscreen_native_clipped_label(mutation):
    root = etree.fromstring(document("offscreen-quote-translation-after").encode())
    card = root.xpath('//*[@content-desc="Quote"]')[0].getparent()
    label = card[-1]
    if mutation == "visible_header":
        card[1].set("bounds", "[264,2200][450,2256]")
    elif mutation == "label_control":
        label.set("clickable", "true")
    elif mutation == "label_disabled":
        label.set("enabled", "false")
    elif mutation == "label_overlap":
        label.set("bounds", "[283,2300][650,2340]")
    elif mutation == "label_inset":
        label.set("bounds", "[283,2323][1060,2340]")
    elif mutation == "label_bottom":
        label.set("bounds", "[283,2323][650,2338]")
    else:
        label.set("text", "Translated from ???")
    assert read_screen(etree.tostring(root), (1080, 2340)).rejected_posts


@pytest.mark.parametrize("mutation", [None, "translation", "early_body"])
def test_synthetic_body_entry_preserves_translation_and_projected_boundary(mutation):
    before = replace(screen("after"), fragments=())
    p = before.posts[0]

    def shifted(view):
        x1, y1, x2, y2 = view.bounds
        box = (x1, max(0, y1 - 600), x2, max(0, y2 - 600))
        return replace(view, bounds=box, visible_bounds=box, overlaps=(), clipped=False)

    q = p.quoted_post
    q = replace(
        q,
        visibility=replace(shifted(q.visibility), bounds=(176, 1633, 1047, 2000)),
        header_visibility=shifted(q.header_visibility),
        translation_visibility=shifted(q.translation_visibility),
        translation="Translated from French"
        if mutation == "translation"
        else q.translation,
        body="Synthetic next quoted body",
        body_visibility=replace(
            shifted(q.translation_visibility),
            bounds=(198, 1700 if mutation == "early_body" else 1740, 1025, 1900),
        ),
    )
    fragment = PostFragment(
        p.body,
        tuple(replace(m, visibility=shifted(m.visibility)) for m in p.media),
        shifted(p.visibility),
        shifted(p.body_visibility),
        quoted_post=q,
        translation=p.translation,
        body_annotations=p.body_annotations,
    )
    after = replace(before, posts=(), fragments=(fragment,))
    if mutation is None:
        assert _alignment(before, after, scrolling=True) == (1, True)
    else:
        with pytest.raises(XError):
            _alignment(before, after, scrolling=True)
