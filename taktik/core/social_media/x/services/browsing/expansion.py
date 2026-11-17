"""Verify inline native text expansion without changing the selected occurrence."""

import re
from dataclasses import replace

from taktik.core.shared.vision.ocr import OcrService
from taktik.core.social_media.x.ui.screen import _intersect

from .navigation import XError

MORE = re.compile(r"\sShow more\s*$")


def _target(source, screenshot):
    area = source.body_visibility.bounds
    words = OcrService.locate(
        screenshot,
        ["Show", "more"],
        region=area,
        min_confidence=70,
        timeout_seconds=5.0,
    )
    pairs = [
        (show, more)
        for show in words
        for more in words
        if show.text.lower() == "show"
        and more.text.lower() == "more"
        and min(show.confidence, more.confidence) >= 70
        and show.height > 0
        and more.height > 0
        and show.width > 0
        and more.width > 0
        and _intersect(show.bbox, area) == show.bbox
        and _intersect(more.bbox, area) == more.bbox
        and 0 <= more.left - show.bbox[2] < show.height
        and abs(show.top - more.top) < max(show.height, more.height) * 0.4
        and area[3] - more.bbox[3] < more.height * 2
    ]
    if len(pairs) != 1:
        raise XError("Cannot locate one visible native Show more control.")
    return pairs[0][1].bbox


def _exclusions(source, target):
    openings = [t.visibility for t in source.targets if t.label == "Open post"]
    if len(openings) != 1:
        raise XError("Cannot verify the native Show more control exclusions.")
    exclusions = list(openings[0].overlaps)
    # Remove only the body text; a control can occupy the exact same rectangle.
    exclusions.remove(source.body_visibility.bounds)
    if any(_intersect(target, r) for r in exclusions):
        raise XError("The native Show more control is covered by other content.")
    return tuple(exclusions)


def _verify(source, post):
    if not post.observable or not post.body_complete:
        raise XError("The expanded X body is not fully visible within the viewport.")
    stable = replace(
        source,
        body=post.body,
        body_complete=post.body_complete,
        content_key=post.content_key,
        visibility=post.visibility,
        body_visibility=post.body_visibility,
        media=post.media,
        actions=post.actions,
        targets=post.targets,
    )
    if (
        stable != post
        or source.body_visibility.bounds[:3] != post.body_visibility.bounds[:3]
        or post.body_visibility.bounds[3] <= source.body_visibility.bounds[3]
        or tuple(replace(m, visibility=None) for m in source.media)
        != tuple(replace(m, visibility=None) for m in post.media)
        or tuple((a.label, a.selected) for a in source.actions)
        != tuple((a.label, a.selected) for a in post.actions)
    ):
        raise XError("The expanded X post changed identity, content, or geometry.")


def read_more(app):
    with app._operation():
        source = app.observe()
        if source is not None and source.body_complete:
            return source
        if source is None or not source.body or not MORE.search(source.body):
            raise XError("The selected X post has no supported Show more control.")
        if source.quoted_post is not None:
            raise XError("Inline expansion of quoted X posts is not supported.")
        prefix = MORE.sub("", source.body)
        if (
            len(prefix) < 32
            or sum(p.content_key == source.content_key for p in app._screen.posts) != 1
        ):
            raise XError("The selected X expansion source is ambiguous.")
        screenshot = app.phone.read("screenshot")
        if screenshot.size != tuple(app.phone.read("size")):
            raise XError("X screen dimensions changed during expansion.")
        target = _target(source, screenshot)
        fresh = app.observe()
        if (
            fresh.content_key != source.content_key
            or fresh.body_visibility != source.body_visibility
        ):
            raise XError("The selected X body changed while locating Show more.")
        before = app._screen
        exclusions = _exclusions(fresh, target)
        app.phone.tap(target, exclude=exclusions).require()
        app.phone.wait(0.3, purpose="readiness")
        screen = app._wait_for(
            lambda s: (
                s.kind == before.kind
                and any(
                    p.body
                    and len(p.body) > len(prefix)
                    and p.body.startswith(prefix)
                    and not MORE.search(p.body)
                    for p in s.posts
                )
            ),
            "inline X text expansion",
        )
        app._check_timeline(screen, before)
        candidates = [
            (i, p)
            for i, p in enumerate(screen.posts)
            if p.author == source.author
            and p.body
            and len(p.body) > len(prefix)
            and p.body.startswith(prefix)
            and not MORE.search(p.body)
        ]
        if len(candidates) != 1 or screen.content_viewport != before.content_viewport:
            raise XError("The expanded X source or browsing context is ambiguous.")
        index, expanded = candidates[0]
        _verify(fresh, expanded)
        app._select(screen, index)
        return app.observe()
