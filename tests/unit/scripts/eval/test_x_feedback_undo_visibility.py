"""Undo recovery uses the current control, including after a small scroll."""

import pytest
from lxml import etree
from unit.scripts.eval.test_x_feedback_validation import (
    FeedbackReplay,
    document,
    selected,
)

from scripts.eval.x_feedback_validation import check_feedback_roundtrip
from taktik.core.shared.phone_interaction import (
    InteractionCancelled,
    InteractionError,
    Status,
)
from taktik.core.social_media.x.ui.screen import _rect, read_screen


def translated(xml, bounds, offset):
    root = etree.fromstring(xml.encode())
    container = root.xpath(".//*[@bounds=$bounds]", bounds=bounds)[0]
    for node in container.iter():
        if node.get("bounds"):
            left, top, right, bottom = _rect(node)
            node.set("bounds", f"[{left},{top + offset}][{right},{bottom + offset}]")
    return etree.tostring(root, encoding="unicode")


def source_document(offset):
    root = etree.fromstring(document("source").encode())
    quote = root.xpath('.//*[@bounds="[176,1359][1047,2235]"]')[0]
    quote.getparent().remove(quote)
    body = root.xpath('.//*[@bounds="[176,1013][1047,1337]"]')[0]
    body.set("bounds", "[176,1013][809,1067]")
    body.set("text", "A short synthetic post.")
    return translated(
        etree.tostring(root, encoding="unicode"), "[0,924][1080,2340]", offset
    )


def receipt_document(offset):
    return translated(document("receipt"), "[0,924][1080,1456]", offset)


class ObscuredFeedbackReplay(FeedbackReplay):
    def __init__(self, offset=780):
        super().__init__()
        self.offset = offset
        self.documents["source"] = source_document(offset)
        self.documents["receipt"] = receipt_document(offset)
        self.xml = self.documents["source"]
        self.scroll_offset = -220

    def long_click(self, x, y, duration):
        self.actions.append(("tap", self.stage))
        if self.stage == "source":
            assert 1019 <= x < 1080 and 957 + self.offset <= y < 1006 + self.offset
            self.stage = "options"
        elif self.stage == "options":
            assert 0 <= x < 1080 and 888 <= y < 1042
            self.stage = "receipt"
        elif self.stage == "receipt":
            assert 853 <= x < 1047 and 988 + self.offset <= y < 1120 + self.offset
            self.stage = "source"
        else:
            raise AssertionError("Unexpected feedback tap.")
        self.xml = self.documents[self.stage]

    def swipe_points(self, path, duration):
        assert self.stage == "receipt"
        assert path[0][1] > path[-1][1]
        assert path[0][1] - path[-1][1] <= 240
        self.actions.append(("scroll", self.stage))
        self.offset += self.scroll_offset
        self.documents["receipt"] = receipt_document(self.offset)
        self.documents["source"] = source_document(self.offset)
        self.xml = self.documents["receipt"]


@pytest.mark.parametrize("offset,scrolls", [(780, 0), (1080, 1)])
def test_feedback_undo_uses_clear_control_without_requiring_clear_card(offset, scrolls):
    replay, browser = selected(ObscuredFeedbackReplay(offset))
    source = browser.observe()
    result = check_feedback_roundtrip(browser, source)
    assert result["restored"]
    assert browser.observe(previous=source).identity == source.identity
    assert replay.actions == [
        ("tap", "source"),
        ("tap", "options"),
        *[("scroll", "receipt")] * scrolls,
        ("tap", "receipt"),
    ]
    replay.phone.close(home=False).require()


def test_obscured_undo_without_scroll_progress_stops_without_repeating_feedback():
    replay, browser = selected(ObscuredFeedbackReplay(1080))
    replay.scroll_offset = 0
    source = browser.observe()
    with pytest.raises(InteractionError) as raised:
        check_feedback_roundtrip(browser, source)
    assert raised.value.result.status == Status.UNCERTAIN
    assert replay.actions.count(("tap", "options")) == 1
    assert ("tap", "receipt") not in replay.actions
    assert 0 < replay.actions.count(("scroll", "receipt")) <= 4
    assert not browser.browsing_valid
    replay.phone.close(home=False).require()


@pytest.mark.parametrize("problem", ["missing", "author", "ambiguous", "disabled"])
def test_scroll_reacquires_undo_from_the_current_feedback_card(problem, monkeypatch):
    replay, browser = selected(ObscuredFeedbackReplay(1080))
    source = browser.observe()
    scroll = replay.swipe_points

    def change(path, duration):
        scroll(path, duration)
        root = etree.fromstring(replay.xml.encode())
        undo = root.xpath('.//*[@text="Undo"]')[0]
        if problem == "missing":
            undo.set("text", "Unavailable")
        elif problem == "disabled":
            undo.getparent().set("enabled", "false")
        elif problem == "author":
            root.xpath('.//*[@text="Show fewer posts from fixture_author"]')[0].set(
                "text", "Show fewer posts from someone_else"
            )
        else:
            receipt = undo.getparent().getparent()
            receipt.getparent().append(etree.fromstring(etree.tostring(receipt)))
        replay.xml = etree.tostring(root, encoding="unicode")

    monkeypatch.setattr(replay, "swipe_points", change)
    with pytest.raises(InteractionError) as raised:
        check_feedback_roundtrip(browser, source)
    assert raised.value.result.status == Status.UNCERTAIN
    assert replay.actions == [
        ("tap", "source"),
        ("tap", "options"),
        ("scroll", "receipt"),
    ]
    replay.phone.close(home=False).require()


def test_obscured_card_and_obscured_undo_have_distinct_confirmation_visibility():
    clear = read_screen(receipt_document(780), (1080, 2340)).removal_notices[0]
    covered = read_screen(receipt_document(1080), (1080, 2340)).removal_notices[0]
    assert not clear.visibility.unobscured
    assert clear.confirmation_visible
    assert not covered.confirmation_visible


@pytest.mark.parametrize("attribute", ["visible-to-user", "enabled"])
@pytest.mark.parametrize(
    "label", ["Show fewer posts from fixture_author", "This post isn’t relevant"]
)
def test_unavailable_refinement_does_not_prevent_clear_undo(label, attribute):
    replay, browser = selected(ObscuredFeedbackReplay())
    root = etree.fromstring(replay.documents["receipt"].encode())
    root.xpath(".//*[@text=$label]", label=label)[0].getparent().set(attribute, "false")
    replay.documents["receipt"] = etree.tostring(root, encoding="unicode")
    source = browser.observe()
    assert check_feedback_roundtrip(browser, source)["restored"]
    assert replay.actions == [("tap", "source"), ("tap", "options"), ("tap", "receipt")]
    replay.phone.close(home=False).require()


@pytest.mark.parametrize("retained_children", [2, 3])
def test_undo_can_be_revealed_when_offscreen_refinements_are_absent(retained_children):
    replay, browser = selected(ObscuredFeedbackReplay(1080))
    root = etree.fromstring(replay.documents["receipt"].encode())
    row = root.xpath(
        './/*[@text="Thanks. X will use this to make your timeline better."]'
    )[0].getparent()
    for child in list(row)[retained_children:]:
        row.remove(child)
    replay.documents["receipt"] = etree.tostring(root, encoding="unicode")
    source = browser.observe()
    assert check_feedback_roundtrip(browser, source)["restored"]
    assert replay.actions == [
        ("tap", "source"),
        ("tap", "options"),
        ("scroll", "receipt"),
        ("tap", "receipt"),
    ]
    replay.phone.close(home=False).require()


@pytest.mark.parametrize("problem", ["transport", "cancel", "deadline"])
def test_interrupted_undo_scroll_never_repeats_feedback(problem, monkeypatch):
    replay, browser = selected(ObscuredFeedbackReplay(1080))
    source = browser.observe()
    scroll = replay.swipe_points

    def interrupt(path, duration):
        scroll(path, duration)
        if problem == "transport":
            raise OSError("scroll outcome lost")
        if problem == "cancel":
            raise InteractionCancelled("cancelled")
        replay.phone.configure(deadline=replay.now)

    monkeypatch.setattr(replay, "swipe_points", interrupt)
    with pytest.raises(
        InteractionError if problem == "transport" else InteractionCancelled
    ):
        check_feedback_roundtrip(browser, source)
    assert replay.actions == [
        ("tap", "source"),
        ("tap", "options"),
        ("scroll", "receipt"),
    ]
    assert not browser.browsing_valid
    replay.phone.close(home=False).require()
