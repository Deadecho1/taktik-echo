"""Verify native feedback and Undo without losing the source occurrence."""

from taktik.core.shared.phone_interaction import InteractionError
from taktik.core.social_media.x.services.browsing.engagement import (
    _apply_feedback,
    _matches_removal_source,
    _uncertain,
)
from taktik.core.social_media.x.services.browsing.navigation import (
    SCROLL_ATTEMPTS,
    XError,
    scroll_region,
)
from taktik.core.social_media.x.services.browsing.selection import _source, _tap


def _receipt(app, source, screen):
    if screen.kind in {"unsupported", "post_options"}:
        return None
    app._check_timeline(screen, app._screen, scrolling=True)
    if any(p.content_key == source.content_key for p in screen.posts):
        return None
    notices = [n for n in screen.removal_notices if n.action == "not_interested"]
    if len(notices) > 1:
        raise XError("Feedback Undo receipt is ambiguous.")
    return (
        notices[0] if notices and _matches_removal_source(notices[0], source) else None
    )


def _find_undo(app, source):
    preference = None
    for attempt in range(SCROLL_ATTEMPTS + 1):
        screen = app._wait_for(
            lambda s: _receipt(app, source, s) is not None, "feedback Undo"
        )
        receipt = _receipt(app, source, screen)
        if receipt.preference is not None:
            if preference is not None and receipt.preference != preference:
                raise XError("The X feedback preference changed while revealing Undo.")
            preference = receipt.preference
        if receipt.undo.visibility.unobscured:
            return receipt.undo
        if attempt == SCROLL_ATTEMPTS:
            break
        region, distance, exclusions = scroll_region(screen)
        viewport = screen.content_viewport
        direction = "down" if receipt.undo.visibility.bounds[1] < viewport[1] else "up"
        app.phone.gesture(
            "scroll",
            direction,
            region,
            distance=min(distance, (viewport[3] - viewport[1]) * 0.1),
            exclude=exclusions,
        ).require()
        app.phone.wait(0.3, purpose="readiness")
    raise XError("Cannot reveal the feedback Undo control.")


def _restored(app, source, screen):
    if screen.kind in {"unsupported", "post_options"}:
        return None
    app._check_timeline(screen, app._screen, scrolling=True)
    matches = [p for p in screen.posts if p.content_key == source.content_key]
    if (
        len(matches) == 1
        and matches[0].author == source.author
        and matches[0].reposted_by == source.reposted_by
        and matches[0].observable
        and not any(n.action == "not_interested" for n in screen.removal_notices)
    ):
        return matches[0]
    return None


def check_feedback_roundtrip(browser, observation):
    """Return restoration evidence only after the original post is verified."""
    app = browser.browser
    with app._operation():
        browser.observe(previous=observation)
        source = _source(app)
        if source.reposted_by != observation.post_context.get("reposted_by"):
            raise XError("The X repost annotation changed before feedback.")
        _apply_feedback(app, source)
        try:
            undo = _find_undo(app, source)
            _tap(app, (undo,), "Undo")
            restored = app._wait_for(
                lambda s: _restored(app, source, s) is not None,
                "feedback Undo restoration",
            )
            app._select(
                restored, restored.posts.index(_restored(app, source, restored))
            )
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
