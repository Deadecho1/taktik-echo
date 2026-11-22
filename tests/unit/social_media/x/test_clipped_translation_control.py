"""The Show original touch target can outlive its translated-language label."""

import pytest
from lxml import etree
from unit.x_fixtures import xml_fixture as document

from taktik.core.social_media.x.services.browsing.navigation import _alignment
from taktik.core.social_media.x.ui.screen import read_screen


def test_clipped_translation_target_preserves_body_without_guessing_language():
    before, after = [
        read_screen(document(f"clipped-translation-control-{s}"), (1080, 2340))
        for s in ("before", "after")
    ]
    assert not after.rejected_posts
    assert after.fragments[0].body == before.posts[0].body
    assert after.fragments[0].translation is None
    assert not hasattr(after.fragments[0], "author")
    assert _alignment(before, after, scrolling=True) == (1, True)


@pytest.mark.parametrize(
    "mutation",
    [
        "unclipped",
        "gap",
        "outside",
        "not_clickable",
        "description",
        "class",
        "duplicate",
        "disabled",
        "scrollable",
    ],
)
def test_lone_translation_control_requires_its_native_clipped_body_edge(mutation):
    root = etree.fromstring(document("clipped-translation-control-after").encode())
    control = root.xpath('//*[@text="Show original"]')[0]
    if mutation == "unclipped":
        control.set("bounds", "[587,136][818,139]")
    elif mutation == "gap":
        control.set("bounds", "[587,35][818,138]")
    elif mutation == "outside":
        control.set("bounds", "[120,35][818,139]")
    elif mutation == "not_clickable":
        control.set("clickable", "false")
    elif mutation == "description":
        control.set("content-desc", "Unknown")
    elif mutation == "class":
        control.set("class", "android.view.View")
    elif mutation == "duplicate":
        control.addprevious(etree.fromstring(etree.tostring(control)))
    elif mutation == "disabled":
        control.set("enabled", "false")
    else:
        control.set("scrollable", "true")
    assert read_screen(etree.tostring(root), (1080, 2340)).rejected_posts
