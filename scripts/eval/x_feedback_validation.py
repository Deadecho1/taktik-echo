"""Verify native feedback and Undo without losing the source occurrence."""

from taktik.core.shared.phone_interaction import InteractionError
from taktik.core.social_media.x.services.browsing.engagement import (
    _apply_feedback_and_confirm,
    _uncertain,
)
from taktik.core.social_media.x.services.browsing.navigation import XError
from taktik.core.social_media.x.services.browsing.selection import _post, _source, _tap


def _receipt(app, source, screen):
    app._check_timeline(screen, app._screen)
    if any(p.content_key == source.content_key for p in screen.posts):
        raise XError("The feedback source reappeared before Undo.")
    notices = [
        n
        for n in screen.removal_notices
        if n.action == "not_interested"
        and n.author
        and n.author.lower() == source.author.lower()
        and n.visibility.bounds[1] == source.header_visibility.bounds[1]
    ]
    if len(notices) != 1:
        raise XError("Feedback Undo receipt unavailable.")
    return notices[0]


def _restored(app, source, screen):
    return (
        not any(
            n.action == "not_interested"
            and (n.author is None or n.author.lower() == source.author.lower())
            for n in screen.removal_notices
        )
        and _post(app, source, screen) is not None
    )


def check_feedback_roundtrip(browser, observation):
    """Return restoration evidence only after the original post is verified."""
    app = browser.browser
    with app._operation():
        browser.observe(previous=observation)
        source = _source(app)
        screen = _apply_feedback_and_confirm(app, source)
        try:
            receipt = _receipt(app, source, screen)
            current = app._snapshot()
            if _receipt(app, source, current) != receipt:
                raise XError("The feedback Undo receipt changed before restoration.")
            _tap(app, (receipt.undo,), "Undo")
            restored = app._wait_for(
                lambda s: _restored(app, source, s), "feedback Undo restoration"
            )
            app._select(restored, app._index)
            browser.observe(previous=observation)
            if not _restored(app, source, app._screen):
                raise XError("The feedback Undo restoration did not persist.")
        except InteractionError as error:
            _uncertain("feedback Undo", error)
        return {
            "source_identity": observation.identity,
            "source_key": source.content_key,
            "restored": True,
        }
