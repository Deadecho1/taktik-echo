"""Limit travel to retain a short video's spatial overlap as its body leaves."""

from pathlib import Path
from unittest.mock import Mock

import pytest
from unit.x_fixtures import xml_fixture

from taktik.core.shared.phone_interaction import Phone
from taktik.core.social_media.x.services.browsing.navigation import (
    X,
    XError,
    _alignment,
)
from taktik.core.social_media.x.ui.screen import read_screen

FIXTURES = Path(__file__).with_name("fixtures")


def document(name):
    return xml_fixture(FIXTURES / f"{name}.xml")


def test_short_video_scroll_budget_preserves_overlap_when_body_leaves():
    phone = Mock(spec=Phone)
    app = X(phone)
    before = read_screen(document("short-video-overlap-before"), (1080, 2340))
    video = before.posts[0].media[0].visibility.bounds
    app._gesture(before, "up")
    distance = phone.gesture.call_args.kwargs["distance"]
    assert 100 < distance <= (video[3] - video[1]) * 0.75


def test_original_disjoint_video_endpoint_remains_unverified():
    before, after = (
        read_screen(document(f"short-video-overlap-{stage}"), (1080, 2340))
        for stage in ("before", "after")
    )
    with pytest.raises(XError, match="Cannot uniquely verify"):
        _alignment(before, after, scrolling=True)
