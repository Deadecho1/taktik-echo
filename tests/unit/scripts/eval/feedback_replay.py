"""Shared feedback replay for named regression scenarios."""

from unit.paths import CORE
from unit.social_media.x.services.android_replay import AndroidReplay
from unit.x_fixtures import SIZE, xml_fixture

from taktik.core.shared.phone_interaction import (
    Phone,
)
from taktik.core.shared.phone_interaction._device import TaktikDevice
from taktik.core.social_media.x.services.browsing.browser import XBrowser
from taktik.core.social_media.x.ui.screen import read_screen

FIXTURES = CORE / "tests/unit/social_media/x/fixtures/engagement"


def document(name):
    return xml_fixture(FIXTURES / f"undo-{name}.xml")


class FeedbackReplay(AndroidReplay):
    def __init__(self):
        super().__init__()
        self.documents = {
            name: document(name)
            for name in ("source", "options", "receipt", "framing", "successor")
        }
        self.xml = self.documents["source"]
        self.stage = "source"
        self.phone = Phone(
            TaktikDevice(self, "fixture"),
            seed=0,
            clock=lambda: self.now,
            sleep=self.sleep,
        )

    def dump_hierarchy(self):
        return self.xml

    def long_click(self, x, y, duration):
        self.actions.append(("tap", self.stage))
        if self.stage == "source":
            assert 1019 <= x < 1080 and 957 <= y < 1006
            self.stage = "options"
        elif self.stage == "options":
            assert 0 <= x < 1080 and 888 <= y < 1042
            self.stage = "receipt"
        elif self.stage == "receipt":
            assert 853 <= x < 1047 and 988 <= y < 1120
            self.stage = "source"
        else:
            raise AssertionError("Cannot tap after framing away the Undo receipt.")
        self.xml = self.documents[self.stage]

    def swipe_points(self, path, duration):
        self.actions.append(("scroll", self.stage))
        self.stage = "framing" if self.stage == "receipt" else "successor"
        self.xml = self.documents[self.stage]


class CompleteFeedbackReplay(FeedbackReplay):
    def __init__(self):
        super().__init__()
        self.documents = {
            name: document(f"complete-{name}")
            for name in ("source", "options", "transition", "receipt", "restored")
        }
        self.xml = self.documents["source"]
        self.pending = []

    def dump_hierarchy(self):
        if self.pending:
            self.xml = self.documents[self.pending.pop(0)]
        return self.xml

    def long_click(self, x, y, duration):
        self.actions.append(("tap", self.stage))
        if self.stage == "source":
            assert 1019 <= x < 1080 and 623 <= y < 672
            self.stage = "options"
        elif self.stage == "options":
            assert 0 <= x < 1080 and 888 <= y < 1042
            self.stage = "receipt"
            self.pending = ["transition", "receipt"]
        elif self.stage == "receipt":
            assert 853 <= x < 1047 and 654 <= y < 786
            self.stage = "restored"
        else:
            raise AssertionError("Unexpected extra tap after verified restoration.")
        self.xml = self.documents[self.stage]

    def swipe_points(self, path, duration):
        raise AssertionError("The complete round trip must not frame a successor.")


def selected(replay=None):
    replay = replay or FeedbackReplay()
    browser = XBrowser(replay.phone, {"for_you"})
    app = browser.browser
    app.timeline = "for_you"
    app.verified_account = app._expected = "@fixture_owner"
    screen = read_screen(replay.xml, SIZE)
    source = screen.observable_posts[0]
    app._select(screen, screen.posts.index(source))
    browser.workflow, browser._username, browser._valid = (
        "for_you",
        "fixture_owner",
        True,
    )
    return replay, browser
