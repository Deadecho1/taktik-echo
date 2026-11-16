"""A tall display name can outlast its clipped handle and age."""

from pathlib import Path

import pytest
from lxml import etree
from taktik.core.social_media.x.services.browsing.navigation import _alignment
from taktik.core.social_media.x.ui.screen import read_screen


def document(name):
    return (Path(__file__).parent / "fixtures" / f"{name}.xml").read_text()


def screen(stage):
    return read_screen(document(f"clipped-name-only-{stage}"), (1080, 2340))


def test_clipped_name_retains_body_without_inferring_missing_author():
    before, after = screen("before"), screen("after")
    p = after.fragments[0]
    assert p.body == before.posts[0].body
    assert not hasattr(p, "author")
    assert _alignment(before, after, scrolling=True) == (1, True)


@pytest.mark.parametrize(
    "mutation",
    [
        "empty",
        "handle",
        "age",
        "control",
        "wrapper_control",
        "nested",
        "outside",
        "unclipped",
        "height",
        "disabled",
    ],
)
def test_name_only_header_requires_plain_clipped_name_geometry(mutation):
    root = etree.fromstring(document("clipped-name-only-after").encode())
    header = root.xpath('//*[@resource-id="timeline_post"]')[0]
    name = header[0]
    if mutation == "empty":
        name.set("text", "")
    elif mutation == "handle":
        name.set("text", "@partial...")
    elif mutation == "age":
        name.set("text", "· 21h")
    elif mutation == "control":
        name.set("clickable", "true")
    elif mutation == "wrapper_control":
        header.set("clickable", "true")
    elif mutation == "nested":
        name.append(etree.fromstring(etree.tostring(name)))
    elif mutation == "outside":
        name.set("bounds", "[176,30][880,145]")
    elif mutation == "unclipped":
        header.set("bounds", "[176,136][876,251]")
        name.set("bounds", "[176,136][469,251]")
    elif mutation == "height":
        name.set("bounds", "[176,30][469,140]")
    else:
        name.set("enabled", "false")
    assert read_screen(etree.tostring(root), (1080, 2340)).rejected_posts
