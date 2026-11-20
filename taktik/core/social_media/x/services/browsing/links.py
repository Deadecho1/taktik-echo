"""Bind a fresh native Copy link receipt to the selected browsing occurrence."""

from dataclasses import dataclass, replace
from urllib.parse import urlsplit

from taktik.core.shared.post_urls import canonicalize

from .navigation import XError, _alignment
from .selection import _control, _post, _source, _tap


@dataclass(frozen=True)
class PostLink:
    source_key: str
    author: str
    post_id: str
    url: str


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
    candidates = [p for p in screen.posts if p.content_key == source.content_key]
    if (
        len(candidates) != 1
        or candidates[0].author != source.author
        or candidates[0].visibility.bounds != source.visibility.bounds
    ):
        raise XError("Copy link did not return to the selected X occurrence.")
    _alignment(
        replace(app._screen, posts=(source,), fragments=()),
        replace(screen, posts=(candidates[0],), fragments=()),
    )
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
