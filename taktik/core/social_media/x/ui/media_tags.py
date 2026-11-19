"""The native tag label beneath outer media, without inferred account handles."""


def media_tag(node, media, actions, viewport, overlaps):
    from .screen import (
        ACTION_LABELS,
        _intersect,
        _rect,
        _Unsupported,
        _visibility,
    )

    previous, following = node.getprevious(), node.getnext()
    rect = _rect(node)
    visibility = _visibility(node, viewport, overlaps)
    if (
        not media
        or any(item.kind not in {"image", "video", "gif"} for item in media)
        or previous is None
        or following is None
        or node.get("class") != "android.widget.TextView"
        or not node.get("text", "").strip()
        or node.get("content-desc")
        or len(node)
        or any(node.get(flag) != "true" for flag in ("clickable", "focusable"))
        or any(node.get(flag) == "true" for flag in ("long-clickable", "scrollable"))
        or not visibility.accessible
        or tuple(action.label for action in actions) != ACTION_LABELS
        or _rect(following) != actions[0].visibility.bounds
        or any(action.visibility.bounds[1] != rect[3] for action in actions)
        or any(item.visibility.bounds[3] != _rect(previous)[3] for item in media)
        or rect[0] != min(item.visibility.bounds[0] for item in media)
        or rect[2] > max(item.visibility.bounds[2] for item in media)
        or not rect[1] <= _rect(previous)[3] < rect[3]
        # Native label touch padding overlaps the bottom of its media.
        or _rect(previous)[3] - rect[1] > (rect[3] - rect[1]) / 2
        or _intersect(rect, _rect(node.getparent())) != rect
    ):
        raise _Unsupported("Unrecognized media tag annotation.")
    return node.get("text") if visibility.unobscured else None
