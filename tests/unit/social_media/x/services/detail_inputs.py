"""Shared detail inputs for named regression scenarios."""

from unit.paths import CORE
from unit.x_fixtures import xml_fixture

FIXTURES = CORE / "tests/unit/social_media/x/fixtures/detail"


def document(name="image-main"):
    return xml_fixture(FIXTURES / f"{name}.xml")
