"""Captured inline expansion through the same Phone interface used on Android."""

import json
from dataclasses import replace

import pytest
from lxml import etree
from unit.paths import CORE
from unit.social_media.x.services.browsing.test_inspection_visits import (
    InspectionReplay,
)

from taktik.core.shared.behavior.tap import free_tap_zone
from taktik.core.shared.phone_interaction import (
    InteractionCancelled,
    InteractionError,
    Result,
    Status,
)
from taktik.core.shared.vision.ocr import OcrService, TextMatch
from taktik.core.social_media.x.services.browsing.browser import XBrowser
from taktik.core.social_media.x.services.browsing.navigation import X, XError

FIXTURES = CORE / "tests/unit/social_media/x/fixtures/expansion"
SIZE = (1080, 2340)
QUERY = "from:OpenAI -filter:replies"
TAP = (526, 942, 618, 964)


def document(name):
    return (FIXTURES / f"{name}.xml").read_text()


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
        assert image.size == SIZE and kwargs["region"] == (176, 533, 1047, 974)
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


def test_inline_expansion_retains_author_context_and_supports_detail_return(
    monkeypatch,
):
    replay, app = started(monkeypatch)
    before = app.observe()
    app.read_more()
    after = app.observe()
    assert after.author == before.author == "@OpenAI"
    assert after.body_complete and after.body.startswith(
        before.body.removesuffix("\xa0Show more")
    )
    assert "patient outreach" in after.body
    assert app.query == QUERY and app.result_tab == "latest"
    assert [event for event in replay.events if event[0] == "expand"] == [
        ("expand", TAP)
    ]
    thread = app.inspect_thread(max_scrolls=0)
    assert thread.detail.main_post is None and not thread.main_verified
    assert app.observe().content_key == after.content_key


def test_browser_read_more_preserves_occurrence_identity_and_marks_expanded_caption(
    monkeypatch,
):
    _replay, app = started(monkeypatch, wrapper=True)
    before = app.observe()
    app.act("read_more", before)
    after = app.observe(previous=before)
    assert after.identity == before.identity and after.caption_expanded
    assert after.source_key != before.source_key
    assert after.caption_type == "full" and after.caption != before.caption
    app.inspect_thread(after, max_scrolls=0)
    assert app.observe(previous=after).caption == after.caption


@pytest.mark.parametrize(
    "change",
    ["author", "prefix", "query", "tab", "header", "body_origin", "media", "duplicate"],
)
def test_expansion_rejects_wrong_post_content_context_or_geometry(monkeypatch, change):
    replay, app = started(monkeypatch)
    changes = {
        "author": ('.//*[@text="@OpenAI"]', "text", "@someone_else"),
        "prefix": (
            './/*[@text and starts-with(@text,"ChatGPT for Healthcare")]',
            "text",
            "Different expanded content.",
        ),
        "query": ('.//*[@text="from:OpenAI -filter:replies"]', "text", "unrelated"),
        "tab": ('.//*[@content-desc="Latest"]/..', "selected", "false"),
        "header": (
            './/*[@resource-id="timeline_post"]',
            "bounds",
            "[176,478][876,527]",
        ),
        "body_origin": (
            './/*[@text and starts-with(@text,"ChatGPT for Healthcare")]',
            "bounds",
            "[176,534][1047,1416]",
        ),
        "media": ('.//*[@content-desc="Video"]', "content-desc", "GIF"),
    }
    if change == "duplicate":
        root = etree.fromstring(replay.expanded.encode())
        node = root.xpath('.//*[@resource-id="timeline_post"]/..')[0]
        node.addnext(etree.fromstring(etree.tostring(node)))
        replay.expanded = etree.tostring(root, encoding="unicode")
    else:
        replay.expanded = mutate(replay.expanded, *changes[change])
    with pytest.raises(XError):
        app.read_more()
    assert app.verified_account is None
    assert len([e for e in replay.events if e[0] == "expand"]) == 1


@pytest.mark.parametrize(
    "words",
    [
        [],
        [TextMatch("Show", 99, 410, 933, 102, 31)],
        [
            TextMatch("Show", 99, 410, 933, 102, 31),
            TextMatch("more", 99, 526, 700, 92, 22),
        ],
    ],
)
def test_missing_or_unaligned_control_never_taps(monkeypatch, words):
    replay, app = started(monkeypatch)
    monkeypatch.setattr(OcrService, "locate", lambda *a, **kw: words)
    with pytest.raises(XError):
        app.read_more()
    assert not any(e[0] == "expand" for e in replay.events)


def test_source_is_reverified_after_ocr_before_tapping(monkeypatch):
    replay, app = started(monkeypatch)
    replay.after_capture = lambda: setattr(replay, "xml", document("expanded"))
    with pytest.raises(XError):
        app.read_more()
    assert not any(e[0] == "expand" for e in replay.events)


@pytest.mark.parametrize(
    "error",
    [
        InteractionCancelled("cancelled"),
        InteractionError("uncertain", result=Result(Status.UNCERTAIN)),
    ],
)
def test_cancelled_or_uncertain_expansion_is_never_retried(monkeypatch, error):
    replay, app = started(monkeypatch)
    replay.expansion_error = error
    with pytest.raises(type(error)):
        app.read_more()
    assert app.verified_account is None
    assert len([e for e in replay.events if e[0] == "expand"]) == 1


def test_already_complete_caption_is_a_noop(monkeypatch):
    replay, app = started(monkeypatch)
    app.read_more()
    before = list(replay.events)
    app.read_more()
    assert replay.events == before


def test_failed_expansion_does_not_claim_a_full_caption(monkeypatch):
    replay, app = started(monkeypatch)
    replay.expanded = replay.results
    with pytest.raises(XError):
        app.read_more()
    assert app.verified_account is None


def test_clipped_expansion_remains_unavailable_as_an_observation(monkeypatch):
    replay, app = started(monkeypatch)
    replay.expanded = mutate(
        replay.expanded,
        './/*[starts-with(@text,"ChatGPT for Healthcare")]',
        "bounds",
        "[176,533][1047,2340]",
    )
    with pytest.raises(XError, match="visible|viewport|clipped"):
        app.read_more()
    assert app.verified_account is None


def test_browser_uses_verified_source_key_when_observation_metadata_is_stale(
    monkeypatch,
):
    _replay, app = started(monkeypatch, wrapper=True)
    before = app.observe()
    app.read_more(replace(before, source_key="incorrect source metadata"))
    assert app.observe().identity == before.identity


def test_new_search_clears_expanded_caption_state(monkeypatch):
    _replay, app = started(monkeypatch, wrapper=True)
    before = app.observe()
    app.read_more(before)
    app.start("fixture_owner", "search", QUERY)
    after = app.observe()
    assert not after.caption_expanded and after.identity != before.identity
    assert after.caption == before.caption


def test_duplicate_control_matches_never_tap(monkeypatch):
    replay, app = started(monkeypatch)
    words = [
        TextMatch(**row) for row in json.loads((FIXTURES / "words.json").read_text())
    ]
    monkeypatch.setattr(OcrService, "locate", lambda *a, **kw: [*words, words[-1]])
    with pytest.raises(XError):
        app.read_more()
    assert not any(e[0] == "expand" for e in replay.events)


def test_deadline_after_capture_prevents_expansion_tap(monkeypatch):
    replay, app = started(monkeypatch)
    replay.phone.configure(deadline=100)
    replay.after_capture = lambda: setattr(replay, "now", 101)
    with pytest.raises(InteractionCancelled):
        app.read_more()
    assert not any(e[0] == "expand" for e in replay.events)


def test_final_expansion_read_rejects_a_changed_post(monkeypatch):
    replay, app = started(monkeypatch)
    read = replay.read
    reads = 0

    def changed(what):
        nonlocal reads
        if what == "hierarchy" and replay.xml == replay.expanded:
            reads += 1
            if reads == 2:
                replay.xml = mutate(
                    replay.expanded, './/*[@text="@OpenAI"]', "text", "@someone_else"
                )
        return read(what)

    replay.read = changed
    with pytest.raises(XError):
        app.read_more()
    assert app.verified_account is None


@pytest.mark.parametrize("timing", ["before_ocr", "after_ocr"])
def test_expansion_preserves_current_native_control_exclusions(monkeypatch, timing):
    replay, app = started(monkeypatch)
    control_bounds = (
        "[176,533][1047,974]" if timing == "before_ocr" else "[526,942][618,964]"
    )

    def cover():
        replay.xml = mutate(
            replay.xml,
            '(.//*[@content-desc="Post options"])[1]',
            "bounds",
            control_bounds,
        )

    if timing == "before_ocr":
        cover()
    else:
        replay.after_capture = cover
    with pytest.raises(XError, match="covered"):
        app.read_more()
    assert not any(e[0] == "expand" for e in replay.events)
