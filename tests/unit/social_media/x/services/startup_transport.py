"""Shared startup transport for named regression scenarios."""

from lxml import etree
from unit.paths import CORE
from unit.social_media.x.services.android_replay import AndroidReplay
from unit.x_fixtures import xml_fixture

from taktik.core.social_media.x.ui.screen import PACKAGE

FIXTURES = CORE / "tests/unit/social_media/x/fixtures/startup"


def document(name):
    return xml_fixture(FIXTURES / f"drawer-tip{name}.xml")


class RawStartup(AndroidReplay):
    def __init__(self):
        super().__init__()
        self.home, self.drawer = document("-home"), document("")
        self.stage = "home"
        self.reads = []
        self.close_error = None
        self.close_stuck = False

    def app_start(self, package):
        assert package == PACKAGE
        self.actions.append("launch")

    def dump_hierarchy(self):
        self.reads.append(self.stage)
        return self.drawer if self.stage == "drawer" else self.home

    def long_click(self, x, y, duration):
        if self.stage == "home" and 273 <= x < 558 and 301 <= y < 433:
            root = etree.fromstring(self.home.encode())
            for label, selected in (("For you", "false"), ("Following", "true")):
                node = root.xpath(".//*[@content-desc=$label]", label=label)[0]
                node.getparent().set("selected", selected)
            self.home = etree.tostring(root, encoding="unicode")
            self.actions.append("select_following")
        elif self.stage == "home":
            assert 11 <= x < 165 and 147 <= y < 301
            self.actions.append("open_drawer")
            self.stage = "drawer"
        else:
            assert 990 <= x < 1080 and 136 <= y < 2340
            self.actions.append("close_drawer")
            if self.close_error:
                raise self.close_error
            if not self.close_stuck:
                self.stage = "home"
