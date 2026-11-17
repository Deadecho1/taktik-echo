"""A prior video's disappearing credit does not change the selected post."""

from dataclasses import replace
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from taktik.core.shared.phone_interaction import Phone, Result, Status
from taktik.core.social_media.x.services.browsing.navigation import (
    X,
    XError,
    _alignment,
)
from taktik.core.social_media.x.ui.screen import read_screen


def document(name):
    return (Path(__file__).with_name("fixtures") / f"{name}.xml").read_text()


def captured_app(name):
    device = SimpleNamespace(
        document=document(name), scrolls=[], phone=Mock(spec=Phone)
    )

    def read(what):
        return {
            "app": {"package": "com.twitter.android"},
            "size": (1080, 2340),
            "hierarchy": device.document,
        }[what]

    def gesture(*args, **kwargs):
        if device.scrolls:
            device.document = device.scrolls.pop(0)
        return Result(Status.SUCCESS)

    device.phone.read.side_effect = read
    device.phone.gesture.side_effect = gesture
    app = X(device.phone)
    app.timeline, app.verified_account = "for_you", "@fixture_owner"
    app._select(read_screen(device.document, (1080, 2340)), 0)
    return app, device


def screen(stage):
    return read_screen(document(f"prior-credit-refresh-{stage}"), (1080, 2340))


def test_observe_keeps_selected_post_when_prior_stationary_credit_fades():
    app, device = captured_app("prior-credit-refresh-before")
    app._index = 1
    selected = app._screen.posts[1]
    device.document = document("prior-credit-refresh-after")
    assert app.observe() == selected
    assert app._screen.posts[0].media[0].source_label is None
    assert app.verified_account == "@fixture_owner"
    device.phone.gesture.assert_not_called()


def test_selected_post_credit_change_still_invalidates_refresh():
    app, device = captured_app("prior-credit-refresh-before")
    device.document = document("prior-credit-refresh-after")
    with pytest.raises(XError, match="changed outside"):
        app.observe()
    assert app.verified_account is None


@pytest.mark.parametrize(
    "mutation",
    ["author", "body", "description", "source", "motion", "footer", "header"],
)
def test_refresh_credit_exception_preserves_identity_and_static_geometry(mutation):
    before, after = screen("before"), screen("after")
    p = after.posts[0]
    m = p.media[0]
    if mutation == "author":
        p = replace(p, author="@changed")
    elif mutation == "body":
        p = replace(p, body="Unexpected body")
    elif mutation == "description":
        p = replace(p, media=(replace(m, description="Changed video"),))
    elif mutation == "source":
        p = replace(p, media=(replace(m, source_label="New source"),))
    elif mutation == "motion":
        x1, y1, x2, y2 = m.visibility.bounds
        p = replace(
            p,
            media=(
                replace(
                    m,
                    visibility=replace(m.visibility, bounds=(x1, y1 - 10, x2, y2 - 10)),
                ),
            ),
        )
    elif mutation == "footer":
        t = p.actions[0]
        x1, y1, x2, y2 = t.visibility.bounds
        p = replace(
            p,
            actions=(
                replace(
                    t, visibility=replace(t.visibility, bounds=(x1, y1 - 10, x2, y2))
                ),
                *p.actions[1:],
            ),
        )
    else:
        v = p.header_visibility
        x1, y1, x2, y2 = v.bounds
        p = replace(p, header_visibility=replace(v, bounds=(x1, y1 - 10, x2, y2)))
    with pytest.raises(XError):
        _alignment(before, replace(after, posts=(p, *after.posts[1:])), refresh_index=1)
