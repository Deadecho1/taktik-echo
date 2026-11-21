"""Synthetic native layouts exercise feedback through the real Phone backend."""

import hashlib
import json
from copy import deepcopy

import pytest
from lxml import etree
from unit.paths import CORE

from scripts.eval.x_feedback_validation import check_feedback_roundtrip
from taktik.core.shared.phone_interaction import (
    InteractionCancelled,
    InteractionError,
    Phone,
    Status,
)
from taktik.core.shared.phone_interaction._device import TaktikDevice
from taktik.core.social_media.x.services.browsing.browser import XBrowser
from taktik.core.social_media.x.services.browsing.navigation import XError
from taktik.core.social_media.x.ui.screen import PACKAGE, read_screen

FIXTURES = CORE / "tests/unit/social_media/x/fixtures/engagement"
SIZE = (1080, 2340)


def document(name):
    return (FIXTURES / f"undo-{name}.xml").read_text()


def test_synthetic_feedback_fixture_integrity():
    manifest = json.loads((FIXTURES / "undo-manifest.json").read_text())
    assert manifest["size"] == list(SIZE)
    assert {entry["file"] for entry in manifest["fixtures"]} == {
        path.name for path in FIXTURES.glob("undo-*.xml")
    }
    for entry in manifest["fixtures"]:
        assert set(entry) == {"file", "kind", "sha256"}
        assert entry["kind"] == "synthetic_native_layout"
        assert (
            hashlib.sha256((FIXTURES / entry["file"]).read_bytes()).hexdigest()
            == entry["sha256"]
        )


class FeedbackReplay:
    def __init__(self):
        self.documents = {
            name: document(name)
            for name in ("source", "options", "receipt", "framing", "successor")
        }
        self.xml = self.documents["source"]
        self.stage = "source"
        self.actions = []
        self.now = 0
        self.phone = Phone(
            TaktikDevice(self, "fixture"),
            seed=0,
            clock=lambda: self.now,
            sleep=self.sleep,
        )

    def app_current(self):
        return {"package": PACKAGE}

    def window_size(self):
        return SIZE

    def dump_hierarchy(self):
        return self.xml

    def sleep(self, seconds):
        self.now += seconds

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


def test_feedback_undo_precedes_successor_framing_and_retains_occurrence():
    replay, browser = selected()
    source = browser.observe()
    evidence = check_feedback_roundtrip(browser, source)
    assert evidence["restored"] is True
    assert evidence["source_key"] == source.source_key
    assert browser.observe(previous=source).identity == source.identity
    assert replay.actions == [("tap", "source"), ("tap", "options"), ("tap", "receipt")]
    assert browser.browsing_valid
    replay.phone.close(home=False).require()


def test_complete_feedback_roundtrip_replays_synthetic_restoration():
    replay, browser = selected(CompleteFeedbackReplay())
    source = browser.observe()
    evidence = check_feedback_roundtrip(browser, source)
    assert evidence == {
        "source_identity": source.identity,
        "source_key": source.source_key,
        "restored": True,
    }
    assert browser.observe(previous=source).identity == source.identity
    assert replay.actions == [("tap", "source"), ("tap", "options"), ("tap", "receipt")]
    assert replay.stage == "restored" and browser.browsing_valid
    replay.phone.close(home=False).require()


def test_public_feedback_still_frames_successor_and_invalidates_old_occurrence():
    replay, browser = selected()
    source = browser.observe()
    result = browser.act("not_interested", source)
    assert result.advanced
    assert browser.observe().identity != source.identity
    assert replay.actions == [
        ("tap", "source"),
        ("tap", "options"),
        ("scroll", "receipt"),
        ("scroll", "framing"),
    ]
    assert browser.browser.navigation_gaps[-1]["source_key"] == source.source_key
    with pytest.raises(XError, match="changed"):
        check_feedback_roundtrip(browser, source)
    assert len(replay.actions) == 4


@pytest.mark.parametrize(
    "problem", ["missing", "author", "ambiguous", "source_present"]
)
def test_invalid_removal_confirmation_never_attempts_undo(problem):
    replay, browser = selected()
    source = browser.observe()
    xml = replay.documents["receipt"]
    if problem == "missing":
        xml = xml.replace('text="Undo"', 'text="Unavailable"')
    elif problem == "author":
        xml = xml.replace(
            "Show fewer posts from fixture_author", "Show fewer posts from Other"
        )
    elif problem == "source_present":
        xml = replay.documents["source"]
    else:
        root = etree.fromstring(xml.encode())
        row = root.xpath(
            './/*[@text="Thanks. X will use this to make your timeline better."]'
        )[0].getparent()
        row.getparent().append(deepcopy(row))
        xml = etree.tostring(root, encoding="unicode")
    replay.documents["receipt"] = xml
    with pytest.raises(InteractionError) as raised:
        check_feedback_roundtrip(browser, source)
    assert raised.value.result.status == Status.UNCERTAIN
    assert isinstance(raised.value.__cause__, XError)
    assert replay.actions == [("tap", "source"), ("tap", "options")]
    assert not browser.browsing_valid


def test_clear_undo_is_used_from_first_receipt_snapshot(monkeypatch):
    replay, browser = selected()
    source = browser.observe()
    read = replay.dump_hierarchy
    reads = 0

    def count():
        nonlocal reads
        if replay.stage == "receipt":
            reads += 1
        return read()

    monkeypatch.setattr(replay, "dump_hierarchy", count)
    assert check_feedback_roundtrip(browser, source)["restored"]
    assert reads == 1
    assert replay.actions == [("tap", "source"), ("tap", "options"), ("tap", "receipt")]
    replay.phone.close(home=False).require()


@pytest.mark.parametrize(
    "problem", ["author", "content", "duplicate", "receipt_persists"]
)
def test_undo_requires_unique_original_source_and_persistent_restoration(problem):
    replay, browser = selected()
    source = browser.observe()
    xml = replay.documents["source"]
    if problem == "author":
        xml = xml.replace("@fixture_author", "@OtherAuthor")
    elif problem == "content":
        root = etree.fromstring(xml.encode())
        body = browser.browser.observe().body
        root.xpath(".//*[@text=$body]", body=body)[0].set("text", body + " Changed.")
        xml = etree.tostring(root, encoding="unicode")
    elif problem == "receipt_persists":
        xml = replay.documents["receipt"]
    else:
        root = etree.fromstring(xml.encode())
        author = root.xpath('.//*[@text="@fixture_author"]')[0]
        post = next(
            n for n in author.iterancestors() if n.get("bounds") == "[0,924][1080,2340]"
        )
        post.getparent().append(deepcopy(post))
        xml = etree.tostring(root, encoding="unicode")
    replay.documents["source"] = xml
    with pytest.raises(InteractionError) as raised:
        check_feedback_roundtrip(browser, source)
    assert raised.value.result.status == Status.UNCERTAIN
    assert isinstance(raised.value.__cause__, XError)
    assert replay.actions == [("tap", "source"), ("tap", "options"), ("tap", "receipt")]
    assert not browser.browsing_valid


@pytest.mark.parametrize("stage", ["options", "receipt"])
@pytest.mark.parametrize("problem", ["transport", "cancel", "deadline"])
def test_interrupted_or_uncertain_mutation_is_never_retried(
    stage, problem, monkeypatch
):
    replay, browser = selected()
    source = browser.observe()
    tap = replay.long_click

    def fail(x, y, duration):
        current = replay.stage
        tap(x, y, duration)
        if current == stage:
            if problem == "transport":
                raise OSError("mutation result lost")
            if problem == "cancel":
                raise InteractionCancelled("cancelled")
            replay.phone.configure(deadline=replay.now)

    monkeypatch.setattr(replay, "long_click", fail)
    with pytest.raises(
        InteractionError if problem == "transport" else InteractionCancelled
    ) as raised:
        check_feedback_roundtrip(browser, source)
    if problem == "transport":
        assert raised.value.result.status == Status.UNCERTAIN
    assert replay.actions.count(("tap", "options")) == 1
    assert replay.actions.count(("tap", "receipt")) == (stage == "receipt")
    assert not browser.browsing_valid
    with pytest.raises(XError):
        check_feedback_roundtrip(browser, source)
    assert replay.actions.count(("tap", "options")) == 1


def test_changed_source_is_rejected_before_opening_feedback():
    replay, browser = selected()
    source = browser.observe()
    replay.xml = replay.xml.replace("@fixture_author", "@OtherAuthor")
    with pytest.raises(XError):
        check_feedback_roundtrip(browser, source)
    assert replay.actions == []
    assert not browser.browsing_valid


def test_restoration_is_reread_before_success(monkeypatch):
    replay, browser = selected()
    source = browser.observe()
    read = replay.dump_hierarchy
    reads = 0

    def changed():
        nonlocal reads
        if ("tap", "receipt") in replay.actions:
            reads += 1
            if reads == 2:
                replay.xml = replay.xml.replace("@fixture_author", "@OtherAuthor")
        return read()

    monkeypatch.setattr(replay, "dump_hierarchy", changed)
    with pytest.raises(InteractionError) as raised:
        check_feedback_roundtrip(browser, source)
    assert raised.value.result.status == Status.UNCERTAIN
    assert reads == 2
    assert replay.actions == [("tap", "source"), ("tap", "options"), ("tap", "receipt")]
    assert not browser.browsing_valid
