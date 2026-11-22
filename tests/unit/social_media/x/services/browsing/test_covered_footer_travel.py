"""Keep body overlap until a video footer supplies all its action anchors."""

from unittest.mock import Mock

import pytest
from unit.x_fixtures import xml_fixture as document

from taktik.core.shared.phone_interaction import Phone
from taktik.core.social_media.x.services.browsing.navigation import (
    X,
    XError,
    _alignment,
)
from taktik.core.social_media.x.ui.screen import read_screen


def screen(stage="before"):
    return read_screen(document(f"covered-footer-travel-{stage}"), (1080, 2340))


def test_unprovable_captured_jump_stays_rejected():
    with pytest.raises(XError):
        _alignment(screen(), screen("after"), scrolling=True)


def test_video_body_stays_available_until_the_covered_footer_is_revealed():
    before = screen()
    phone = Mock(spec=Phone)
    X(phone)._gesture(before, "up")
    distance = phone.gesture.call_args.kwargs["distance"]
    post = before.posts[0]
    assert [a.label for a in post.actions] == [
        "Reply",
        "Repost",
        "Like",
        "Impressions",
        "Share",
    ]
    assert distance == pytest.approx(440.25)
    assert post.body_visibility.bounds[3] - distance > before.content_viewport[1]
