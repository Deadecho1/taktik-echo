"""Feed advancement on the captured 47.7.3 photo that exhausted Moria's retries."""

from copy import deepcopy
from pathlib import Path
from unittest.mock import Mock

import pytest
from lxml import etree

from taktik.core.shared.browsing import PlatformError
from taktik.core.shared.phone_interaction import Result, Status
from taktik.core.social_media.tiktok.services.browsing.browser import TikTok

FIXTURE = Path(__file__).parents[1] / "fixtures/tt4773_en_for_you_single_photo.xml"
PACKAGE = "com.zhiliaoapp.musically"


def captured_screen():
    return etree.parse(str(FIXTURE)).getroot()


def by_id(root, name):
    return root.xpath(f'//*[@resource-id="{PACKAGE}:id/{name}"]')[0]


def browser(root):
    phone = Mock()
    phone.read.side_effect = lambda kind: (
        (1440, 3216) if kind == "size" else etree.tostring(root, encoding="unicode")
    )
    phone.gesture.return_value = Result(Status.SUCCESS)
    return TikTok(phone, {"for_you"})


@pytest.mark.parametrize("badge_visible", [True, False])
def test_advance_4773_single_photo_inside_its_image(badge_visible):
    root = captured_screen()
    if not badge_visible:
        by_id(root, "tv_label").set("text", "")
    app = browser(root)

    app.advance()

    app.phone.gesture.assert_called_once_with("page", "up", (0, 160, 1152, 2000))
    app.phone.tap.assert_not_called()
    app.phone.command.assert_not_called()


@pytest.mark.parametrize(
    "missing", ["image", "pager", "wrong_parent", "ambiguous", "outside", "empty"]
)
def test_unverified_photo_geometry_stops_before_a_gesture(missing):
    root = captured_screen()
    image = by_id(root, "x0u")
    if missing in ("image", "pager"):
        by_id(root, "x0u" if missing == "image" else "rbj").set("resource-id", "")
    elif missing == "wrong_parent":
        root[0].append(image)
    elif missing == "ambiguous":
        image.getparent().append(deepcopy(image))
    elif missing == "outside":
        image.set("bounds", "[0,160][1440,3040]")
    else:
        image.set("bounds", "[0,160][1440,160]")
    app = browser(root)

    with pytest.raises(PlatformError, match="safe swipe area.*photo layout"):
        app.advance()

    app.phone.gesture.assert_not_called()


def test_uncertain_photo_swipe_is_not_retried():
    app = browser(captured_screen())
    app.phone.gesture.return_value = Result(
        Status.UNCERTAIN, detail="Swipe outcome unknown"
    )

    with pytest.raises(PlatformError, match="Swipe outcome unknown"):
        app.advance()

    app.phone.gesture.assert_called_once()
