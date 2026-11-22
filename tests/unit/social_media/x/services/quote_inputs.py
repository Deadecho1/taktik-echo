"""Shared quote inputs for named regression scenarios."""

from unit.paths import CORE
from unit.x_fixtures import xml_fixture

from taktik.core.social_media.x.ui.screen import read_screen

FIXTURES = CORE / "tests/unit/social_media/x/fixtures"


def screens(family="quote-body-preview"):
    return [
        read_screen(
            xml_fixture(FIXTURES / f"{family}-{stage}.xml").encode(), (1080, 2340)
        )
        for stage in ("before", "after")
    ]
