"""Bounded read-only visits that retain the verified feed occurrence."""

import io
import math
from dataclasses import dataclass

from taktik.core.social_media.x.ui.inspection import Detail, Profile
from taktik.core.social_media.x.ui.screen import Media, Post, Rect

from .navigation import (
    XError,
    _free_regions,
    _quote_content,
    _scroll_motion,
    scroll_region,
)


@dataclass(frozen=True)
class ProfileVisit:
    source_key: str
    profile: Profile
    tab: str
    posts: tuple[Post, ...]


@dataclass(frozen=True)
class ThreadInspection:
    source_key: str
    detail: Detail
    posts: tuple[Post, ...]
    scrolls: int
    stop_reason: str
    # A navigation reference is not independent identification of the main post.
    main_verified: bool = False
    complete: bool = False
    main_text: str | None = None
    main_text_complete: bool = False


@dataclass(frozen=True)
class MediaInspection:
    source_key: str
    index: int
    media: Media
    frames: tuple[bytes, ...]
    view: str
    crop: Rect
    partial: bool


def _limit(value, name, minimum, maximum):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(f"{name} must be an integer between {minimum} and {maximum}.")


def visit_profile(app):
    with app._visit("Visit author", "profile") as (source, screen):
        current = app._snapshot()
        if any(
            s.active_account is not None
            and s.active_account.lower() != app.verified_account.lower()
            for s in (screen, current)
        ):
            raise XError("The active X account changed during the profile visit.")
        if (
            screen.profile is None
            or current.kind != "profile"
            or current.profile is None
            or current.profile.handle.lower() != source.author.lower()
            or screen.profile.handle.lower() != source.author.lower()
            or current.tab != screen.tab
        ):
            raise XError("The visited X profile does not verify the selected author.")
        result = ProfileVisit(
            source.content_key, current.profile, current.tab, current.observable_posts
        )
    return result


def _detail_context(before, after):
    if after.kind != "detail" or after.detail is None:
        raise XError("X left the inspected thread.")
    for field in ("timestamp", "sort_order"):
        old, new = getattr(before.detail, field), getattr(after.detail, field)
        if old is not None and new is not None:
            left, right = old.text, new.text
            if field == "timestamp":
                left, right = left.rsplit(" • ", 1)[0], right.rsplit(" • ", 1)[0]
            if left != right:
                raise XError("The X thread context changed during inspection.")
    old, new = before.detail.main_post, after.detail.main_post
    if (
        old is not None
        and new is not None
        and (
            old.author != new.author
            or old.body != new.body
            or _quote_content(old.quoted_post) != _quote_content(new.quoted_post)
        )
    ):
        raise XError("The native main post changed during thread inspection.")


def _verify_main_source(source, main):
    from .expansion import MORE

    if main is None:
        return False
    if (
        main.author.lower() != source.author.lower()
        or main.display_name != source.display_name
    ):
        raise XError("The native detail author does not match the selected X post.")
    if source.body is not None:
        prefix = MORE.sub("", source.body)
        if main.body is None or (
            main.body != source.body
            and (
                source.body_complete
                or len(prefix) < 32
                or not main.body.startswith(prefix)
            )
        ):
            raise XError("The native detail body does not match the selected X post.")
    elif main.body is not None:
        raise XError("The native detail added a body to the selected bodyless X post.")
    if _quote_content(main.quoted_post) != _quote_content(source.quoted_post) and (
        main.quoted_post is not None or main.body_complete
    ):
        raise XError("The native detail quote does not match the selected X post.")
    observed_media = tuple((m.kind, m.description) for m in main.media)
    expected_media = tuple((m.kind, m.description) for m in source.media)
    if observed_media != expected_media and (observed_media or main.body_complete):
        raise XError("The native detail media does not match the selected X post.")
    return main.observable


class _TextCoverage:
    def __init__(self, detail):
        main = detail.main_post
        self.text = (
            main.body
            if main is not None
            and main.header_visibility.unobscured
            and main.author_visibility.unobscured
            else None
        )
        self.seen = bytearray(len(self.text or ""))
        if self.text is not None and main.body_complete:
            self.seen[:] = b"\1" * len(self.seen)

    def add(self, detail):
        if self.text is None or detail.text is None:
            return
        if detail.text.text != self.text:
            raise XError("The native main text changed during bounded reading.")
        for span in detail.text.ranges:
            if span.visibility.unobscured:
                self.seen[span.start : span.end] = b"\1" * (span.end - span.start)

    def result(self):
        from .expansion import MORE

        if self.text is None:
            return None, False
        end = next(
            (
                i
                for i, char in enumerate(self.text)
                if not char.isspace() and not self.seen[i]
            ),
            len(self.text),
        )
        return self.text[:end], end == len(self.text) and not MORE.search(self.text)


def inspect_thread(app, *, max_posts, max_scrolls):
    _limit(max_posts, "max_posts", 1, 50)
    _limit(max_scrolls, "max_scrolls", 0, 8)
    with app._visit("Open post", "detail") as (source, screen):
        current = app._snapshot()
        _detail_context(screen, current)
        _verify_main_source(source, screen.detail.main_post)
        main_verified = _verify_main_source(source, current.detail.main_post)
        screen, detail = current, current.detail
        coverage = _TextCoverage(detail)
        posts, seen = [], set()
        scrolls = 0
        while True:
            coverage.add(screen.detail)
            for post in screen.observable_posts:
                if post.content_key not in seen and len(posts) < max_posts:
                    posts.append(post)
                    seen.add(post.content_key)
            if len(posts) == max_posts:
                reason = "post_limit"
                break
            if scrolls == max_scrolls:
                reason = "scroll_limit"
                break
            current = app._snapshot()
            _detail_context(screen, current)
            _verify_main_source(source, current.detail.main_post)
            try:
                stationary = _scroll_motion(screen, current)
                region, distance, exclusions = scroll_region(current)
            except XError:
                reason = "insufficient_scroll_evidence"
                break
            if stationary != 0:
                raise XError("The X thread moved outside inspection scrolling.")
            app.phone.gesture(
                "scroll", "up", region, distance=distance, exclude=exclusions
            ).require()
            app.phone.wait(0.3, purpose="readiness")
            scrolls += 1
            after = app._snapshot()
            _detail_context(current, after)
            _verify_main_source(source, after.detail.main_post)
            try:
                shift = _scroll_motion(current, after)
            except XError:
                reason = "unverified_movement"
                break
            if shift >= -2:
                reason = "no_progress"
                break
            screen = after
        main_text, text_complete = coverage.result()
        result = ThreadInspection(
            source.content_key,
            detail,
            tuple(posts),
            scrolls,
            reason,
            main_verified=main_verified,
            main_text=main_text,
            main_text_complete=text_complete,
        )
    return result


def _frame(phone, crop):
    image = phone.read("screenshot")
    if image.size != tuple(phone.read("size")):
        raise XError("X screen dimensions changed during media capture.")
    frame = image.crop(crop).convert("RGB")
    frame.thumbnail((1024, 1024))
    buffer = io.BytesIO()
    frame.save(buffer, format="JPEG", quality=85)
    return buffer.getvalue()


def _gallery_matches(screen, source, media):
    gallery = screen.gallery
    if (
        screen.kind != "media"
        or gallery is None
        or gallery.author.lower() != source.author.lower()
        or gallery.caption.text != source.body
        or gallery.description != media.description.removeprefix("Image: ")
    ):
        raise XError("The X media gallery does not verify the selected post and image.")
    return gallery


def inspect_media(app, *, index, frame_count, interval):
    _limit(index, "index", 0, 3)
    _limit(frame_count, "frame_count", 1, 6)
    if (
        not isinstance(interval, (int, float))
        or not math.isfinite(interval)
        or not 0 <= interval <= 5
    ):
        raise ValueError("Media frame interval must be between zero and five seconds.")
    with app._operation():
        source = app.observe()
        if source is None or index >= len(source.media):
            raise XError("The selected X post has no such media item.")
        media = source.media[index]
        if media.kind == "image":
            if (
                not media.description
                or sum(m.description == media.description for m in source.media) != 1
            ):
                raise XError("The selected X image is ambiguous.")
            with app._visit(f"Open media {index}", "media") as (fresh, screen):
                if fresh.content_key != source.content_key:
                    raise XError("X changed before opening its media.")
                gallery = _gallery_matches(screen, source, media)
                frames = []
                for number in range(frame_count):
                    if number:
                        app.phone.wait(interval, purpose="frame")
                    current = _gallery_matches(app._snapshot(), source, media)
                    if current != gallery:
                        raise XError("The X gallery geometry changed during capture.")
                    frames.append(_frame(app.phone, gallery.crop))
                    if _gallery_matches(app._snapshot(), source, media) != gallery:
                        raise XError("The X gallery changed during capture.")
                result = MediaInspection(
                    source.content_key,
                    index,
                    media,
                    tuple(frames),
                    "gallery",
                    gallery.crop,
                    False,
                )
            return result
        if (
            media.kind not in {"video", "gif"}
            or media.visibility.visible_bounds is None
        ):
            raise XError("No supported, visible X media to inspect.")
        regions = list(
            _free_regions(media.visibility.visible_bounds, media.visibility.overlaps, 1)
        )
        if not regions:
            raise XError("The X media is covered by controls.")
        crop = max(regions, key=lambda r: (r[2] - r[0]) * (r[3] - r[1]))
        frames = []
        for number in range(frame_count):
            if number:
                app.phone.wait(interval, purpose="frame")
            for capture in (True, False):
                current = app.observe()
                if (
                    current.content_key != source.content_key
                    or index >= len(current.media)
                    or current.media[index] != media
                ):
                    raise XError("The X media changed during capture.")
                if capture:
                    frames.append(_frame(app.phone, crop))
        return MediaInspection(
            source.content_key,
            index,
            media,
            tuple(frames),
            "inline",
            crop,
            crop != media.visibility.bounds,
        )
