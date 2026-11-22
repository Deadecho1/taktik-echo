"""Expanded toolbar clipping retains native translation and body evidence."""

import pytest
from lxml import etree
from unit.x_fixtures import xml_fixture as document

from taktik.core.social_media.x.ui.screen import read_screen


def screen():
    return read_screen(document("expanded-translation-edge-before"), (1080, 2340))


def test_expanded_translation_edge_preserves_unattributed_fragment():
    s = screen()
    assert not s.collapsed and not s.rejected_posts
    p = s.fragments[0]
    assert not hasattr(p, "author")
    assert p.translation == "Translated from Spanish"
    assert p.body_visibility.visible_bounds == p.body_visibility.bounds
    assert p.body_visibility.overlaps == ((389, 438, 691, 570),)
    assert p.quoted_post.reply_to == ("@Marcelochumango",)


@pytest.mark.parametrize(
    "mutation", ["below_toolbar", "body_gap", "disabled", "language"]
)
def test_expanded_fragment_requires_native_translation_at_the_body_edge(mutation):
    root = etree.fromstring(document("expanded-translation-edge-before").encode())
    control = root.xpath('//*[@text="Show original"]')[0]
    if mutation == "below_toolbar":
        control.set("bounds", "[633,432][864,499]")
    elif mutation == "body_gap":
        control.getnext().set("bounds", "[176,500][1047,603]")
    elif mutation == "disabled":
        control.set("clickable", "false")
    else:
        control.getprevious().set("text", "Translated from ???")
    assert read_screen(etree.tostring(root), (1080, 2340)).rejected_posts
