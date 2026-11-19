"""Native engagement state and scoped menus; no device access."""

from dataclasses import dataclass

from .screen import (
    HANDLE,
    Screen,
    Target,
    Visibility,
    _clickable,
    _desc,
    _one,
    _rect,
    _target,
    _Unsupported,
    _visibility,
)


@dataclass(frozen=True)
class PostOptions:
    author: str
    following: bool
    feedback_label: str | None


@dataclass(frozen=True)
class RemovalNotice:
    action: str
    text: str
    author: str | None
    visibility: Visibility
    undo: Target


def read_notices(scope, viewport, overlays):
    notices = []
    for node in scope.xpath('.//*[@class="android.widget.TextView"]'):
        text = node.get("text", "")
        if text.startswith("You unfollowed "):
            action, author = "unfollow", text.removeprefix("You unfollowed ")
            expected_count = 2
        elif text == "Thanks. X will use this to make your timeline better.":
            action, author = "not_interested", None
            expected_count = 4
        else:
            continue
        if author is not None and not HANDLE.fullmatch(author):
            continue
        row = node.getparent()
        ancestors = []
        for ancestor in node.iterancestors():
            if ancestor.get("scrollable") == "true":
                break
            ancestors.append(ancestor)
        if any(a.get("clickable") == "true" for a in ancestors):
            continue
        texts = row.xpath('.//*[@text!=""]')
        undo = row.xpath('.//*[@text="Undo"]')
        if (
            len(row) != expected_count
            or len(texts) != expected_count
            or len(undo) != 1
            or texts[0] is not node
        ):
            continue
        if action == "not_interested":
            fewer = texts[2].get("text", "")
            author = "@" + fewer.removeprefix("Show fewer posts from ")
            if not fewer.startswith("Show fewer posts from ") or not HANDLE.fullmatch(
                author
            ):
                continue
            if texts[3].get("text") != "This post isn’t relevant":
                continue
            for extra in texts[2:]:
                _target(extra, extra.get("text"), row, viewport, overlays)
        target = _target(undo[0], "Undo", row, viewport, overlays)
        visibility = _visibility(row, viewport, overlays)
        if not all(
            _visibility(n, viewport, overlays).unobscured for n in (row, *texts)
        ):
            continue
        if _rect(node)[2] > target.visibility.bounds[0]:
            continue
        notices.append(RemovalNotice(action, text, author, visibility, target))
    return tuple(notices)


def read_options(root, area, overlays):
    from .inspection import _control_covers

    close = _one(_desc(root, "Close sheet"), "sheet dismissal")
    menu = _one(root.xpath('.//*[@class="android.widget.ScrollView"]'), "options list")
    panel = menu
    for ancestor in menu.iterancestors():
        if close in ancestor.iter():
            break
        panel = ancestor
    labels = []
    controls = [_target(close, "Close sheet", root, area, (*overlays, _rect(panel)))]
    for row in menu:
        text = _one(row.xpath('.//*[@text!=""]'), "option label")
        label = text.get("text")
        labels.append(label)
        target = _clickable(text, menu)
        covers = (*overlays, *_control_covers(menu, target))
        if not _visibility(text, area, covers).unobscured:
            raise _Unsupported("Post options are obscured.")
        controls.append(_target(text, label, menu, area, covers))
    fixed = {
        "Add/remove from Lists",
        "Report post",
        "Request Community Note",
        "View Post Interactions",
        "View Hidden Replies",
    }
    feedback_labels = [
        s for s in labels if s in {"This post's not helpful", "Not interested in Post"}
    ]
    if len(feedback_labels) > 1:
        raise _Unsupported("Ambiguous recommendation feedback.")
    feedback = feedback_labels[0] if feedback_labels else None
    follow = _one(
        [s for s in labels if s.startswith(("Follow ", "Unfollow "))],
        "follow state option",
    )
    author = follow.split(" ", 1)[1]
    if not HANDLE.fullmatch(author):
        raise _Unsupported("Invalid options author.")
    expected = fixed | {follow, f"Mute {author}", f"Block {author}"}
    if feedback:
        expected.add(feedback)
    if len(labels) != len(expected) or set(labels) != expected:
        raise _Unsupported("Unrecognized post options structure.")
    return Screen(
        "post_options",
        overlaps=overlays,
        controls=tuple(controls),
        post_options=PostOptions(author, follow.startswith("Unfollow "), feedback),
    )
