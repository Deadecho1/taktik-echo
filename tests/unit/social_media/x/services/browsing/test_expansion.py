"""Captured inline expansion through the same Phone interface used on Android."""

import json
import subprocess
from dataclasses import replace

import pytest
from lxml import etree
from PIL import Image
from unit.social_media.x.services.expansion_replay import (
    AREA,
    FIXTURES,
    LIMIT_TAP,
    QUERY,
    TAP,
    WORDS,
    document,
    limit_selected,
    locate,
    mutate,
    started,
)
from unit.social_media.x.services.inspection_replay import InspectionReplay
from unit.social_media.x.services.startup_transport import RawStartup
from unit.x_fixtures import SIZE, fixture_manifest, xml_fixture

from scripts.eval.x_caption_validation import check_caption
from taktik.core.shared.behavior.tap import free_tap_zone
from taktik.core.shared.phone_interaction import (
    InteractionCancelled,
    InteractionError,
    Phone,
    Result,
    Status,
)
from taktik.core.shared.phone_interaction._device import TaktikDevice
from taktik.core.shared.vision.ocr import OcrService, TextMatch
from taktik.core.social_media.x.services.browsing import expansion
from taktik.core.social_media.x.services.browsing.browser import XBrowser
from taktik.core.social_media.x.services.browsing.navigation import XError
from taktik.core.social_media.x.ui.screen import _intersect, read_screen


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


def test_captured_limit_is_typed_only_after_source_verification(monkeypatch):
    replay, browser = limit_selected(monkeypatch)
    before = browser.observe()
    with pytest.raises(XError) as raised:
        browser.read_more(before)
    assert type(raised.value).__name__ == "XInlineExpansionLimit"
    assert not browser.browsing_valid
    assert replay.events == [("expand", LIMIT_TAP)]
    post = next(
        p for p in read_screen(replay.xml, SIZE).posts if len(p.body or "") == 3143
    )
    assert not post.observable and not post.body_complete


@pytest.mark.parametrize(
    "change",
    [
        "author",
        "header",
        "origin",
        "prefix",
        "tab",
        "duplicate",
        "overlay",
        "inaccessible",
        "disabled",
        "ancestor_clip",
    ],
)
def test_changed_or_ambiguous_source_is_not_a_recoverable_viewport_limit(
    monkeypatch, change
):
    replay, browser = limit_selected(monkeypatch)
    source = browser.observe()
    root = etree.fromstring(replay.expanded.encode())
    body = next(n for n in root.iter("node") if len(n.get("text", "")) == 3143)
    header = root.xpath('.//*[@resource-id="timeline_post"]')[-1]
    if change == "author":
        replay.expanded = replay.expanded.replace(
            "@" + source.username, "@someone_else"
        )
    else:
        if change == "header":
            header.set("bounds", "[176,920][876,970]")
        elif change == "origin":
            body.set("bounds", "[176,1081][1047,2340]")
        elif change == "prefix":
            body.set("text", "Unrelated text" * 300)
        elif change in {"inaccessible", "disabled"}:
            body.set(
                "visible-to-user" if change == "inaccessible" else "enabled", "false"
            )
        elif change == "ancestor_clip":
            body.getparent().set("bounds", "[0,908][1080,1500]")
        elif change == "tab":
            root.xpath('.//*[@resource-id="scaffold_home_tabbed"]')[0].set(
                "resource-id", "unknown_context"
            )
        elif change == "duplicate":
            container = header.getparent()
            container.addnext(etree.fromstring(etree.tostring(container)))
        elif change == "overlay":
            etree.SubElement(
                root,
                "node",
                package="external.app",
                text="Unknown dialog",
                bounds="[0,0][1080,2340]",
                **{"visible-to-user": "true"},
            )
        replay.expanded = etree.tostring(root, encoding="unicode")
    with pytest.raises(XError) as raised:
        browser.read_more(source)
    assert not isinstance(raised.value, expansion.XInlineExpansionLimit)
    assert not browser.browsing_valid
    assert replay.events.count(("expand", LIMIT_TAP)) == 1


def test_clipped_expansion_with_changed_visible_media_remains_unclassified(monkeypatch):
    replay, app = started(monkeypatch)
    replay.expanded = mutate(
        replay.expanded,
        './/*[starts-with(@text,"ChatGPT for Healthcare")]',
        "bounds",
        "[176,533][1047,2340]",
    )
    replay.expanded = mutate(
        replay.expanded, './/*[@content-desc="Video"]', "content-desc", "GIF"
    )
    with pytest.raises(XError) as raised:
        app.read_more()
    assert not isinstance(raised.value, expansion.XInlineExpansionLimit)


TARGET = (532, 1983, 625, 2001)


class CropReplay(InspectionReplay):
    def __init__(
        self, *, source="crop-edge-source", area=AREA, target=TARGET, expanded=None
    ):
        super().__init__()
        self.xml = document(source)
        self.area, self.target, self.expanded = area, target, expanded
        self.error = None

    def tap(self, target, exclude, kind):
        assert target == self.target
        assert _intersect(target, self.area) == target
        assert free_tap_zone(target, exclude) == target
        self.events.append(("expand", target))
        if self.error:
            raise self.error
        # Without captured post-tap evidence, unchanged XML must fail verification.
        if self.expanded:
            self.xml = self.expanded


def selected(replay=None):
    replay = replay or CropReplay()
    screen = read_screen(replay.xml, SIZE)
    workflow = "search" if screen.kind == "search_results" else "for_you"
    browser = XBrowser(replay.phone, {workflow})
    app = browser.browser
    app.timeline = workflow
    if workflow == "search":
        app.query, app.result_tab = screen.query, screen.tab.lower()
        browser.target = screen.query
    app.verified_account = app._expected = "@fixture_owner"
    app._select(
        screen,
        next(
            i
            for i, p in enumerate(screen.posts)
            if p.body_visibility.bounds == replay.area
        ),
    )
    browser.workflow, browser._username, browser._valid = (
        workflow,
        "fixture_owner",
        True,
    )
    return replay, browser


def captured_ocr(monkeypatch):
    calls = []
    monkeypatch.setattr(OcrService, "_resolve_tesseract_cmd", lambda: "tesseract")

    def tsv(command, image, **kwargs):
        calls.append(image.size)
        assert kwargs["timeout_seconds"] == 5.0
        name = "body" if image.height == 365 else "context"
        assert image.size in {(871, 365), (871, 376)}
        return (FIXTURES / f"crop-edge-{name}.tsv").read_text()

    monkeypatch.setattr(OcrService, "_image_to_tsv", tsv)
    return calls


def test_captured_translated_caption_locates_safe_target_without_inventing_expansion(
    monkeypatch,
):
    calls = captured_ocr(monkeypatch)
    replay, browser = selected()
    source = browser.observe()
    coverage = []
    with pytest.raises(XError):
        check_caption(
            browser, source, features={}, covered=lambda *args: coverage.append(args)
        )
    assert replay.events == [("expand", TARGET)]
    assert calls == [(871, 376)]
    assert not coverage and not browser.browsing_valid


@pytest.mark.parametrize("scale", [0.5, 1, 2])
def test_context_scales_with_screen_but_target_stays_inside_body(monkeypatch, scale):
    def scaled(values):
        return tuple(int(value * scale) for value in values)

    words = [
        TextMatch(w.text, w.confidence, *scaled((w.left, w.top, w.width, w.height)))
        for w in WORDS
    ]
    target, regions = locate(monkeypatch, words, scaled(AREA), scaled(SIZE))
    assert _intersect(target, scaled(AREA)) == target
    assert target == _intersect(words[1].bbox, scaled(AREA))
    assert regions[0][:3] == scaled(AREA)[:3]
    assert 0 < regions[0][3] - scaled(AREA)[3] <= (min(scaled(SIZE)) + 99) // 100


@pytest.mark.parametrize(
    "words",
    [
        [],
        WORDS[:1],
        [replace(WORDS[0], confidence=66.541107), WORDS[1]],
        [replace(WORDS[0], confidence=float("nan")), WORDS[1]],
        [WORDS[0], replace(WORDS[1], confidence=float("inf"))],
        [replace(WORDS[0], text="Sho"), WORDS[1]],
        [WORDS[0], replace(WORDS[1], text="more…")],
        [*WORDS, WORDS[1]],
        [*WORDS, *(replace(w, left=w.left + 250) for w in WORDS)],
        [replace(w, top=w.top + 15) for w in WORDS],
        [replace(w, top=w.top + 4) for w in WORDS],
        [replace(w, top=w.top - 150) for w in WORDS],
        [replace(WORDS[0], width=0), WORDS[1]],
        [WORDS[0], replace(WORDS[1], height=-1)],
        [replace(WORDS[0], left=175), WORDS[1]],
        [WORDS[0], replace(WORDS[1], width=600)],
        [WORDS[0], replace(WORDS[1], top=1970)],
        [WORDS[0], replace(WORDS[1], left=560)],
        [replace(WORDS[0], height=100), WORDS[1]],
    ],
)
def test_ambiguous_incomplete_or_unowned_words_reject(monkeypatch, words):
    with pytest.raises(XError, match="one visible native"):
        locate(monkeypatch, words)


@pytest.mark.parametrize("bottom,accepted", [(2005, False), (2006, True), (2340, True)])
def test_screen_edge_caps_context_and_rejects_cut_glyphs(monkeypatch, bottom, accepted):
    if not accepted:
        with pytest.raises(XError):
            locate(monkeypatch, size=(1080, bottom))
    else:
        target, regions = locate(monkeypatch, size=(1080, bottom))
        assert target == TARGET and regions[0][3] <= bottom


def test_neighboring_pair_in_context_cannot_replace_the_owned_pair(monkeypatch):
    neighbors = [replace(w, top=2002, height=8) for w in WORDS]
    target, _ = locate(monkeypatch, [*WORDS, *neighbors])
    assert target == TARGET
    with pytest.raises(XError):
        locate(monkeypatch, neighbors)


@pytest.mark.parametrize("overflow,accepted", [(5, True), (6, False)])
def test_at_least_three_quarters_of_each_word_must_be_inside_body(
    monkeypatch, overflow, accepted
):
    words = [replace(w, top=AREA[3] - 20 + overflow, height=20) for w in WORDS]
    if accepted:
        target, _ = locate(monkeypatch, words)
        assert target == (532, AREA[3] - 20 + overflow, 625, AREA[3])
    else:
        with pytest.raises(XError):
            locate(monkeypatch, words)


@pytest.mark.parametrize("change", ["body", "author", "control"])
def test_fresh_source_and_exclusions_still_guard_crop_target(monkeypatch, change):
    captured_ocr(monkeypatch)
    replay, browser = selected()
    changes = {
        "body": (
            './/*[@bounds="[176,1636][1047,2001]"]',
            "bounds",
            "[176,1636][1047,2002]",
        ),
        "author": ('.//*[@text="@damsizcimcime"]', "text", "@someone_else"),
        "control": (
            './/*[@content-desc="Post options"]',
            "bounds",
            "[532,1983][625,2001]",
        ),
    }
    replay.after_capture = lambda: setattr(
        replay, "xml", mutate(replay.xml, *changes[change])
    )
    with pytest.raises(XError):
        browser.read_more(browser.observe())
    assert not replay.events and not browser.browsing_valid


@pytest.mark.parametrize("failure", ["missing", "timeout", "cancel", "deadline"])
def test_ocr_failure_or_interruption_never_injects(monkeypatch, failure):
    captured_ocr(monkeypatch)
    replay, browser = selected()
    if failure == "missing":
        monkeypatch.setattr(OcrService, "_resolve_tesseract_cmd", lambda: None)
    elif failure == "timeout":

        def timeout(*args, **kwargs):
            raise subprocess.TimeoutExpired("tesseract", 5)

        monkeypatch.setattr(OcrService, "_image_to_tsv", timeout)
    else:

        def interrupt(*args, **kwargs):
            if failure == "cancel":
                raise InteractionCancelled("cancelled")
            replay.phone.configure(deadline=replay.now)
            return WORDS

        monkeypatch.setattr(OcrService, "locate", interrupt)
    with pytest.raises(
        InteractionCancelled if failure in {"cancel", "deadline"} else XError
    ):
        browser.read_more(browser.observe())
    assert not replay.events and not browser.browsing_valid


def test_uncertain_crop_target_injection_is_not_retried(monkeypatch):
    captured_ocr(monkeypatch)
    replay, browser = selected()
    replay.error = OSError("tap response lost")
    coverage = []
    with pytest.raises(InteractionError):
        check_caption(
            browser,
            browser.observe(),
            features={},
            covered=lambda *a: coverage.append(a),
        )
    assert replay.events == [("expand", TARGET)]
    assert not coverage and not browser.browsing_valid


def same_height_selected(monkeypatch, expanded=None):
    captured_ocr(monkeypatch)
    return selected(
        CropReplay(
            source="same-height-source",
            area=(176, 605, 1047, 970),
            target=(532, 952, 625, 970),
            expanded=expanded or document("same-height-expanded"),
        )
    )


def test_captured_same_height_completion_verifies_added_text_and_keeps_occurrence(
    monkeypatch,
):
    replay, browser = same_height_selected(monkeypatch)
    source = browser.observe()
    coverage = []
    result = check_caption(
        browser, source, features={}, covered=lambda *args: coverage.append(args)
    )
    assert result.identity == source.identity and result.source_key != source.source_key
    assert result.caption == expansion.MORE.sub("", source.caption) + ' Monday?"'
    assert result.caption_expanded and result.caption_type == "full"
    assert browser.browser.observe().body_visibility.bounds == replay.area
    assert replay.events == [("expand", replay.target)]
    assert [name for name, _ in coverage] == ["inline_caption_attempt", "read_more"]


@pytest.mark.parametrize("change", ["shrunk", "author", "no_added_text", "prefix"])
def test_same_height_completion_still_requires_stable_source_and_new_text(
    monkeypatch, change
):
    xml = document("same-height-expanded")
    body = './/*[@bounds="[176,605][1047,970]" and @text!=""]'
    source = next(
        p
        for p in read_screen(document("same-height-source"), SIZE).posts
        if p.body_visibility.bounds == (176, 605, 1047, 970)
    )
    changes = {
        "shrunk": (body, "bounds", "[176,605][1047,969]"),
        "author": ('.//*[@text="@damsizcimcime"]', "text", "@another_author"),
        "no_added_text": (body, "text", expansion.MORE.sub("", source.body)),
        "prefix": (body, "text", "Changed " + source.body),
    }
    replay, browser = same_height_selected(monkeypatch, mutate(xml, *changes[change]))
    coverage = []
    with pytest.raises(XError):
        check_caption(
            browser,
            browser.observe(),
            features={},
            covered=lambda *args: coverage.append(args),
        )
    assert replay.events == [("expand", replay.target)]
    assert not coverage and not browser.browsing_valid


class WrappedReplay(RawStartup):
    def __init__(self):
        super().__init__()
        self.home = document("wrapped-source")
        self.expanded = document("wrapped-expanded")
        self.after_capture = lambda: None
        self.expansion_error = None

    def screenshot(self):
        self.after_capture()
        return Image.new("RGB", SIZE, "white")

    def long_click(self, x, y, duration):
        if self.stage == "home" and 180 <= x < 271 and 979 <= y < 997:
            self.actions.append("expand")
            self.home = self.expanded
            if self.expansion_error:
                raise self.expansion_error
        else:
            super().long_click(x, y, duration)


@pytest.fixture
def wrapped(monkeypatch):
    raw = WrappedReplay()
    phone = Phone(
        TaktikDevice(raw, "fixture"), seed=0, clock=lambda: raw.now, sleep=raw.sleep
    )
    browser = XBrowser(phone, {"for_you"})
    calls = []
    monkeypatch.setattr(OcrService, "_resolve_tesseract_cmd", lambda: "tesseract")

    def tsv(command, image, **kwargs):
        calls.append(image.size)
        assert image.size == (871, 486) and kwargs["timeout_seconds"] == 5.0
        return (FIXTURES / "wrapped-words.tsv").read_text()

    monkeypatch.setattr(OcrService, "_image_to_tsv", tsv)
    try:
        browser.start("fixture_owner", "for_you")
        raw.actions.clear()
        yield raw, browser, calls
    finally:
        phone.close(home=False).require()


def test_wrapped_control_completes_caption_through_raw_device(wrapped):
    raw, browser, calls = wrapped
    source = browser.observe()
    coverage = []
    result = check_caption(
        browser, source, features={}, covered=lambda *args: coverage.append(args)
    )
    assert result.identity == source.identity and result.source_key != source.source_key
    assert result.caption == expansion.MORE.sub("", source.caption) + (
        " The last case contains a handmade compass."
    )
    assert result.caption_expanded and result.caption_type == "full"
    assert raw.actions == ["expand"] and calls == [(871, 486)]
    assert [name for name, _ in coverage] == ["inline_caption_attempt", "read_more"]


WRAPPED_WORDS = [
    TextMatch("Show", 96, 841, 915, 103, 31),
    TextMatch("more", 96, 180, 979, 91, 22),
]


@pytest.mark.parametrize(
    "words",
    [
        [],
        WRAPPED_WORDS[:1],
        WRAPPED_WORDS[1:],
        [replace(WRAPPED_WORDS[0], confidence=69), WRAPPED_WORDS[1]],
        [WRAPPED_WORDS[0], replace(WRAPPED_WORDS[1], confidence=float("nan"))],
        [replace(WRAPPED_WORDS[0], text="Sho"), WRAPPED_WORDS[1]],
        [WRAPPED_WORDS[0], replace(WRAPPED_WORDS[1], text="more…")],
        [*WRAPPED_WORDS, WRAPPED_WORDS[0]],
        [*WRAPPED_WORDS, replace(WRAPPED_WORDS[0], left=830)],
        [*WRAPPED_WORDS, WRAPPED_WORDS[1]],
        [
            *WRAPPED_WORDS,
            TextMatch("Show", 96, 720, 970, 103, 31),
            TextMatch("more", 96, 836, 979, 91, 22),
        ],
        [replace(WRAPPED_WORDS[0], left=700), WRAPPED_WORDS[1]],
        [WRAPPED_WORDS[0], replace(WRAPPED_WORDS[1], left=210)],
        [replace(WRAPPED_WORDS[0], top=850), WRAPPED_WORDS[1]],
        [replace(WRAPPED_WORDS[0], top=951), WRAPPED_WORDS[1]],
        [replace(WRAPPED_WORDS[0], top=970), WRAPPED_WORDS[1]],
        [replace(WRAPPED_WORDS[0], left=1048), WRAPPED_WORDS[1]],
        [WRAPPED_WORDS[0], replace(WRAPPED_WORDS[1], left=175)],
        [WRAPPED_WORDS[0], replace(WRAPPED_WORDS[1], top=984)],
        [WRAPPED_WORDS[0], replace(WRAPPED_WORDS[1], top=997)],
        [replace(WRAPPED_WORDS[0], height=0), WRAPPED_WORDS[1]],
    ],
)
def test_wrapped_words_need_unique_owned_adjacent_lines(wrapped, monkeypatch, words):
    raw, browser, _ = wrapped
    monkeypatch.setattr(OcrService, "locate", lambda *args, **kwargs: words)
    coverage = []
    with pytest.raises(XError, match="one visible native"):
        check_caption(
            browser,
            browser.observe(),
            features={},
            covered=lambda *args: coverage.append(args),
        )
    assert not raw.actions and not coverage and not browser.browsing_valid


@pytest.mark.parametrize("change", ["author", "body", "overlap", "cancel", "deadline"])
def test_wrapped_control_rechecks_source_and_session_before_tap(wrapped, change):
    raw, browser, _ = wrapped
    source = browser.observe()

    def changed():
        if change == "cancel":
            raise InteractionCancelled("cancelled")
        if change == "deadline":
            browser.phone.configure(deadline=raw.now)
            return
        changes = {
            "author": ('.//*[@text="@fixture_author"]', "text", "@another_author"),
            "body": (
                './/*[@bounds="[176,522][1047,997]"]',
                "bounds",
                "[176,523][1047,997]",
            ),
            "overlap": (
                './/*[@content-desc="Post options"]',
                "bounds",
                "[180,979][271,997]",
            ),
        }
        raw.home = mutate(raw.home, *changes[change])

    raw.after_capture = changed
    with pytest.raises(
        InteractionCancelled if change in {"cancel", "deadline"} else XError
    ):
        browser.read_more(source)
    assert not raw.actions and not browser.browsing_valid


@pytest.mark.parametrize("outcome", ["unchanged", "wrong_author", "uncertain"])
def test_wrapped_tap_alone_does_not_credit_expansion(wrapped, outcome):
    raw, browser, _ = wrapped
    if outcome == "unchanged":
        raw.expanded = raw.home
    elif outcome == "wrong_author":
        raw.expanded = mutate(
            raw.expanded, './/*[@text="@fixture_author"]', "text", "@another_author"
        )
    else:
        raw.expansion_error = OSError("tap response lost")
    coverage = []
    with pytest.raises(InteractionError if outcome == "uncertain" else XError):
        check_caption(
            browser,
            browser.observe(),
            features={},
            covered=lambda *args: coverage.append(args),
        )
    assert raw.actions == ["expand"]
    assert not coverage and not browser.browsing_valid


def test_wrapped_control_does_not_enable_quoted_expansion(wrapped):
    raw, browser, calls = wrapped
    raw.home = xml_fixture("nested-quote-tail-after.xml")
    raw.home = mutate(
        raw.home,
        './/*[@bounds="[176,916][1047,1405]" and @text!=""]',
        "text",
        "A synthetic outer caption with enough text to expand.\xa0Show more",
    )
    screen = read_screen(raw.home, SIZE)
    index = next(
        i for i, p in enumerate(screen.posts) if p.quoted_post and p.observable
    )
    browser.browser._select(screen, index)
    with pytest.raises(XError, match="quoted"):
        browser.read_more(browser.observe())
    assert not raw.actions and not calls and not browser.browsing_valid


@pytest.mark.parametrize("scale", [0.5, 1, 2])
def test_wrapped_geometry_scales_with_words_and_body(monkeypatch, scale):
    words = [
        replace(
            word,
            **{
                name: int(getattr(word, name) * scale)
                for name in ("left", "top", "width", "height")
            },
        )
        for word in WRAPPED_WORDS
    ]
    area = tuple(int(value * scale) for value in (176, 522, 1047, 997))
    size = tuple(int(value * scale) for value in SIZE)
    target, _ = locate(monkeypatch, words, area, size)
    assert target == _intersect(words[1].bbox, area)


def test_wrapped_synthetic_fixture_integrity():
    manifest = fixture_manifest(FIXTURES / "wrapped-manifest.json")
    assert manifest["kind"] == "synthetic_native_layout"
