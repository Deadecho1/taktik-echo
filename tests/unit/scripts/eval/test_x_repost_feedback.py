"""Synthetic repost continuations through XBrowser, Phone and TaktikDevice."""

from copy import deepcopy

import pytest
from lxml import etree
from unit.scripts.eval.test_x_feedback_undo_visibility import (
    ObscuredFeedbackReplay,
    source_document,
)
from unit.scripts.eval.test_x_feedback_validation import (
    FIXTURES,
    SIZE,
    CompleteFeedbackReplay,
    FeedbackReplay,
    selected,
)
from unit.x_fixtures import xml_fixture

from scripts.eval.x_feedback_validation import _find_undo, check_feedback_roundtrip
from taktik.core.shared.phone_interaction import (
    InteractionCancelled,
    InteractionError,
    Status,
)
from taktik.core.social_media.x.services.browsing.navigation import XError
from taktik.core.social_media.x.ui.screen import read_screen


def repost_source(xml, annotation=".. reposted"):
    root = etree.fromstring(xml.encode())
    handle = root.xpath('.//*[@text="@fixture_author"]')[0]
    header = handle.getparent()
    row = deepcopy(header)
    row.set("resource-id", "social_context")
    for child in list(row)[1:]:
        row.remove(child)
    row[0].set("text", annotation)
    top = read_screen(xml, SIZE).observable_posts[0].header_visibility.bounds[1]
    row.set("bounds", f"[176,{top - 30}][876,{top}]")
    row[0].set("bounds", f"[176,{top - 30}][700,{top}]")
    header.addprevious(row)
    return etree.tostring(root, encoding="unicode")


def repost_receipt(xml, children=4):
    root = etree.fromstring(xml.encode())
    preference = root.xpath('.//*[@text="Show fewer posts from fixture_author"]')[0]
    preference.set("text", "Show fewer reposts from fixture_sharer")
    row = preference.getparent().getparent()
    for child in list(row)[children:]:
        row.remove(child)
    return etree.tostring(root, encoding="unicode")


class RepostFeedbackReplay(CompleteFeedbackReplay):
    def __init__(self, children=4):
        super().__init__()
        for name in ("source", "restored"):
            self.documents[name] = repost_source(self.documents[name])
        self.documents["receipt"] = repost_receipt(self.documents["receipt"], children)
        self.xml = self.documents["source"]


@pytest.mark.parametrize("children", [2, 3, 4])
def test_repost_roundtrip_owns_one_undo_and_verifies_original_restoration(children):
    replay, browser = selected(RepostFeedbackReplay(children))
    source = browser.observe()
    assert browser.browser.observe().reposted_by == ".. reposted"
    result = check_feedback_roundtrip(browser, source)
    assert result == {
        "source_identity": source.identity,
        "source_key": source.source_key,
        "restored": True,
    }
    assert replay.stage == "restored"
    assert replay.actions == [("tap", "source"), ("tap", "options"), ("tap", "receipt")]
    assert browser.observe(previous=source).identity == source.identity
    assert browser.browsing_valid
    replay.phone.close(home=False).require()


def test_repost_preference_account_is_not_attributed_to_outer_author():
    replay = RepostFeedbackReplay()
    source = read_screen(replay.xml, SIZE).observable_posts[0]
    notices = read_screen(replay.documents["receipt"], SIZE).removal_notices
    assert len(notices) == 1
    notice = notices[0]
    assert notice.author is None
    assert notice.preference.kind == "reposts"
    assert notice.preference.account == "@fixture_sharer" != source.author
    assert source.reposted_by == ".. reposted"
    replay.phone.close(home=False).require()


@pytest.mark.parametrize("header_offset", [0, 66])
def test_public_repost_feedback_still_confirms_then_advances(
    header_offset, monkeypatch
):
    replay = FeedbackReplay()
    root = etree.fromstring(source_document(header_offset).encode())
    post = root.xpath('.//*[@text="@fixture_author"]')[0].getparent().getparent()
    post.set("bounds", f"[0,924][1080,{2340 + header_offset}]")
    replay.documents["source"] = repost_source(etree.tostring(root, encoding="unicode"))
    replay.documents["receipt"] = repost_receipt(replay.documents["receipt"])
    tap = replay.long_click
    monkeypatch.setattr(
        replay,
        "long_click",
        lambda x, y, duration: tap(
            x, y - header_offset if replay.stage == "source" else y, duration
        ),
    )
    replay.xml = replay.documents["source"]
    replay, browser = selected(replay)
    source = browser.observe()
    result = browser.act("not_interested", source)
    assert result.advanced and browser.observe().identity != source.identity
    assert replay.actions == [
        ("tap", "source"),
        ("tap", "options"),
        ("scroll", "receipt"),
        ("scroll", "framing"),
    ]
    replay.phone.close(home=False).require()


@pytest.mark.parametrize("problem", ["moved_slot", "extra_sibling", "missing_slot"])
def test_public_repost_confirmation_requires_original_native_slot(problem):
    replay = FeedbackReplay()
    replay.documents["source"] = repost_source(replay.documents["source"])
    root = etree.fromstring(repost_receipt(replay.documents["receipt"]).encode())
    row = root.xpath('.//*[@text="Undo"]')[0].getparent().getparent()
    slot = row.getparent().getparent()
    if problem == "moved_slot":
        slot.set("bounds", "[0,925][1080,1456]")
    elif problem == "extra_sibling":
        extra = deepcopy(row[-1])
        extra.remove(extra[0])
        slot.append(extra)
    else:
        slot.getparent().replace(slot, row)
    replay.documents["receipt"] = etree.tostring(root, encoding="unicode")
    replay.xml = replay.documents["source"]
    replay, browser = selected(replay)
    source = browser.observe()
    with pytest.raises(InteractionError) as raised:
        browser.act("not_interested", source)
    assert raised.value.result.status == Status.UNCERTAIN
    assert replay.actions == [("tap", "source"), ("tap", "options")]
    assert not browser.browsing_valid
    replay.phone.close(home=False).require()


@pytest.mark.parametrize(
    "problem",
    ["ordinary_source", "ordinary_preference", "malformed", "extra", "ambiguous"],
)
def test_unowned_repost_receipt_never_taps_undo(problem):
    replay = RepostFeedbackReplay()
    if problem == "ordinary_source":
        replay.documents["source"] = CompleteFeedbackReplay().documents["source"]
        replay.xml = replay.documents["source"]
    else:
        root = etree.fromstring(replay.documents["receipt"].encode())
        preference = root.xpath('.//*[@text="Show fewer reposts from fixture_sharer"]')[
            0
        ]
        row = preference.getparent().getparent()
        if problem == "ordinary_preference":
            preference.set("text", "Show fewer posts from fixture_sharer")
        elif problem == "malformed":
            preference.set("text", "Show fewer reposts from @fixture_sharer")
        elif problem == "extra":
            row.append(deepcopy(row[-1]))
        else:
            unrelated = deepcopy(row)
            unrelated.xpath('.//*[@text="Show fewer reposts from fixture_sharer"]')[
                0
            ].set("text", "Show fewer posts from unrelated")
            row.addnext(unrelated)
        replay.documents["receipt"] = etree.tostring(root, encoding="unicode")
    replay, browser = selected(replay)
    source = browser.observe()
    with pytest.raises(InteractionError) as raised:
        check_feedback_roundtrip(browser, source)
    assert raised.value.result.status == Status.UNCERTAIN
    assert replay.actions == [("tap", "source"), ("tap", "options")]
    assert not browser.browsing_valid
    replay.phone.close(home=False).require()


def add_receipt(source_xml, receipt_xml):
    source = etree.fromstring(source_xml.encode())
    receipt = etree.fromstring(receipt_xml.encode())
    row = receipt.xpath('.//*[@text="Undo"]')[0].getparent().getparent()
    source.xpath('.//*[@scrollable="true"]')[0].append(deepcopy(row))
    return etree.tostring(source, encoding="unicode")


@pytest.mark.parametrize("public", [False, True])
def test_existing_receipt_blocks_new_feedback_before_any_tap(public):
    replay = RepostFeedbackReplay()
    replay.xml = add_receipt(replay.xml, replay.documents["receipt"])
    replay, browser = selected(replay)
    source = browser.observe()
    with pytest.raises(XError, match="existing X feedback receipt") as raised:
        if public:
            browser.act("not_interested", source)
        else:
            check_feedback_roundtrip(browser, source)
    assert raised.value.result.status == Status.UNSUPPORTED
    assert replay.actions == []
    assert not browser.browsing_valid
    replay.phone.close(home=False).require()


@pytest.mark.parametrize(
    "account", ["", "x" * 16, "bad-name", "bad name", "＠name", "name "]
)
def test_malformed_repost_preference_never_owns_undo(account):
    replay = RepostFeedbackReplay()
    replay.documents["receipt"] = replay.documents["receipt"].replace(
        "Show fewer reposts from fixture_sharer", f"Show fewer reposts from {account}"
    )
    replay, browser = selected(replay)
    source = browser.observe()
    with pytest.raises(InteractionError) as raised:
        check_feedback_roundtrip(browser, source)
    assert raised.value.result.status == Status.UNCERTAIN
    assert replay.actions == [("tap", "source"), ("tap", "options")]
    replay.phone.close(home=False).require()


@pytest.mark.parametrize(
    "problem", ["hidden_undo", "disabled_undo", "extra_control", "reordered_undo"]
)
def test_undo_requires_accessible_owned_native_control(problem):
    replay = RepostFeedbackReplay()
    root = etree.fromstring(replay.documents["receipt"].encode())
    undo = root.xpath('.//*[@text="Undo"]')[0]
    wrapper, row = undo.getparent(), undo.getparent().getparent()
    if problem == "hidden_undo":
        undo.set("visible-to-user", "false")
    elif problem == "disabled_undo":
        wrapper.set("enabled", "false")
    elif problem == "extra_control":
        extra = deepcopy(wrapper)
        extra.remove(extra[0])
        row[-1].append(extra)
    else:
        row.remove(wrapper)
        row.append(wrapper)
    replay.documents["receipt"] = etree.tostring(root, encoding="unicode")
    replay, browser = selected(replay)
    source = browser.observe()
    with pytest.raises(InteractionError):
        check_feedback_roundtrip(browser, source)
    assert replay.actions == [("tap", "source"), ("tap", "options")]
    assert not browser.browsing_valid
    replay.phone.close(home=False).require()


class CoveredRepostReplay(ObscuredFeedbackReplay):
    def __init__(self, offset=1080):
        super().__init__(offset)
        self.convert()
        self.xml = self.documents["source"]

    def convert(self):
        self.documents["source"] = repost_source(self.documents["source"])
        self.documents["receipt"] = repost_receipt(self.documents["receipt"])

    def swipe_points(self, path, duration):
        super().swipe_points(path, duration)
        self.convert()
        self.xml = self.documents["receipt"]


@pytest.mark.parametrize(
    "offset,children,scrolls", [(780, 4, 0), (1080, 2, 1), (1080, 3, 1), (1080, 4, 1)]
)
def test_repost_undo_uses_clear_control_or_bounded_reveal(offset, children, scrolls):
    replay = CoveredRepostReplay(offset)
    root = etree.fromstring(replay.documents["receipt"].encode())
    row = root.xpath('.//*[@text="Undo"]')[0].getparent().getparent()
    for child in list(row)[children:]:
        row.remove(child)
    replay.documents["receipt"] = etree.tostring(root, encoding="unicode")
    replay, browser = selected(replay)
    source = browser.observe()
    assert check_feedback_roundtrip(browser, source)["restored"]
    assert browser.observe(previous=source).identity == source.identity
    assert replay.actions == [
        ("tap", "source"),
        ("tap", "options"),
        *[("scroll", "receipt")] * scrolls,
        ("tap", "receipt"),
    ]
    replay.phone.close(home=False).require()


@pytest.mark.parametrize("problem", ["account", "kind", "no_progress"])
def test_repost_undo_reveal_preserves_preference_and_bounds(problem, monkeypatch):
    replay, browser = selected(CoveredRepostReplay())
    source = browser.observe()
    scroll = replay.swipe_points
    if problem == "no_progress":
        replay.scroll_offset = 0

    def changed(path, duration):
        scroll(path, duration)
        if problem == "account":
            replay.xml = replay.xml.replace("fixture_sharer", "different")
        elif problem == "kind":
            replay.xml = replay.xml.replace(
                "Show fewer reposts from fixture_sharer",
                "Show fewer posts from fixture_author",
            )

    monkeypatch.setattr(replay, "swipe_points", changed)
    with pytest.raises(InteractionError) as raised:
        check_feedback_roundtrip(browser, source)
    assert raised.value.result.status == Status.UNCERTAIN
    assert replay.actions.count(("tap", "options")) == 1
    assert ("tap", "receipt") not in replay.actions
    assert replay.actions.count(("scroll", "receipt")) == (
        4 if problem == "no_progress" else 1
    )
    assert not browser.browsing_valid
    replay.phone.close(home=False).require()


@pytest.mark.parametrize(
    "problem",
    [
        "author",
        "content",
        "reposter",
        "duplicate",
        "receipt_persists",
        "following",
        "foreground",
    ],
)
def test_repost_undo_needs_independent_original_restoration(problem, monkeypatch):
    replay, browser = selected(RepostFeedbackReplay())
    source = browser.observe()
    xml = replay.documents["restored"]
    if problem == "author":
        xml = xml.replace("@fixture_author", "@different")
    elif problem == "content":
        xml = xml.replace("Synthetic post caption 4", "Changed synthetic caption")
    elif problem == "reposter":
        xml = xml.replace(".. reposted", "Different reposted")
    elif problem == "duplicate":
        root = etree.fromstring(xml.encode())
        post = root.xpath('.//*[@text="@fixture_author"]')[0].getparent().getparent()
        post.addnext(deepcopy(post))
        xml = etree.tostring(root, encoding="unicode")
    elif problem == "receipt_persists":
        xml = add_receipt(xml, replay.documents["receipt"])
    elif problem == "following":
        root = etree.fromstring(xml.encode())
        for label in ("For you", "Following"):
            target = root.xpath(".//*[@content-desc=$label]", label=label)[0]
            target.getparent().set(
                "selected", "true" if label == "Following" else "false"
            )
        xml = etree.tostring(root, encoding="unicode")
    else:
        app_current = replay.app_current
        monkeypatch.setattr(
            replay,
            "app_current",
            lambda: (
                {"package": "other.app"}
                if replay.stage == "restored"
                else app_current()
            ),
        )
    replay.documents["restored"] = xml
    with pytest.raises(InteractionError) as raised:
        check_feedback_roundtrip(browser, source)
    assert raised.value.result.status == Status.UNCERTAIN
    assert replay.actions == [("tap", "source"), ("tap", "options"), ("tap", "receipt")]
    assert not browser.browsing_valid
    replay.phone.close(home=False).require()


@pytest.mark.parametrize("stage", ["options", "receipt"])
@pytest.mark.parametrize("problem", ["transport", "cancel", "deadline"])
def test_repost_mutation_interruption_invalidates_without_retry(
    stage, problem, monkeypatch
):
    replay, browser = selected(RepostFeedbackReplay())
    source = browser.observe()
    tap = replay.long_click

    def interrupted(x, y, duration):
        current = replay.stage
        tap(x, y, duration)
        if current == stage:
            if problem == "transport":
                raise OSError("Repost mutation outcome lost")
            if problem == "cancel":
                raise InteractionCancelled("Cancelled repost mutation")
            replay.phone.configure(deadline=replay.now)

    monkeypatch.setattr(replay, "long_click", interrupted)
    with pytest.raises(
        InteractionError if problem == "transport" else InteractionCancelled
    ):
        check_feedback_roundtrip(browser, source)
    assert replay.actions.count(("tap", "options")) == 1
    assert replay.actions.count(("tap", "receipt")) == (stage == "receipt")
    assert not browser.browsing_valid
    with pytest.raises(XError):
        check_feedback_roundtrip(browser, source)
    replay.phone.configure(deadline=None)
    replay.phone.close(home=False).require()


@pytest.mark.parametrize("change", ["author", "reposter", "menu_author"])
def test_changed_repost_decision_cannot_apply_feedback(change):
    replay, browser = selected(RepostFeedbackReplay())
    source = browser.observe()
    if change == "author":
        replay.xml = replay.xml.replace("@fixture_author", "@different")
    elif change == "reposter":
        replay.xml = replay.xml.replace(".. reposted", "Different reposted")
    else:
        replay.documents["options"] = replay.documents["options"].replace(
            "@fixture_author", "@different"
        )
    with pytest.raises(XError):
        check_feedback_roundtrip(browser, source)
    assert replay.actions == ([("tap", "source")] if change == "menu_author" else [])
    assert not browser.browsing_valid
    replay.phone.close(home=False).require()


def test_changed_account_after_feedback_cannot_authorize_undo():
    replay, browser = selected(RepostFeedbackReplay())
    source = browser.observe()
    replay.documents["transition"] = xml_fixture(
        FIXTURES.parent / "startup/drawer.xml"
    ).replace("@fixture_owner", "@different")
    with pytest.raises(InteractionError) as raised:
        check_feedback_roundtrip(browser, source)
    assert raised.value.result.status == Status.UNCERTAIN
    assert "active X handle" in str(raised.value.__cause__)
    assert replay.actions == [("tap", "source"), ("tap", "options")]
    assert not browser.browsing_valid
    replay.phone.close(home=False).require()


def test_recovery_rechecks_previously_owned_preference_before_undo():
    replay, browser = selected(RepostFeedbackReplay())
    app = browser.browser
    source = app.observe()
    preference = (
        read_screen(replay.documents["receipt"], SIZE).removal_notices[0].preference
    )
    replay.stage = "receipt"
    replay.xml = replay.documents["receipt"].replace("fixture_sharer", "different")
    with pytest.raises(XError, match="preference changed"):
        _find_undo(app, source, preference=preference)
    assert replay.actions == []
    replay.phone.close(home=False).require()
