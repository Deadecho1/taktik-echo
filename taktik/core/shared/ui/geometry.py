"""Native screen geometry and selector helpers shared by platform adapters."""

from taktik.core.shared.device.ui_dump import parse_bounds


def intersection(a, b):
    result = max(a[0], b[0]), max(a[1], b[1]), min(a[2], b[2]), min(a[3], b[3])
    return result if result[0] < result[2] and result[1] < result[3] else None


def free_regions(area, exclusions, minimum_width):
    """Continuous rectangles excluding controls, for capture or safe gestures."""
    boxes = [box for rect in exclusions if (box := intersection(area, rect))]
    edges = sorted({area[0], area[2], *(x for box in boxes for x in (box[0], box[2]))})
    for i, left in enumerate(edges):
        for right in edges[i + 1 :]:
            if right - left < minimum_width:
                continue
            blocked = sorted(
                (b[1], b[3]) for b in boxes if b[0] < right and b[2] > left
            )
            top = area[1]
            for start, end in blocked:
                if start > top:
                    yield left, top, right, start
                top = max(top, end)
            if top < area[3]:
                yield left, top, right, area[3]


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
