"""Captured sources exercise workflow dispatch and public browser inspection."""

from copy import deepcopy
from dataclasses import replace

import pytest
from lxml import etree
from unit.social_media.x.services.browsing.test_inspection_visits import (
    InspectionReplay,
    started,
)
from unit.social_media.x.ui.test_inspection_screen import SIZE, document

from scripts.eval.x_media_validation import select_media_check
from taktik.core.shared.phone_interaction import (
    InteractionCancelled,
    InteractionError,
    Status,
)
from taktik.core.shared.ui.geometry import bounds
from taktik.core.social_media.x.services.browsing.browser import XBrowser
from taktik.core.social_media.x.services.browsing.navigation import XError
from taktik.core.social_media.x.ui.screen import read_screen


def ambiguous_source():
    replay = InspectionReplay(image=True)
    replay.xml = document("ambiguous-image-source")
    browser = XBrowser(replay.phone, {"for_you"})
    app = browser.browser
    app.timeline = "for_you"
    app.verified_account = app._expected = "@fixture_owner"
    screen = read_screen(replay.xml, SIZE)
    index = next(i for i, post in enumerate(screen.posts) if post.observable)
    app._select(screen, index)
    browser.workflow, browser._username, browser._valid = (
        "for_you",
        "fixture_owner",
        True,
    )
    return replay, browser


def dispatch(browser, features, skipped):
    task = select_media_check(
        browser,
        browser.observe(),
        features=features,
        skipped=skipped.append,
    )
    if task is not None:
        name, operation = task
        result = operation()
        features[name] = result
        return result


def test_captured_duplicate_images_are_skipped_without_invalidating_browsing():
    replay, browser = ambiguous_source()
    source = browser.observe()
    assert [m.description for m in browser.browser.observe().media] == ["Image"] * 2
    features, skipped = {}, []
    assert dispatch(browser, features, skipped) is None
    assert features == {} and replay.events == [] and replay.capture_count == 0
    assert [item["index"] for item in skipped] == [0, 1]
    assert {item["reason"] for item in skipped} == {"ambiguous_description"}
    assert browser.browsing_valid
    assert browser.observe(previous=source).identity == source.identity


def continuation():
    root = etree.fromstring(document("ambiguous-image-source").encode())
    posts = root.xpath('.//*[@resource-id="timeline_post"]')
    posts[0].getparent().getparent().remove(posts[0].getparent())
    prior = posts[1].getparent()
    image = etree.fromstring(document("image-source").encode())
    successor = deepcopy(
        image.xpath('.//*[@resource-id="timeline_post"]')[0].getparent()
    )
    for container, offset in ((prior, -1000), (successor, 946)):
        for node in container.iter():
            left, top, right, bottom = bounds(node)
            node.set("bounds", f"[{left},{top + offset}][{right},{bottom + offset}]")
    prior.getparent().append(successor)
    return etree.tostring(root, encoding="unicode")


def test_skipped_source_can_advance_then_inspect_a_later_eligible_image():
    replay, browser = ambiguous_source()
    original = browser.observe()
    features, skipped = {}, []
    assert dispatch(browser, features, skipped) is None
    replay.scrolls = [continuation()]
    browser.advance()
    later = browser.observe()
    assert later.identity != original.identity and later.username == "NASA"
    assert "image" not in features
    replay.restored = replay.xml
    result = dispatch(browser, features, skipped)
    assert features == {"image": result}
    assert result.view == "gallery" and len(result.frames) == 2
    assert browser.observe(previous=later).identity == later.identity
    assert result.source_key == later.source_key
    assert replay.events[-2:] == [("visit", "Open media 0"), ("tap", "inspection Back")]
    assert browser.browsing_valid


@pytest.mark.parametrize("kind", ["image", "video", "gif"])
def test_duplicate_source_occurrences_only_block_image_visits(kind):
    replay, browser = started(image=True, wrapper=True)
    root = etree.fromstring(replay.xml.encode())
    if kind != "image":
        root.xpath('.//*[starts-with(@content-desc,"Image:")]')[0].set(
            "content-desc", "Video" if kind == "video" else "GIF"
        )
    posts = root.xpath('.//*[@resource-id="timeline_post"]')
    duplicate = deepcopy(posts[0].getparent())
    for node in duplicate.iter():
        left, top, right, bottom = bounds(node)
        node.set("bounds", f"[{left},{top + 1278}][{right},{bottom + 1278}]")
    second = posts[1].getparent()
    second.getparent().replace(second, duplicate)
    replay.xml = etree.tostring(root, encoding="unicode")
    browser.browser._select(read_screen(replay.xml, SIZE), 0)
    observation = browser.observe()
    assert (
        sum(
            post.content_key == observation.source_key
            for post in browser.browser._screen.posts
        )
        == 2
    )
    features, skipped = {}, []
    events = list(replay.events)
    result = dispatch(browser, features, skipped)
    if kind == "image":
        assert result is None and not features
        assert [item["reason"] for item in skipped] == ["ambiguous_source"]
    else:
        assert result.view == "inline" and result.media.kind == kind
        assert features == {kind: result} and not skipped
    assert replay.events == events and browser.browsing_valid


@pytest.mark.parametrize(
    "failure",
    [
        "missing_description",
        "empty_description",
        "duplicate_hidden_description",
        "missing_target",
        "duplicate_target",
        "hidden_target",
        "inaccessible_target",
        "covered_target",
        "sliver_target",
        "hidden_media",
        "inaccessible_media",
        "covered_media",
    ],
)
def test_unsupported_media_stays_pending_without_dispatch(monkeypatch, failure):
    replay, browser = started(image=True, wrapper=True)
    observation = browser.observe()
    app = browser.browser
    source = app.observe()
    media = source.media[0]
    target = next(t for t in source.targets if t.label == "Open media 0")
    targets = source.targets
    if failure in {"missing_description", "empty_description"}:
        media = replace(
            media, description=None if failure.startswith("missing") else ""
        )
    elif failure.endswith("media"):
        visibility = media.visibility
        if failure == "hidden_media":
            visibility = replace(visibility, visible_bounds=None)
        elif failure == "inaccessible_media":
            visibility = replace(visibility, accessible=False)
        else:
            visibility = replace(visibility, overlaps=(visibility.bounds,))
        media = replace(media, visibility=visibility)
    elif failure == "missing_target":
        targets = tuple(t for t in targets if t != target)
    elif failure == "duplicate_target":
        targets = (*targets, target)
    elif failure.endswith("target"):
        visibility = target.visibility
        if failure == "hidden_target":
            visibility = replace(visibility, visible_bounds=None)
        elif failure == "inaccessible_target":
            visibility = replace(visibility, accessible=False)
        else:
            left, top, right, bottom = visibility.bounds
            covered = (
                left,
                top,
                right - (10 if failure == "sliver_target" else 0),
                bottom,
            )
            visibility = replace(visibility, overlaps=(covered,))
        targets = tuple(
            replace(t, visibility=visibility) if t == target else t for t in targets
        )
    items = (media,)
    if failure == "duplicate_hidden_description":
        items += (
            replace(media, visibility=replace(media.visibility, visible_bounds=None)),
        )
    changed = replace(source, media=items, targets=targets)
    monkeypatch.setattr(type(app), "observe", lambda self: changed)
    events = list(replay.events)
    skipped = []
    assert (
        select_media_check(browser, observation, features={}, skipped=skipped.append)
        is None
    )
    assert skipped and replay.events == events and replay.capture_count == 0
    assert browser.browsing_valid


@pytest.mark.parametrize("kind", ["image", "video", "gif"])
def test_original_later_media_index_survives_skipped_images(kind):
    replay, browser = started(image=True, wrapper=True)
    root = etree.fromstring(replay.xml.encode())
    node = root.xpath('.//*[starts-with(@content-desc,"Image:")]')[0]
    for index in range(2):
        duplicate = deepcopy(node)
        duplicate.set("content-desc", "Image")
        duplicate.set("bounds", f"[{176 + index * 200},898][{376 + index * 200},1604]")
        node.addprevious(duplicate)
    node.set("bounds", "[576,898][1047,1604]")
    if kind != "image":
        node.set("content-desc", "Video" if kind == "video" else "GIF")
    replay.xml = replay.restored = etree.tostring(root, encoding="unicode")
    screen = read_screen(replay.xml, SIZE)
    browser.browser._select(screen, 0)
    tap = replay.tap

    def tap_later_media(target, exclude, kind):
        if read_screen(replay.xml, SIZE).kind == "search_results":
            assert 576 <= target[0] < target[2] <= 1047
            assert 898 <= target[1] < target[3] <= 1604
            replay.events.append(("visit", "Open media 2"))
            replay.xml = replay.gallery
        else:
            tap(target, exclude, kind)

    replay.tap = tap_later_media
    features, skipped = {}, []
    result = dispatch(browser, features, skipped)
    assert result.index == 2 and result.media.kind == kind
    assert features == {kind: result}
    assert [item["index"] for item in skipped] == [0, 1]
    assert result.view == ("gallery" if kind == "image" else "inline")
    if kind == "image":
        assert replay.events[-2:] == [
            ("visit", "Open media 2"),
            ("tap", "inspection Back"),
        ]
    else:
        assert not any(event[0] == "visit" for event in replay.events)


@pytest.mark.parametrize(
    "failure", ["gallery", "source", "open", "return", "capture", "cancel", "deadline"]
)
def test_real_inspection_failures_propagate_without_coverage_or_retry(failure):
    replay, browser = started(image=True, wrapper=True)
    if failure == "gallery":
        replay.gallery = replay.gallery.replace("@NASA", "@Else")
    elif failure == "source":
        replay.restored = replay.restored.replace("@NASA", "@Else")
    elif failure == "open":
        replay.visit_error = OSError("tap response lost")
    elif failure == "return":
        replay.back_error = OSError("back response lost")
    elif failure == "capture":
        replay.capture_error = OSError("capture response lost")
    elif failure == "cancel":
        replay.capture_error = InteractionCancelled("cancelled")
    else:
        replay.after_capture = lambda: replay.phone.configure(deadline=replay.now)
    features, skipped = {}, []
    with pytest.raises((InteractionError, InteractionCancelled)) as raised:
        dispatch(browser, features, skipped)
    assert not features and not skipped and not browser.browsing_valid
    assert replay.events.count(("visit", "Open media 0")) == 1
    assert replay.events.count(("tap", "inspection Back")) <= 1
    if failure in {"open", "return", "capture"}:
        assert raised.value.result.status == Status.UNCERTAIN
    if failure in {"cancel", "deadline"}:
        assert isinstance(raised.value, InteractionCancelled)
    replay.phone.close().require()
    assert replay.closed


@pytest.mark.parametrize("failure", ["cancel", "deadline", "source"])
def test_changes_between_selection_and_dispatch_are_not_swallowed(failure):
    replay, browser = started(image=True, wrapper=True)
    skipped = []
    name, operation = select_media_check(
        browser, browser.observe(), features={}, skipped=skipped.append
    )
    assert name == "image"
    if failure == "cancel":
        replay.phone.configure(cancelled=lambda: True)
    elif failure == "deadline":
        replay.phone.configure(deadline=replay.now)
    else:
        replay.xml = replay.xml.replace("@NASA", "@Else")
    events = list(replay.events)
    with pytest.raises((InteractionError, InteractionCancelled)):
        operation()
    assert replay.events == events and not browser.browsing_valid


def test_stale_observation_cannot_select_a_check():
    replay, browser = started(image=True, wrapper=True)
    source = replace(browser.observe(), identity="stale")
    events = list(replay.events)
    with pytest.raises(XError):
        select_media_check(browser, source, features={}, skipped=lambda _: None)
    assert replay.events == events and not browser.browsing_valid


@pytest.mark.parametrize("state", ["empty", "covered", "unsupported"])
def test_no_pending_supported_kind_produces_no_check(monkeypatch, state):
    replay, browser = started(image=True, wrapper=True)
    app = browser.browser
    source = app.observe()
    if state == "empty":
        source = replace(source, media=())
    elif state == "unsupported":
        source = replace(source, media=(replace(source.media[0], kind="audio"),))
    monkeypatch.setattr(type(app), "observe", lambda self: source)
    features = {"image": "prior verified check"} if state == "covered" else {}
    before = dict(features)
    skipped = []
    assert dispatch(browser, features, skipped) is None
    assert features == before and skipped == []
    assert browser.browsing_valid and replay.capture_count == 0


@pytest.mark.parametrize("failure", ["cancel", "deadline"])
def test_interrupted_selection_does_not_turn_into_a_skip(failure):
    replay, browser = ambiguous_source()
    source = browser.observe()
    if failure == "cancel":
        replay.phone.configure(cancelled=lambda: True)
    else:
        replay.phone.configure(deadline=replay.now)
    skipped = []
    with pytest.raises(InteractionCancelled):
        select_media_check(browser, source, features={}, skipped=skipped.append)
    assert not skipped and replay.events == [] and not browser.browsing_valid
