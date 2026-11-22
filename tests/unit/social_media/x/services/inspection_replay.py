"""Shared inspection replay for named regression scenarios."""

from lxml import etree
from PIL import Image
from unit.social_media.x.services.inspection_inputs import document
from unit.social_media.x.services.search_replay import SearchReplay
from unit.x_fixtures import SIZE

from taktik.core.shared.behavior.tap import free_tap_zone
from taktik.core.social_media.x.services.browsing.browser import XBrowser
from taktik.core.social_media.x.services.browsing.navigation import X
from taktik.core.social_media.x.ui.screen import PACKAGE, read_screen


class InspectionReplay(SearchReplay):
    def __init__(self, image=False):
        super().__init__()
        self.results = document("image-source" if image else "text-source")
        self.latest = self.results
        self.restored = document("image-return" if image else "text-return")
        self.profile = document("profile")
        self.detail = document("image-detail" if image else "text-detail")
        self.gallery = document("image-gallery")
        self.package = PACKAGE
        self.after_capture = None
        self.capture_error = None
        self.visit_error = None
        self.back_error = None
        self.capture_count = 0

    def read(self, what):
        if what == "screen_reader_hierarchy":
            return self.xml
        if what == "app":
            return {"package": self.package}
        if what == "screenshot":
            self.capture_count += 1
            if self.capture_error:
                raise self.capture_error
            if self.after_capture:
                self.after_capture()
            return Image.new("RGB", SIZE, "navy")
        return super().read(what)

    def tap(self, target, exclude, kind):
        assert free_tap_zone(target, exclude) is not None
        screen = read_screen(self.xml, SIZE)
        if screen.kind in {"profile", "detail", "media"}:
            assert target == next(
                t.visibility.visible_bounds
                for t in screen.controls
                if t.label == "Back"
            )
            self.events.append(("tap", "inspection Back"))
            self.xml = self.restored
            if self.back_error:
                raise self.back_error
            return
        matches = [
            t
            for p in screen.posts
            for t in p.targets
            if t.visibility.visible_bounds is not None
            and t.visibility.overlaps == tuple(exclude)
            and t.visibility.visible_bounds[0]
            <= target[0]
            < target[2]
            <= t.visibility.visible_bounds[2]
            and t.visibility.visible_bounds[1]
            <= target[1]
            < target[3]
            <= t.visibility.visible_bounds[3]
        ]
        if matches:
            assert len(matches) == 1
            selected = matches[0]
            assert tuple(exclude) == selected.visibility.overlaps
            self.events.append(("visit", selected.label))
            self.xml = {
                "Visit author": self.profile,
                "Open post": self.detail,
                "Open media 0": self.gallery,
            }[selected.label]
            if self.visit_error:
                raise self.visit_error
            return
        super().tap(target, exclude, kind)

    def command(self, name, value):
        if name == "back" and read_screen(self.xml, SIZE).kind == "detail":
            self.events.append(("back", None))
            self.xml = self.restored
            if self.back_error:
                raise self.back_error
            return
        super().command(name, value)


def started(image=False, wrapper=False):
    replay = InspectionReplay(image)
    app = XBrowser(replay.phone, {"search"}) if wrapper else X(replay.phone)
    query = "from:NASA filter:images -filter:replies" if image else "from:NASA"
    if wrapper:
        app.browser.result_tab = "latest"
        # XBrowser opens Top; the captured tab is changed without altering content.
        root = etree.fromstring(replay.results.encode())
        for label in ("Top", "Latest"):
            node = root.xpath(".//*[@content-desc=$label]", label=label)[0].getparent()
            node.set("selected", "true" if label == "Top" else "false")
        replay.results = etree.tostring(root, encoding="unicode")
        replay.restored = replay.results
        app.start("fixture_owner", "search", query)
    else:
        app.start("fixture_owner", "search", query=query, result_tab="latest")
    return replay, app
