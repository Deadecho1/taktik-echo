"""Bind a fresh native Copy link receipt to the selected browsing occurrence."""

from dataclasses import dataclass, fields, is_dataclass, replace
from urllib.parse import urlsplit

from taktik.core.shared.post_urls import canonicalize

from ...ui.screen import Visibility
from .navigation import READ_ATTEMPTS, XError, _alignment
from .selection import _control, _post, _source, _tap


@dataclass(frozen=True)
class PostLink:
    source_key: str
    author: str
    post_id: str
    url: str


def _rectangles(value):
    """Keep all native bounds while allowing coverage and readability to change."""
    if isinstance(value, Visibility):
        yield value.bounds
    elif is_dataclass(value):
        for field in fields(value):
            yield from _rectangles(getattr(value, field.name))
    elif isinstance(value, tuple):
        for item in value:
            yield from _rectangles(item)


def _verify_source(before, source, screen):
    candidates = [p for p in screen.posts if p.content_key == source.content_key]
    if (
        len(candidates) != 1
        or candidates[0].author != source.author
        or tuple(_rectangles(candidates[0])) != tuple(_rectangles(source))
    ):
        raise XError("The selected X source changed during clipboard verification.")
    _alignment(
        replace(before, posts=(source,), fragments=()),
        replace(screen, posts=(candidates[0],), fragments=()),
    )


def wait_for_clipboard_dismissal(app, screen):
    before = app._screen
    if (
        screen.obscured_screen is None
        or before.clipboard_text is None
        or before.clipboard_bounds is None
        or app._index is None
    ):
        return screen
    source = before.posts[app._index]
    for attempt in range(READ_ATTEMPTS):
        current = screen.obscured_screen or screen
        if screen.obscured_screen is not None:
            previous, retained = before.clipboard_bounds, current.clipboard_bounds
            retracting = (
                retained is not None
                and retained[1:] == previous[1:]
                and previous[0] <= retained[0] < previous[2]
            )
            fullscreen = (
                screen.waiting_for == "fullscreen_system_window"
                and before.kind == current.kind == "home"
                and before.collapsed
                and current.collapsed
            )
            if not (retracting or fullscreen):
                raise XError("Unrecognized window during X clipboard dismissal.")
        app._check_timeline(current, before)
        if current.content_viewport != before.content_viewport:
            raise XError("X viewport changed during clipboard dismissal.")
        if current.active_account not in {None, app.verified_account}:
            raise XError("X account changed during clipboard dismissal.")
        if current.clipboard_text not in {None, before.clipboard_text}:
            raise XError("The clipboard receipt changed during dismissal.")
        _verify_source(before, source, current)
        if current.clipboard_bounds is None:
            return current
        if attempt < READ_ATTEMPTS - 1:
            app.phone.wait(0.3, purpose="readiness")
            screen = app._snapshot()
    raise XError("Cannot verify X clipboard dismissal within the read limit.")


def _link(source, value):
    try:
        url, post_id = canonicalize("x", value)
    except ValueError as error:
        raise XError(
            "The native Copy link receipt has no direct X post URL."
        ) from error
    author = "@" + urlsplit(url).path.split("/")[1]
    if author.lower() != source.author.lower():
        raise XError("The copied X link does not identify the selected outer author.")
    return PostLink(source.content_key, author, post_id, url)


def _restore(app, source):
    screen = app._snapshot()
    if screen.kind == "share":
        _tap(app, screen.controls, "Close sheet")
    if app._screen is None:
        return
    screen = app._wait_for(
        lambda s: s.kind == app._screen.kind and _post(app, source, s) is not None,
        "the original X post after Share",
    )
    app._select(screen, app._index)
    app.observe()


def _returned(app, source, link, screen):
    if (
        screen.clipboard_text is not None
        and _link(source, screen.clipboard_text) != link
    ):
        raise XError("The native copied link changed during verification.")
    app._check_timeline(screen, app._screen)
    _verify_source(app._screen, source, screen)
    return _post(app, source, screen) is not None


def copy_link(app):
    with app._operation():
        source = _source(app)
        _control(source.actions, "Share")
        try:
            _tap(app, source.actions, "Share")
            sheet = app._wait_for(
                lambda s: s.kind == "share" and s.clipboard_text is None,
                "the native X Share sheet without an old clipboard receipt",
            )
            current = app._snapshot()
            if (
                current.kind != "share"
                or current.clipboard_text is not None
                or current.controls != sheet.controls
            ):
                raise XError("The X Share controls changed before Copy link.")
            _tap(app, current.controls, "Copy link")
            screen = app._wait_for(
                lambda s: s.kind == app._screen.kind and s.clipboard_text is not None,
                "a fresh native Copy link receipt",
            )
            link = _link(source, screen.clipboard_text)
            if not _returned(app, source, link, screen):
                # The clipboard preview can cover the unchanged source body.
                screen = app._wait_for(
                    lambda s: _returned(app, source, link, s),
                    "the selected X occurrence after Copy link",
                    interval=1.0,
                )
            app._select(screen, app._index)
            app.observe()
            if not _returned(app, source, link, app._screen):
                raise XError("Copy link did not return to the selected X occurrence.")
            return link
        except BaseException as error:
            with app.phone.cleanup():
                try:
                    _restore(app, source)
                except Exception as cleanup_error:
                    raise error from cleanup_error
            raise
