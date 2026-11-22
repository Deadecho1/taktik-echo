"""Shared expansion replay for named regression scenarios."""

import json
from types import SimpleNamespace

from lxml import etree
from PIL import Image
from unit.paths import CORE
from unit.social_media.x.services.inspection_replay import InspectionReplay
from unit.social_media.x.services.search_replay import document as search_document
from unit.x_fixtures import SIZE, xml_fixture

from taktik.core.shared.behavior.tap import free_tap_zone
from taktik.core.shared.vision.ocr import OcrService, TextMatch
from taktik.core.social_media.x.services.browsing import expansion
from taktik.core.social_media.x.services.browsing.browser import XBrowser
from taktik.core.social_media.x.services.browsing.navigation import X
from taktik.core.social_media.x.ui.screen import read_screen

FIXTURES = CORE / "tests/unit/social_media/x/fixtures/expansion"


QUERY = "from:OpenAI -filter:replies"


TAP = (526, 942, 618, 964)


def document(name):
    return xml_fixture(FIXTURES / f"{name}.xml")


def mutate(xml, xpath, attr, value):
    root = etree.fromstring(xml.encode())
    for node in root.xpath(xpath):
        node.set(attr, value)
    return etree.tostring(root, encoding="unicode")


class ExpansionReplay(InspectionReplay):
    def __init__(self):
        super().__init__()
        self.results = self.latest = document("source")
        self.expanded = document("expanded")
        self.restored = document("return")
        self.detail = document("detail")
        self.expansion_error = None

    def tap(self, target, exclude, kind):
        if target == TAP:
            assert free_tap_zone(target, exclude) == target
            self.events.append(("expand", target))
            self.xml = self.expanded
            if self.expansion_error:
                raise self.expansion_error
            return
        super().tap(target, exclude, kind)


def started(monkeypatch, wrapper=False):
    replay = ExpansionReplay()
    words = [
        TextMatch(**row) for row in json.loads((FIXTURES / "words.json").read_text())
    ]

    def locate(image, queries, **kwargs):
        assert image.size == SIZE and kwargs["region"] == (176, 533, 1047, 985)
        return words

    monkeypatch.setattr(OcrService, "locate", locate)
    if wrapper:
        for field in ("results", "expanded", "restored"):
            xml = getattr(replay, field)
            xml = mutate(xml, './/*[@content-desc="Latest"]/..', "selected", "false")
            xml = mutate(xml, './/*[@content-desc="Top"]/..', "selected", "true")
            setattr(replay, field, xml)
        app = XBrowser(replay.phone, {"search"})
        app.start("fixture_owner", "search", QUERY)
    else:
        app = X(replay.phone)
        app.start("fixture_owner", "search", query=QUERY, result_tab="latest")
    return replay, app


LIMIT_TAP = (568, 1647, 660, 1669)


class LimitReplay(InspectionReplay):
    def __init__(self):
        super().__init__()
        self.xml = document("soak-source")
        self.expanded = document("soak-expanded")

    def tap(self, target, exclude, kind):
        if target == LIMIT_TAP:
            assert free_tap_zone(target, exclude) == target
            self.events.append(("expand", target))
            self.xml = self.expanded
        else:
            super().tap(target, exclude, kind)

    def command(self, name, value):
        super().command(name, value)
        if name == "launch":
            # Separate startup capture, not a physical return to the expanded post.
            self.xml = search_document("for-you")


def limit_selected(monkeypatch):
    replay = LimitReplay()
    browser = XBrowser(replay.phone, {"for_you"})
    app = browser.browser
    app.timeline = "for_you"
    app.verified_account = app._expected = "@fixture_owner"
    screen = read_screen(replay.xml, SIZE)
    index = next(
        i for i, p in enumerate(screen.posts) if p.body and p.body.endswith("Show more")
    )
    app._select(screen, index)
    browser.workflow, browser._username, browser._valid = (
        "for_you",
        "fixture_owner",
        True,
    )
    monkeypatch.setattr(expansion, "_target", lambda *_: LIMIT_TAP)
    return replay, browser


AREA = (176, 1636, 1047, 2001)


WORDS = [
    TextMatch("Show", 96.177139, 416, 1974, 103, 31),
    TextMatch("more", 96.734894, 532, 1983, 93, 22),
]


def locate(monkeypatch, words=WORDS, area=AREA, size=SIZE):
    regions = []

    def ocr(image, queries, **kwargs):
        assert kwargs["min_confidence"] == 70
        regions.append(kwargs["region"])
        return words

    monkeypatch.setattr(OcrService, "locate", ocr)
    source = SimpleNamespace(body_visibility=SimpleNamespace(bounds=area))
    return expansion._target(source, Image.new("RGB", size)), regions
