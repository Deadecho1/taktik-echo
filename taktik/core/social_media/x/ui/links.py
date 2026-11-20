"""Native Share targets and Android clipboard receipt metadata."""

from .inspection import _control_covers
from .screen import (
    Screen,
    _clickable,
    _desc,
    _one,
    _rect,
    _target,
    _Unsupported,
    _visibility,
)

SYSTEM_UI = "com.android.systemui"


def empty_system_window(window, area):
    """Identify an inert empty window, without claiming it is a clipboard receipt."""
    return (
        window.get("package") == SYSTEM_UI
        and window.get("class") == "android.widget.FrameLayout"
        and not len(window)
        and all(
            not window.get(key)
            for key in ("text", "resource-id", "content-desc", "hint")
        )
        and all(
            window.get(flag) == "false"
            for flag in (
                "checkable",
                "checked",
                "clickable",
                "focusable",
                "focused",
                "scrollable",
                "long-clickable",
                "password",
                "selected",
            )
        )
        and window.get("enabled") == "true"
        and window.get("visible-to-user") == "true"
        and _visibility(window, area).unobscured
    )


def read_share(root, area, overlays):
    close = _one(_desc(root, "Close sheet"), "Share dismissal")
    copy = _one(root.xpath('.//*[@text="Copy link"]'), "Copy link label")
    via = _one(root.xpath('.//*[@text="Share via…"]'), "Share via label")
    target = _clickable(copy, root)
    other = _clickable(via, root)
    if (
        target.getparent() is not other.getparent()
        or target is other
        or _rect(other)[2] > _rect(target)[0]
        or _rect(other)[1::2] != _rect(target)[1::2]
        or _rect(close)[3] > _rect(target)[1]
    ):
        raise _Unsupported("Unrecognized native Share action row.")
    controls = []
    for node, label in ((close, "Close sheet"), (copy, "Copy link")):
        control = _clickable(node, root)
        covers = (*overlays, *_control_covers(root, control))
        if label == "Copy link" and not _visibility(node, area, covers).unobscured:
            raise _Unsupported(f"The native {label} label is obscured.")
        controls.append(_target(node, label, root, area, covers))
    return Screen("share", overlaps=overlays, controls=tuple(controls))


def read_clipboard(window, area):
    """Return receipt metadata, never a claim that its complete text is visible."""
    if any(n.get("package") != SYSTEM_UI for n in window.iter()):
        raise _Unsupported("Unexpected package inside clipboard receipt.")
    receipt = _one(
        window.xpath('.//*[@resource-id="com.android.systemui:id/clipboard_ui"]'),
        "Android clipboard receipt",
    )
    preview = _one(
        receipt.xpath('.//*[@resource-id="com.android.systemui:id/text_preview"]'),
        "clipboard text preview",
    )
    parent = preview.getparent()
    if (
        receipt.get("content-desc") != "Clipboard"
        or parent.get("resource-id") != SYSTEM_UI + ":id/clipboard_preview"
        or parent.get("clickable") != "true"
        or preview.get("class") != "android.widget.TextView"
        or not preview.get("text")
        or not _visibility(receipt, area).unobscured
        or not _visibility(preview, area).unobscured
    ):
        raise _Unsupported("Unrecognized or obscured clipboard receipt.")
    return preview.get("text")
