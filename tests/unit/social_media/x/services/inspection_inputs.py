"""Shared inspection inputs for named regression scenarios."""

from unit.paths import CORE
from unit.x_fixtures import xml_fixture

FIXTURES = CORE / "tests/unit/social_media/x/fixtures/inspection"


def document(name):
    return xml_fixture(FIXTURES / f"{name}.xml")


ENGAGEMENT_FIXTURES = CORE / "tests/unit/social_media/x/fixtures/engagement"


def engagement_document(name):
    return xml_fixture(ENGAGEMENT_FIXTURES / f"{name}.xml")


LINK_FIXTURES = CORE / "tests/unit/social_media/x/fixtures/links"


LINK_QUERY = 'from:NASA "stellar merger"'


LINK_URL = "https://x.com/NASA/status/2123169377855922254"


def link_document(name):
    return xml_fixture(LINK_FIXTURES / f"{name}.xml")
