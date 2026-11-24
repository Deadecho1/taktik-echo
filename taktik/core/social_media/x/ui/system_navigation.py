"""Recognize Android's bottom buttons as exclusions, never X controls."""

from .screen import _intersect, _rect, _Unsupported, _visibility

PREFIX = "com.android.systemui:id/"
WRAPPERS = {
    "navigation_bar_frame",
    "navigation_bar_view",
    "navigation_inflater",
    "horizontal",
    "nav_buttons",
    "nav_bar_widget",
    "ends_group",
    "center_group",
    "menu_container",
}
BUTTONS = {"back": {"Back"}, "home": {"Home"}, "recent_apps": {"Overview", "Recents"}}
OPTIONAL_BUTTONS = {"ime_switcher": {"Switch input method"}}


def bottom_bar(window, area):
    if window.get("resource-id") != PREFIX + "navigation_bar_frame":
        return None
    nodes = list(window.iter())
    if any(node.get("package") != "com.android.systemui" for node in nodes):
        raise _Unsupported("Unexpected package inside Android navigation bar.")
    top = min(_rect(node)[1] for node in nodes)
    if top < area[3] * 0.9 or _rect(window)[3] != area[3]:
        raise _Unsupported("Unrecognized Android navigation bar geometry.")
    found = set()
    back = None
    for node in nodes:
        identity = node.get("resource-id", "").removeprefix(PREFIX)
        rect = _rect(node)
        if (
            node.get("text")
            or node.get("content-desc", "")
            not in (BUTTONS | OPTIONAL_BUTTONS).get(identity, {""})
            or identity
            not in WRAPPERS | BUTTONS.keys() | OPTIONAL_BUTTONS.keys() | {""}
            or _intersect(rect, area) != rect
            or rect[1] < top
            or node.get("scrollable") == "true"
        ):
            raise _Unsupported("Unrecognized Android navigation bar content.")
        if identity in BUTTONS | OPTIONAL_BUTTONS:
            if identity in found or node.get("class") != "android.widget.ImageView":
                raise _Unsupported("Ambiguous Android navigation button.")
            found.add(identity)
            if identity == "back":
                visible = _visibility(node, area)
                if not visible.unobscured:
                    raise _Unsupported("Android Back button is obscured.")
                back = visible.visible_bounds
    if not BUTTONS.keys() <= found:
        raise _Unsupported("Incomplete Android navigation bar.")
    # Some OEM roots exclude the ends of their own child containers. Exclude the
    # complete bottom band so no X target or gesture can enter those controls.
    return (area[0], top, area[2], area[3]), back
