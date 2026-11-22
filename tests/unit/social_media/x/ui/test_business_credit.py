import pytest
from lxml import etree
from unit.paths import CORE
from unit.x_fixtures import xml_fixture

from taktik.core.social_media.x.ui.screen import read_screen

FIXTURE = (CORE / "tests/unit/social_media/x/fixtures") / "business-credit.xml"


def test_business_video_credit_retains_the_source_and_outer_author():
    screen = read_screen(xml_fixture(FIXTURE), (1080, 2340))
    assert not screen.rejected_posts
    (post,) = screen.posts
    assert post.author == "@fixture_author"
    assert post.media[0].source_label == "Fixture Business"
    assert post.labels == ("Verified",)
    assert post.advertising == "unknown"


@pytest.mark.parametrize("mutation", ["unknown", "text", "interactive", "outside"])
def test_damaged_business_credit_stays_rejected(mutation):
    root = etree.fromstring(xml_fixture(FIXTURE).encode())
    (badge,) = root.xpath('//*[@content-desc="Verified Business"]')
    if mutation == "unknown":
        badge.set("content-desc", "Unrecognized badge")
    elif mutation == "text":
        badge.set("text", "unexpected")
    elif mutation == "interactive":
        badge.set("clickable", "true")
    else:
        badge.set("bounds", "[0,0][100,100]")
    screen = read_screen(etree.tostring(root), (1080, 2340))
    assert not screen.posts
    assert screen.rejected_posts
