"""Single-attempt engagement with native target and outcome verification."""

from dataclasses import dataclass

from taktik.core.shared.phone_interaction import InteractionError, Result, Status

from .navigation import XError
from .selection import _control, _post, _source, _tap, _unsupported


@dataclass(frozen=True)
class EngagementResult:
    action: str
    source_key: str
    changed: bool
    selected: bool | None = None
    advanced: bool = False


def _uncertain(action, error):
    message = f"X could not finish verifying {action}; do not repeat the engagement."
    raise XError(message, result=Result(Status.UNCERTAIN, detail=message)) from error


def set_footer(app, label, selected):
    if type(selected) is not bool:
        raise ValueError("An X engagement state must be boolean.")
    action = {"Like": "like", "Bookmark": "save"}[label]
    with app._operation():
        source = _source(app)
        target, region = _control(source.actions, label)
        if (
            target.selected is None
            or target.state_visibility is None
            or not target.state_visibility.unobscured
        ):
            _unsupported(f"The native X {label} state is unknown.")
        if target.selected == selected:
            return EngagementResult(action, source.content_key, False, selected)
        try:
            app.phone.tap(region, exclude=target.visibility.overlaps).require()

            def confirmed(screen):
                post = _post(app, source, screen)
                if post is None:
                    return False
                targets = [t for t in post.actions if t.label == label]
                return (
                    len(targets) == 1
                    and targets[0].selected == selected
                    and targets[0].state_visibility is not None
                    and targets[0].state_visibility.unobscured
                )

            screen = app._wait_for(confirmed, f"{label} state")
            app._select(screen, app._index)
            current = app.observe()
            if not any(
                t.label == label
                and t.selected == selected
                and t.state_visibility is not None
                and t.state_visibility.unobscured
                for t in current.actions
            ):
                raise XError(f"The X {label} state did not persist.")
        except InteractionError as error:
            _uncertain(action, error)
        return EngagementResult(action, source.content_key, True, selected)


def _menu_author(source, screen):
    if (
        screen.kind != "post_options"
        or screen.post_options is None
        or screen.post_options.author.lower() != source.author.lower()
    ):
        raise XError("The X post menu does not identify the selected author.")
    return screen.post_options


def _open_menu(app, source):
    current = _source(app)
    if current.content_key != source.content_key:
        raise XError("The X source changed before opening its menu.")
    _tap(app, current.targets, "Post options")
    screen = app._wait_for(lambda s: s.kind == "post_options", "post menu")
    _menu_author(source, screen)
    return screen


def _return_to_source(app, source):
    screen = app._wait_for(
        lambda s: s.kind != "post_options" and _post(app, source, s) is not None,
        "the original X engagement occurrence",
    )
    app._select(screen, app._index)
    return app.observe()


def _close_menu(app, source, screen):
    _menu_author(source, screen)
    _tap(app, screen.controls, "Close sheet")
    return _return_to_source(app, source)


def _removed(app, source, action):
    def confirmed(screen):
        if screen.kind in {"unsupported", "post_options"}:
            return False
        app._check_timeline(screen, app._screen)
        if any(p.content_key == source.content_key for p in screen.posts):
            return False
        notices = [
            n
            for n in screen.removal_notices
            if n.action == action
            and (n.author is None or n.author.lower() == source.author.lower())
            and n.visibility.bounds[1] == source.header_visibility.bounds[1]
        ]
        return len(notices) == 1

    screen = app._wait_for(confirmed, f"native {action} confirmation")
    current = app._snapshot()
    if not confirmed(current) or current.removal_notices != screen.removal_notices:
        raise XError("The X engagement confirmation did not persist.")
    app.navigation_gaps.append(
        {
            "method": "engagement_removal",
            "action": action,
            "source_key": source.content_key,
        }
    )
    app._first_post(current, retained_context=True)
    app.observe()
    return EngagementResult(
        action, source.content_key, True, False if action == "unfollow" else None, True
    )


def set_following(app, selected):
    action = "follow" if selected else "unfollow"
    with app._operation():
        source = _source(app)
        if source.author.lower() == app.verified_account.lower():
            _unsupported("X cannot follow the active account.")
        screen = _open_menu(app, source)
        state = _menu_author(source, screen)
        if state.following == selected:
            _close_menu(app, source, screen)
            return EngagementResult(action, source.content_key, False, selected)
        current = app._snapshot()
        if _menu_author(source, current) != state:
            raise XError("The X relationship changed before engagement.")
        label = f"{'Follow' if selected else 'Unfollow'} {state.author}"
        _control(current.controls, label)
        try:
            _tap(app, current.controls, label)
            if not selected:
                return _removed(app, source, action)
            _return_to_source(app, source)
            menu = _open_menu(app, source)
            if _menu_author(source, menu).following != selected:
                raise XError("The X relationship did not change.")
            current = app._snapshot()
            if _menu_author(source, current).following != selected:
                raise XError("The X relationship did not persist.")
            _close_menu(app, source, current)
        except InteractionError as error:
            _uncertain(action, error)
        return EngagementResult(action, source.content_key, True, selected)


def not_interested(app):
    with app._operation():
        source = _source(app)
        screen = _open_menu(app, source)
        state = _menu_author(source, screen)
        if state.feedback_label != "Not interested in Post":
            _close_menu(app, source, screen)
            _unsupported(
                "X does not offer verified Not interested feedback for this post."
            )
        current = app._snapshot()
        if _menu_author(source, current) != state:
            raise XError("The X feedback menu changed before engagement.")
        _control(current.controls, state.feedback_label)
        try:
            _tap(app, current.controls, state.feedback_label)
            return _removed(app, source, "not_interested")
        except InteractionError as error:
            _uncertain("not_interested", error)
