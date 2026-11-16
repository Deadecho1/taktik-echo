"""A native name/age row without a handle supplies only unattributed content."""

from pathlib import Path

import pytest
from lxml import etree
from taktik.core.social_media.x.services.browsing.navigation import _alignment
from taktik.core.social_media.x.ui.screen import read_screen

FIXTURES = Path(__file__).with_name("fixtures")


def document(name):
    return (FIXTURES / f"{name}.xml").read_text()


def test_unbadged_name_age_row_keeps_translated_body_and_video_unattributed():
    before, after = [
        read_screen(document(f"unbadged-header-{s}"), (1080, 2340))
        for s in ("before", "after")
    ]
    fragment = after.fragments[-1]
    assert fragment.body and fragment.translation == "Translated from Japanese"
    assert not hasattr(fragment, "author")
    assert _alignment(before, after, scrolling=True) == (0, True)


@pytest.mark.parametrize(
    "mutation", ["age", "name", "interactive", "outside", "overlap"]
)
def test_unbadged_header_requires_plain_contained_name_and_age(mutation):
    root = etree.fromstring(document("unbadged-header-after").encode())
    header = root.xpath('//*[@resource-id="timeline_post"]')[0]
    name, age = header
    if mutation == "age":
        age.set("text", "Unknown")
    elif mutation == "name":
        name.set("text", "@partial...")
    elif mutation == "interactive":
        age.set("clickable", "true")
    elif mutation == "outside":
        age.set("bounds", "[787,360][876,410]")
    else:
        age.set("bounds", "[700,385][876,410]")
    screen = read_screen(etree.tostring(root), (1080, 2340))
    assert all(f.translation is None for f in screen.fragments)
    assert screen.rejected_posts
