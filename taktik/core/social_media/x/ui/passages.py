"""Retain native text below a fully hidden, incomplete search author header."""


def hidden_header_passage(header, viewport, overlaps):
    from .screen import (
        HANDLE,
        VERIFICATION_LABELS,
        PostFragment,
        _intersect,
        _plain_annotation,
        _rect,
        _translation,
        _visibility,
    )

    container = header.getparent()
    if len(header) != 3 or len(container) != 7 or container[1] is not header:
        return None
    name, badge, handle = header
    avatar, _, grok, options, label, original, body = container
    rect = _rect(body)
    if (
        container.get("class") != "android.view.View"
        or container.get("clickable") != "true"
        or container.get("text")
        or container.get("content-desc")
        or header.get("class") != "android.view.View"
        or header.get("text")
        or header.get("content-desc")
        or any(
            header.get(flag) == "true"
            for flag in ("clickable", "focusable", "long-clickable", "scrollable")
        )
        or not all(_plain_annotation(n) for n in (name, handle, body))
        or not name.get("text")
        or "@" in name.get("text")
        or not HANDLE.fullmatch(handle.get("text", ""))
        or badge.get("class") != "android.view.View"
        or badge.get("content-desc") not in VERIFICATION_LABELS
        or badge.get("text")
        or len(badge)
        or any(
            badge.get(flag) == "true"
            for flag in ("clickable", "focusable", "long-clickable", "scrollable")
        )
        or any(_intersect(_rect(n), _rect(header)) != _rect(n) for n in header)
        or not (_rect(name)[2] <= _rect(badge)[0] < _rect(badge)[2] <= _rect(handle)[0])
        or any(_rect(n)[3] > viewport[1] for n in container if n is not body)
        or any(
            not _visibility(n, viewport, overlaps).accessible for n in container.iter()
        )
        or not body.get("text")
        or not (rect[1] < viewport[1] < viewport[3] <= rect[3])
        or not (viewport[0] <= rect[0] < rect[2] <= viewport[2])
        or _intersect(rect, _rect(container)) != rect
    ):
        return None
    for node, kind, description, long_clickable in (
        (avatar, "android.widget.ImageView", name.get("text"), True),
        (grok, "android.widget.ImageView", "Explain this post with Grok", False),
        (options, "android.widget.Button", "Post options", False),
    ):
        if (
            node.get("class") != kind
            or node.get("content-desc") != description
            or node.get("text")
            or len(node)
            or node.get("scrollable") == "true"
            or (node.get("long-clickable") == "true") != long_clickable
            or any(node.get(flag) != "true" for flag in ("clickable", "focusable"))
        ):
            return None
    translation, nodes = _translation(container, header)
    if not translation or nodes != {label, original} or _rect(original)[3] != rect[1]:
        return None
    return PostFragment(
        body.get("text"),
        (),
        _visibility(container, viewport, overlaps),
        _visibility(body, viewport, overlaps),
        translation=translation,
    )
