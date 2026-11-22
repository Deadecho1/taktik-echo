"""Visible native character ranges, independent of a clipped body rectangle."""

import math
from dataclasses import dataclass

from .screen import TextSpan, Visibility, _intersect, _Unsupported, _visibility


@dataclass(frozen=True)
class TextRange:
    start: int
    end: int
    visibility: Visibility


@dataclass(frozen=True)
class DetailText:
    text: str
    ranges: tuple[TextRange, ...]

    @property
    def anchors(self):
        return tuple(
            TextSpan(self.text[r.start : r.end], r.visibility) for r in self.ranges
        )


def read_text(listing, viewport, overlays, timestamp):
    from .inspection import _control_covers

    bodies = [
        n for n in listing if n is not timestamp and n.get("taktik-character-locations")
    ]
    if len(bodies) != 1:
        return None
    node = bodies[0]
    text = node.get("text", "")
    positions = node.get("taktik-character-locations").split(";")
    if not text or len(positions) != len(text.encode("utf-16-le")) // 2:
        raise _Unsupported("Native character positions do not match the body.")
    view = _visibility(node, viewport, (*overlays, *_control_covers(listing, node)))
    ranges = []
    unit = 0
    for index, char in enumerate(text):
        count = 2 if ord(char) > 0xFFFF else 1
        values = positions[unit : unit + count]
        unit += count
        if "null" in values:
            continue
        try:
            boxes = [tuple(float(v) for v in value.split(",")) for value in values]
            if any(len(r) != 4 or not all(math.isfinite(v) for v in r) for r in boxes):
                raise ValueError
        except ValueError as error:
            raise _Unsupported("Invalid native character geometry.") from error
        rect = (
            math.floor(min(r[0] for r in boxes)),
            math.floor(min(r[1] for r in boxes)),
            math.ceil(max(r[2] for r in boxes)),
            math.ceil(max(r[3] for r in boxes)),
        )
        if (
            rect[0] >= rect[2]
            or rect[1] >= rect[3]
            or view.visible_bounds is None
            or _intersect(rect, view.visible_bounds) != rect
            or any(_intersect(rect, cover) for cover in view.overlaps)
            or not view.accessible
        ):
            continue
        if (
            ranges
            and ranges[-1].end == index
            and ranges[-1].visibility.bounds[1::2] == rect[1::2]
        ):
            old = ranges.pop()
            previous = old.visibility.bounds
            rect = (
                min(previous[0], rect[0]),
                rect[1],
                max(previous[2], rect[2]),
                rect[3],
            )
            start = old.start
        else:
            start = index
        ranges.append(TextRange(start, index + 1, Visibility(rect, rect)))
    return DetailText(text, tuple(ranges))
