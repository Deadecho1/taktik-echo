"""Copy-link dispatch through the public browser and real Phone transport."""

import hashlib
import json
from copy import deepcopy

import pytest
from lxml import etree
from unit.social_media.x.services.browsing.test_links import (
    GlyphLinkReplay,
    document,
    glyph_browser,
)
from unit.social_media.x.ui.test_inspection_screen import LINK_FIXTURES

from scripts.eval.x_link_validation import select_copy_link_check
from taktik.core.shared.phone_interaction import (
    InteractionCancelled,
    InteractionError,
    SessionExpired,
    Status,
)
from taktik.core.shared.ui.geometry import bounds
from taktik.core.social_media.x.services.browsing.navigation import XError


def xml(root):
    return etree.tostring(root, encoding="unicode")


def shift(node, offset):
    for child in node.iter():
        left, top, right, bottom = bounds(child)
        child.set("bounds", f"[{left},{top + offset}][{right},{bottom + offset}]")


def opportunity(layout="covered"):
    root = etree.fromstring(document("share-opportunity-source").encode())
    icon = root.xpath('.//*[@content-desc="Share"]')[0]
    if layout == "partial":
        icon.set("bounds", "[1003,2055][1047,2099]")
    elif layout == "clipped":
        icon.set("bounds", "[1036,2103][1047,2147]")
        icon.getparent().set("bounds", "[959,2059][1080,2177]")
        icon.getparent().getparent().set("bounds", "[0,1458][1080,2177]")
    return xml(root)


def receipt(source):
    root = etree.fromstring(source.encode())
    template = etree.fromstring(document("share-glyph-receipt").encode())
    overlay = template.xpath(
        './/*[@resource-id="com.android.systemui:id/clipboard_ui"]'
    )
    assert len(overlay) == 1
    window = overlay[0]
    while window.getparent() is not template:
        window = window.getparent()
    root.append(deepcopy(window))
    return xml(root)


class OpportunityReplay(GlyphLinkReplay):
    def __init__(self, layout="covered"):
        super().__init__()
        self.frames["source"] = opportunity(layout)
        self.frames["receipt"] = receipt(self.frames["source"])
        self.receipt_reads = 0
        self.scrolls = []
        self.share_region = {
            "partial": (1003, 2055, 1047, 2076),
            "clipped": (1036, 2103, 1080, 2147),
        }.get(layout)

    def dump_hierarchy(self):
        if self.state == "receipt":
            self.receipt_reads += 1
            if self.receipt_reads > 1:
                return self.frames["source"]
        return super().dump_hierarchy()

    def long_click(self, x, y, duration):
        if self.state != "source":
            return super().long_click(x, y, duration)
        left, top, right, bottom = self.share_region
        assert left <= x < right and top <= y < bottom
        self.actions.append((self.state, x, y))
        self.controls.append("Share")
        self.state = "share"
        if self.share_error:
            raise self.share_error

    def swipe_points(self, *args, **kwargs):
        assert not self.scrolls
        self.scrolls.append((args, kwargs))
        self.frames["source"] = self.frames["next"]
        self.frames["receipt"] = receipt(self.frames["source"])


def test_opportunity_fixture_has_only_synthetic_integrity_metadata():
    manifest = json.loads(
        (LINK_FIXTURES / "share-opportunity-manifest.json").read_text()
    )
    assert manifest["kind"] == "synthetic_native_layout"
    for item in manifest["fixtures"]:
        assert set(item) == {"file", "kind", "sha256"}
        assert item["kind"] == "synthetic_native_layout"
        assert (
            hashlib.sha256((LINK_FIXTURES / item["file"]).read_bytes()).hexdigest()
            == item["sha256"]
        )


def dispatch(browser, observation, features, skipped):
    task = select_copy_link_check(
        browser, observation, features=features, skipped=skipped.append
    )
    if task is not None:
        name, operation = task
        result = operation()
        features[name] = result
        return result


def test_observable_source_with_unusable_share_defers_without_action_or_credit():
    raw = GlyphLinkReplay()
    raw.frames["source"] = document("share-opportunity-source")
    raw, browser = glyph_browser(raw)
    observation = browser.observe()
    source = browser.browser.observe()
    share = next(a for a in source.actions if a.label == "Share")
    assert source.observable
    assert share.visibility.visible_bounds == (959, 2022, 1080, 2140)
    assert share.glyph_visibility.bounds == (1003, 2066, 1047, 2110)
    features, skipped = {}, []
    assert dispatch(browser, observation, features, skipped) is None
    assert raw.actions == [] and features == {}
    assert skipped == [
        {
            "source_identity": observation.identity,
            "source_key": observation.source_key,
            "reason": "No uncovered X Share target.",
        }
    ]
    assert browser.browsing_valid
    assert browser.observe(previous=observation).identity == observation.identity


@pytest.mark.parametrize("layout", ["partial", "clipped"])
def test_supported_covered_share_copies_once_and_verifies_return(layout):
    raw, browser = glyph_browser(OpportunityReplay(layout))
    observation = browser.observe()
    features, skipped = {}, []
    result = dispatch(browser, observation, features, skipped)
    assert features == {"copy_link": result} and skipped == []
    assert result.url == "https://x.com/fixture_author/status/1000000000000000001"
    assert result.source_key == observation.source_key
    assert raw.controls == ["Share", "Copy link"]
    assert browser.browsing_valid
    assert browser.observe(previous=observation).identity == observation.identity
    actions = list(raw.actions)
    assert dispatch(browser, observation, features, skipped) is None
    assert raw.actions == actions


def test_deferred_source_advances_to_a_distinct_eligible_occurrence():
    raw = OpportunityReplay()
    root = etree.fromstring(raw.frames["source"].encode())
    row = root.xpath('.//*[@resource-id="timeline_post"]')[0].getparent()
    later = deepcopy(row)
    body = later.xpath(
        './/*[@text="Synthetic text for a covered Share opportunity. Show more"]'
    )[0]
    body.set("text", "Synthetic later source with a usable Share glyph.")
    shift(later, 850)
    row.getparent().append(later)
    raw.frames["source"] = xml(root)
    for post in (row, later):
        shift(post, -1000)
    raw.frames["next"] = xml(root)
    raw.share_region = (1003, 1916, 1047, 1960)
    raw, browser = glyph_browser(raw)
    original = browser.observe()
    features, skipped = {}, []
    assert dispatch(browser, original, features, skipped) is None
    assert not features and not raw.actions
    browser.advance()
    later = browser.observe()
    assert (
        later.source_key != original.source_key and later.identity != original.identity
    )
    assert len(raw.scrolls) == 1
    result = dispatch(browser, later, features, skipped)
    assert features == {"copy_link": result} and len(skipped) == 1
    assert result.source_key == later.source_key
    assert raw.controls == ["Share", "Copy link"]
    assert browser.observe(previous=later).identity == later.identity


@pytest.mark.parametrize(
    "problem",
    ["missing", "hidden", "disabled", "duplicate", "unowned", "tiny", "malformed"],
)
def test_unusable_native_geometry_defers_without_trying_the_action(problem):
    raw = OpportunityReplay("partial")
    raw, browser = glyph_browser(raw)
    observation = browser.observe()
    root = etree.fromstring(raw.frames["source"].encode())
    icon = root.xpath('.//*[@content-desc="Share"]')[0]
    if problem == "missing":
        icon.set("content-desc", "")
    elif problem == "hidden":
        icon.set("visible-to-user", "false")
    elif problem == "disabled":
        icon.set("enabled", "false")
    elif problem == "duplicate":
        icon.getparent().append(deepcopy(icon))
    elif problem == "unowned":
        icon.set("bounds", "[940,2055][984,2099]")
    elif problem == "tiny":
        icon.set("bounds", "[1003,2055][1014,2066]")
    else:
        icon.set("bounds", "[1047,2099][1003,2055]")
    raw.frames["source"] = xml(root)
    features, skipped = {}, []
    if problem in {"duplicate", "malformed"}:
        with pytest.raises(InteractionError):
            dispatch(browser, observation, features, skipped)
        assert not features and not skipped and not raw.actions
        assert not browser.browsing_valid
        return
    assert dispatch(browser, observation, features, skipped) is None
    assert features == {} and raw.actions == [] and len(skipped) == 1
    assert browser.browsing_valid


@pytest.mark.parametrize(
    "problem", ["stale", "platform", "source", "context", "account"]
)
@pytest.mark.parametrize("stage", ["selection", "execution"])
def test_changed_decisions_or_context_stop_without_deferral_or_credit(problem, stage):
    raw, browser = glyph_browser(OpportunityReplay("partial"))
    observation = browser.observe()
    features, skipped = {}, []
    task = select_copy_link_check(
        browser, observation, features=features, skipped=skipped.append
    )
    if problem == "stale":
        browser._occurrence += 1
    elif problem == "platform":
        observation.platform = "instagram"
    elif problem == "source":
        raw.frames["source"] = raw.frames["source"].replace(
            "Synthetic text", "Changed text"
        )
    elif problem == "context":
        raw.frames["source"] = raw.frames["share"]
    else:
        browser.browser.verified_account = None
    with pytest.raises(InteractionError):
        if stage == "selection":
            dispatch(browser, observation, features, skipped)
        else:
            task[1]()
    assert not features and not skipped and not raw.actions
    assert not browser.browsing_valid


@pytest.mark.parametrize("stage", ["selection", "execution", "share", "copy"])
@pytest.mark.parametrize("problem", ["cancel", "deadline", "transport"])
def test_interruption_and_uncertainty_propagate_without_retry_or_credit(stage, problem):
    raw, browser = glyph_browser(OpportunityReplay("partial"))
    observation = browser.observe()
    features, skipped = {}, []
    task = select_copy_link_check(
        browser, observation, features=features, skipped=skipped.append
    )
    error = {
        "cancel": InteractionCancelled("stop"),
        "deadline": SessionExpired("expired"),
        "transport": RuntimeError("injection uncertain"),
    }[problem]
    if stage in {"share", "copy"}:
        setattr(raw, f"{stage}_error", error)
    elif problem == "cancel":
        browser.phone.configure(cancelled=lambda: True)
    elif problem == "deadline":
        browser.phone.configure(deadline=raw.now - 1)
    else:

        def fail_read():
            raise error

        raw.dump_hierarchy = fail_read
    with pytest.raises((InteractionError, InteractionCancelled)) as caught:
        if stage == "selection":
            dispatch(browser, observation, features, skipped)
        else:
            task[1]()
    if problem == "transport":
        assert caught.value.result.status in {Status.UNCERTAIN, Status.FAILED}
    else:
        assert isinstance(caught.value, type(error))
    assert not features and not skipped and not browser.browsing_valid
    assert raw.controls.count("Share") == (stage in {"share", "copy"})
    assert raw.controls.count("Copy link") == (stage == "copy")
    if stage == "share":
        assert raw.controls == ["Share", "Close sheet"]


def test_geometry_change_after_selection_remains_an_action_failure():
    raw, browser = glyph_browser(OpportunityReplay("partial"))
    observation = browser.observe()
    skipped = []
    task = select_copy_link_check(
        browser, observation, features={}, skipped=skipped.append
    )
    raw.frames["source"] = opportunity()
    with pytest.raises(XError, match="No uncovered X Share target"):
        task[1]()
    assert not raw.actions and not skipped and not browser.browsing_valid


def test_duplicate_source_is_an_error_instead_of_a_control_deferral():
    raw = OpportunityReplay("partial")
    root = etree.fromstring(raw.frames["source"].encode())
    row = root.xpath('.//*[@resource-id="timeline_post"]')[0].getparent()
    duplicate = deepcopy(row)
    shift(duplicate, -900)
    row.getparent().insert(0, duplicate)
    raw.frames["source"] = xml(root)
    raw, browser = glyph_browser(raw)
    observation = browser.observe()
    features, skipped = {}, []
    with pytest.raises(XError, match="ambiguous"):
        dispatch(browser, observation, features, skipped)
    assert not features and not skipped and not raw.actions
    assert not browser.browsing_valid


@pytest.mark.parametrize("problem", ["author", "url", "source_return", "sheet"])
def test_failed_receipt_or_return_never_earns_feature_credit(problem):
    raw, browser = glyph_browser(OpportunityReplay("partial"))
    observation = browser.observe()
    if problem == "author":
        raw.frames["receipt"] = raw.frames["receipt"].replace(
            "https://x.com/fixture_author/status/",
            "https://x.com/fixture_other/status/",
        )
    elif problem == "url":
        raw.frames["receipt"] = raw.frames["receipt"].replace(
            "https://x.com/fixture_author/status/",
            "https://example.com/fixture_author/status/",
        )
    elif problem == "source_return":
        raw.frames["receipt"] = raw.frames["receipt"].replace(
            "Synthetic text", "Changed text"
        )
    else:
        raw.frames["share"] = raw.frames["source"]
    features, skipped = {}, []
    with pytest.raises(XError):
        dispatch(browser, observation, features, skipped)
    assert not features and not skipped and not browser.browsing_valid
    assert raw.controls.count("Share") == 1
    assert raw.controls.count("Copy link") == (problem != "sheet")
