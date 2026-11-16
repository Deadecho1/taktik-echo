"""Native screen geometry and selector helpers shared by platform adapters."""

from taktik.core.shared.device.ui_dump import parse_bounds


def bounds(node):
    return parse_bounds(node.get("bounds", ""))


def nodes(root, selectors, within=None):
    for selector in selectors:
        found = []
        for node in root.xpath(selector):
            rect = bounds(node)
            if (
                rect is None
                or rect[2] <= rect[0]
                or rect[3] <= rect[1]
                or node.get("enabled") == "false"
            ):
                continue
            if within and not (
                within[0] <= rect[0] < rect[2] <= within[2]
                and within[1] <= rect[1] < rect[3] <= within[3]
            ):
                continue
            found.append(node)
        if found:
            return found
    return []


def text_of(node):
    return node.get("text") or node.get("content-desc") or ""
