"""Shared link transport for named regression scenarios."""

from unit.social_media.x.services.android_replay import AndroidReplay
from unit.social_media.x.services.inspection_inputs import link_document as document
from unit.x_fixtures import SIZE

from taktik.core.shared.phone_interaction import (
    Phone,
)
from taktik.core.shared.phone_interaction._device import TaktikDevice
from taktik.core.social_media.x.services.browsing.browser import XBrowser
from taktik.core.social_media.x.ui.screen import read_screen


class GlyphLinkReplay(AndroidReplay):
    def __init__(self):
        super().__init__()
        self.state = "source"
        self.share_error = self.copy_error = None
        self.controls = []
        self.frames = {
            "source": document("share-glyph-complete-source"),
            "share": document("share-glyph-sheet"),
            "receipt": document("share-glyph-receipt"),
        }

    def dump_hierarchy(self):
        return self.frames[self.state]

    def long_click(self, x, y, duration):
        self.actions.append((self.state, x, y))
        if self.state == "source":
            self.controls.append("Share")
            if 1003 <= x < 1047 and 1928 <= y < 1972:
                self.state = "share"
            if self.share_error:
                raise self.share_error
        elif self.state == "share":
            for label, region, following in (
                ("Copy link", (220, 1996, 418, 2230), "receipt"),
                ("Close sheet", (0, 136, 1080, 545), "source"),
            ):
                if region[0] <= x < region[2] and region[1] <= y < region[3]:
                    self.controls.append(label)
                    self.state = following
                    if label == "Copy link" and self.copy_error:
                        raise self.copy_error
                    break
            else:
                raise AssertionError("The tap missed the verified sheet controls.")
        else:
            raise AssertionError("No additional native mutation is expected.")


def glyph_browser(raw=None):
    raw = raw or GlyphLinkReplay()
    phone = Phone(
        TaktikDevice(raw, "fixture"),
        seed=0,
        clock=lambda: raw.now,
        sleep=raw.sleep,
    )
    browser = XBrowser(phone, {"for_you"})
    app = browser.browser
    app.timeline = "for_you"
    app.verified_account = app._expected = "@fixture_owner"
    screen = read_screen(raw.dump_hierarchy(), SIZE)
    app._select(
        screen,
        next(
            i for i, post in enumerate(screen.posts) if post.author == "@fixture_author"
        ),
    )
    browser.workflow, browser._username, browser._valid = (
        "for_you",
        "fixture_owner",
        True,
    )
    return raw, browser
