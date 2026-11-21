"""Recognition of the native drawer migration tip window."""

from ..screen import PACKAGE, _intersect, _rect, _Unsupported, _visibility

TIP_TEXT = "Bookmarks, Likes, and Offline videos moved here"


def tip_bounds(window, area):
    nodes = list(window.iter())
    classes = (
        "android.view.ViewGroup",
        "android.view.View",
        "android.view.View",
        "android.view.View",
        "android.view.View",
        "android.widget.TextView",
    )
    if tuple(n.get("class") for n in nodes) != classes or any(
        len(n) != (0 if i == 5 else 1) for i, n in enumerate(nodes)
    ):
        raise _Unsupported("Unrecognized X drawer tip structure.")
    rect = _rect(window)
    if _intersect(rect, area) != rect or rect == area:
        raise _Unsupported("Invalid X drawer tip bounds.")
    for i, node in enumerate(nodes):
        if (
            node.get("package") != PACKAGE
            or node.get("resource-id", "") != ("android:id/content" if i == 0 else "")
            or node.get("text", "") != (TIP_TEXT if i == 5 else "")
            or node.get("content-desc", "")
            or node.get("hint", "")
            or any(
                node.get(flag) != ("true" if i == 3 else "false")
                for flag in ("clickable", "focusable")
            )
            or any(
                node.get(flag) != "false"
                for flag in (
                    "checkable",
                    "checked",
                    "focused",
                    "scrollable",
                    "long-clickable",
                    "password",
                    "selected",
                )
            )
            or node.get("enabled") != "true"
            or node.get("visible-to-user") != "true"
            or not _visibility(node, area).unobscured
            or (i < 4 and _rect(node) != rect)
        ):
            raise _Unsupported("Unrecognized X drawer tip content or geometry.")
    return rect
