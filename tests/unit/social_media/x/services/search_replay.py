"""Shared search replay for named regression scenarios."""

from lxml import etree
from unit.paths import CORE
from unit.x_fixtures import SIZE, xml_fixture

from taktik.core.shared.phone_interaction import (
    Phone,
    TextField,
)
from taktik.core.shared.ui.geometry import bounds
from taktik.core.social_media.x.ui.screen import PACKAGE, read_screen

FIXTURES = CORE / "tests/unit/social_media/x/fixtures/search"


def document(name):
    return xml_fixture(FIXTURES / f"{name}.xml")


def changed_query(xml, query):
    root = etree.fromstring(xml.encode())
    for node in root.xpath('.//*[@text="astronomy"]'):
        node.set("text", query)
    return etree.tostring(root, encoding="unicode")


def shifted_results(distance):
    root = etree.fromstring(document("search-latest").encode())
    containers = root.xpath(
        './/*[@resource-id="Search"]/node/node[@scrollable="true"]'
        '/node[@scrollable="true"]/node'
    )
    for container in containers:
        for node in container.iter():
            left, top, right, bottom = bounds(node)
            node.set(
                "bounds", f"[{left},{top + distance}][{right},{bottom + distance}]"
            )
    return etree.tostring(root, encoding="unicode")


class SearchReplay:
    def __init__(self):
        self.xml = document("for-you")
        self.events = []
        self.results = document("search-top")
        self.query_input = document("search-empty")
        self.explore = document("explore")
        self.latest = document("search-latest")
        self.scrolls = []
        self.typing_error = None
        self.typed_transform = lambda xml: xml
        self.tap_error = None
        self.enter_error = None
        self.tab_stuck = False
        self.now = 0
        self.closed = False
        self.phone = Phone(self, clock=lambda: self.now, sleep=self.sleep)

    def bind(self, phone):
        self.phone = phone

    def sleep(self, seconds):
        self.now += seconds

    def read(self, what):
        return {"hierarchy": self.xml, "size": SIZE, "app": {"package": PACKAGE}}[what]

    def tap(self, target, exclude, kind):
        screen = read_screen(self.xml, SIZE)
        matches = [
            c.label for c in screen.controls if c.visibility.visible_bounds == target
        ]
        assert len(matches) == 1, matches
        label = matches[0]
        self.events.append(("tap", label))
        if self.tap_error:
            raise self.tap_error
        transitions = {
            "Show navigation drawer": "account-drawer",
            "Close navigation menu": "for-you",
            "Home": "for-you",
            "Explore": "explore",
            "Search": "search-empty",
        }
        if label == "Latest":
            if not self.tab_stuck:
                self.xml = self.latest
        elif label in {"Search", "Back"}:
            self.xml = self.query_input
        elif label == "Explore":
            self.xml = self.explore
        else:
            self.xml = document(transitions[label])

    def command(self, name, value):
        self.events.append((name, value))
        if name == "enter":
            self.xml = self.results
            if self.enter_error:
                raise self.enter_error
        elif name == "back":
            self.xml = document("explore")

    def enter_text(self, field, text, submit):
        self.events.append(("type", field, text))
        assert field == TextField(PACKAGE, "SearchQuery")
        if self.typing_error:
            raise self.typing_error
        self.xml = self.typed_transform(
            changed_query(document("search-suggestions"), text)
        )
        submit().require()
        return text

    def gesture(self, intent, direction, region, distance, exclude):
        self.events.append(("gesture", intent, direction, region, distance, exclude))
        if self.scrolls:
            self.xml = self.scrolls.pop(0)

    def close(self):
        self.closed = True
